#!/usr/bin/env python3
# coding: utf-8
"""
Assistente de Estoque IA v2.2 (adaptado do Colab para Render)
Gemini 2.5 Flash + Telegram (webhook) + Google Sheets + Google Calendar
Memória persistente por usuário + function_call seguro
"""

import os
import json
import datetime
import traceback
import logging
from typing import Any, Dict

import requests
import gspread
from googleapiclient.discovery import build
import google.generativeai as genai

# ---------------------------
# Config logging
# ---------------------------
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("estoque-bot")

# ---------------------------
# Environment (Render)
# ---------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")            # obrigatório
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")            # obrigatório (gemini-2.5-flash)
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")    # JSON completo do service account
NOME_PLANILHA = os.getenv("NOME_PLANILHA", "EstoqueDepositoBebidas")
ABA_ESTOQUE = os.getenv("ABA_ESTOQUE", "Estoque")
ABA_MOV = os.getenv("ABA_MOV", "Movimentacoes")
CALENDAR_ID = os.getenv("CALENDAR_ID", "")

MEMORY_FOLDER = os.getenv("MEMORY_FOLDER", "/tmp/memory_users")  # persistência local no container

# Validações básicas
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN não definido nas environment variables.")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY não definido nas environment variables.")
if not GOOGLE_CREDENTIALS:
    raise ValueError("❌ GOOGLE_CREDENTIALS não definido nas environment variables (JSON).")

os.makedirs(MEMORY_FOLDER, exist_ok=True)

# ---------------------------
# Google: Sheets + Calendar
# ---------------------------
try:
    # usamos gspread.service_account_from_dict para construir cliente a partir do JSON carregado em env
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds_dict)
    sheets_service = build("sheets", "v4", credentials=gc.auth)  # opcional, mas mantido
    calendar_service = build("calendar", "v3", credentials=gc.auth)
    logger.info("✅ Conectado ao Google (Sheets + Calendar).")
except Exception as e:
    logger.exception("❌ Erro ao conectar ao Google: %s", e)
    raise

def abrir_aba(nome_aba: str):
    try:
        sh = gc.open(NOME_PLANILHA)
    except Exception as e:
        raise RuntimeError(f"Não foi possível abrir a planilha '{NOME_PLANILHA}': {e}")
    try:
        ws = sh.worksheet(nome_aba)
    except gspread.WorksheetNotFound:
        raise RuntimeError(f"Aba '{nome_aba}' não encontrada. Crie manualmente: {ABA_ESTOQUE} e {ABA_MOV}.")
    return ws

# ---------------------------
# Funções de negócio (Sheets + Calendar)
# ---------------------------
def obter_saldo(produto: str) -> Dict[str, Any]:
    try:
        ws = abrir_aba(ABA_ESTOQUE)
        rows = ws.get_all_records()
        for r in rows:
            nome = str(r.get("Produto","")).strip()
            if produto.strip().lower() in nome.lower():
                try:
                    qtd = int(r.get("Quantidade",0))
                except:
                    qtd = 0
                return {"status":"sucesso","produto": nome,"quantidade":qtd}
        return {"status":"vazio","mensagem":f"{produto} não encontrado."}
    except Exception as e:
        logger.exception("Erro obter_saldo: %s", e)
        return {"status":"erro","mensagem": str(e)}

def registrar_movimentacao(produto: str, quantidade: int, tipo: str, responsavel: str="", observacao: str="") -> Dict[str, Any]:
    try:
        ws = abrir_aba(ABA_MOV)
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = [agora, produto, quantidade, tipo, responsavel or "", observacao or ""]
        ws.append_row(linha)
        return {"status":"sucesso","mensagem":"Movimentação registrada","linha":linha}
    except Exception as e:
        logger.exception("Erro registrar_movimentacao: %s", e)
        return {"status":"erro","mensagem":str(e)}

def atualizar_saldo(produto: str, quantidade: int, acao: str, responsavel: str="", observacao: str="") -> Dict[str, Any]:
    try:
        ws = abrir_aba(ABA_ESTOQUE)
        rows = ws.get_all_records()
        produto_norm = produto.strip()
        encontrado = False
        for idx, r in enumerate(rows, start=2):
            nome = str(r.get("Produto","")).strip()
            if produto_norm.lower() == nome.lower() or produto_norm.lower() in nome.lower():
                encontrado = True
                try:
                    atual = int(r.get("Quantidade",0))
                except:
                    atual = 0
                act_upper = str(acao).strip().upper()
                if act_upper in ["COMPRA","ENTRADA","IN","+"]:
                    novo = atual + int(quantidade)
                    tipo_mov = "Entrada"
                elif act_upper in ["VENDA","SAIDA","OUT","-"]:
                    novo = atual - int(quantidade)
                    tipo_mov = "Saída"
                else:
                    novo = atual + int(quantidade)
                    tipo_mov = acao.capitalize()
                # atualiza: assumimos colunas: A=Produto, B=Quantidade, C=Última Atualização (exemplo)
                ws.update_cell(idx, 2, novo)
                # coluna 3 para timestamp (ajuste conforme sua planilha)
                try:
                    ws.update_cell(idx, 3, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    pass
                mv = registrar_movimentacao(nome, int(quantidade), tipo_mov, responsavel, observacao)
                return {"status":"sucesso","produto":nome,"quantidade":int(quantidade),"novo_saldo":novo,"movimentacao":mv}
        # não encontrado -> adicionar novo
        if not encontrado:
            tipo_mov = "Entrada" if str(acao).strip().upper() in ["COMPRA","ENTRADA"] else acao
            ws.append_row([produto_norm, int(quantidade), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            mv = registrar_movimentacao(produto_norm, int(quantidade), tipo_mov, responsavel, observacao)
            return {"status":"sucesso","produto":produto_norm,"quantidade":int(quantidade),"novo_saldo":int(quantidade),"movimentacao":mv,"mensagem":"Produto novo adicionado ao estoque"}
    except Exception as e:
        logger.exception("Erro atualizar_saldo: %s", e)
        return {"status":"erro","mensagem":str(e)}

def registrar_evento_calendar(titulo: str, descricao: str, data: str, hora: str, duracao_minutos: int = 60) -> Dict[str, Any]:
    try:
        dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        inicio = dt.isoformat()
        fim = (dt + datetime.timedelta(minutes=duracao_minutos)).isoformat()
        evento = {
            'summary': titulo,
            'description': descricao or "",
            'start': {'dateTime': inicio, 'timeZone': 'America/Sao_Paulo'},
            'end': {'dateTime': fim, 'timeZone': 'America/Sao_Paulo'},
        }
        ev = calendar_service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
        return {"status":"sucesso", "mensagem": f"Evento criado: {ev.get('summary','(sem título)')}", "link": ev.get('htmlLink','')}
    except Exception as e:
        logger.exception("Erro registrar_evento_calendar: %s", e)
        return {"status":"erro","mensagem": str(e)}

# Map de funções
FUNCTION_MAP = {
    "atualizar_saldo": atualizar_saldo,
    "obter_saldo": obter_saldo,
    "registrar_evento": registrar_evento_calendar,
    "registrar_movimentacao": registrar_movimentacao,
}

# ---------------------------
# Gemini (2.5 Flash) setup
# ---------------------------
genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "Você é o 'ESTOQUE BOT', um assistente amigável para gerenciar estoque de bebidas. "
    "Compreende linguagem natural, pode registrar compras, vendas, consultar saldos, registrar movimentações "
    "e agendar eventos no calendário. Use as funções quando necessário e sempre responda de forma clara e curta."
)

# memória persistente por usuário (arquivos)
def caminho_memoria(user_id: int) -> str:
    return os.path.join(MEMORY_FOLDER, f"memory_{user_id}.json")

def carregar_memoria(user_id: int):
    path = caminho_memoria(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_memoria(user_id: int, mem_obj):
    path = caminho_memoria(user_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mem_obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("Erro salvar_memoria: %s", e)

# chats em runtime
conversas_usuarios = {}

def criar_chat_para_usuario(user_id: int):
    # cria um modelo generativo com declarações de funções
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[
            genai.types.FunctionDeclaration(
                name="atualizar_saldo",
                description="Atualiza o estoque e registra movimentação. Args: produto, quantidade, acao, responsavel, observacao",
                parameters={
                    "type":"object",
                    "properties":{
                        "produto":{"type":"string"},
                        "quantidade":{"type":"integer"},
                        "acao":{"type":"string"},
                        "responsavel":{"type":"string"},
                        "observacao":{"type":"string"}
                    },
                    "required":["produto","quantidade","acao"]
                }
            ),
            genai.types.FunctionDeclaration(
                name="obter_saldo",
                description="Consulta o saldo de um produto. Args: produto",
                parameters={
                    "type":"object",
                    "properties":{"produto":{"type":"string"}},
                    "required":["produto"]
                }
            ),
            genai.types.FunctionDeclaration(
                name="registrar_evento",
                description="Agenda evento no calendário. Args: titulo, descricao, data (YYYY-MM-DD), hora (HH:MM), duracao_minutos (opcional)",
                parameters={
                    "type":"object",
                    "properties":{
                        "titulo":{"type":"string"},
                        "descricao":{"type":"string"},
                        "data":{"type":"string"},
                        "hora":{"type":"string"},
                        "duracao_minutos":{"type":"integer"}
                    },
                    "required":["titulo","data","hora"]
                }
            ),
            genai.types.FunctionDeclaration(
                name="registrar_movimentacao",
                description="Registra movimentação manual. Args: produto, quantidade, tipo, responsavel, observacao",
                parameters={
                    "type":"object",
                    "properties":{
                        "produto":{"type":"string"},
                        "quantidade":{"type":"integer"},
                        "tipo":{"type":"string"},
                        "responsavel":{"type":"string"},
                        "observacao":{"type":"string"}
                    },
                    "required":["produto","quantidade","tipo"]
                }
            )
        ]
    )
    # start_chat retorna um objeto de chat que podemos usar .send_message()
    chat = model.start_chat(history=[])
    # injeta memória inicial se houver
    mem = carregar_memoria(user_id)
    if mem and isinstance(mem, dict):
        summary = mem.get("summary")
        if summary:
            try:
                chat.send_message(f"[MEMÓRIA] {summary}")
            except:
                pass
    conversas_usuarios[user_id] = chat
    return chat

def obter_chat_usuario(user_id: int):
    if user_id in conversas_usuarios:
        return conversas_usuarios[user_id]
    return criar_chat_para_usuario(user_id)

# ---------------------------
# Telegram helpers
# ---------------------------
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def enviar_mensagem_telegram(chat_id: int, texto: str):
    try:
        payload = {"chat_id": chat_id, "text": texto}
        r = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=10)
        logger.info("📤 Resposta Telegram: %s -> %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("Erro enviar_mensagem_telegram: %s", e)

# ---------------------------
# Flask webhook
# ---------------------------
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "🤖 Assistente de Estoque IA (Render) - ativo", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        logger.info("🟢 RAW UPDATE RECEBIDO: %s", update)

        if not update:
            return "no data", 200

        # extrai a mensagem (variações)
        message = update.get("message") or update.get("edited_message") or update.get("channel_post")
        if not message:
            logger.warning("Sem campo message no update.")
            return "no message", 200

        user_text = message.get("text", "") or ""
        user_id = update.get("message", {}).get("from", {}).get("id") or message.get("from", {}).get("id")
        user_first = message.get("from", {}).get("first_name", "")

        logger.info("🗣️ [%s | %s] %s", user_first, user_id, user_text)

        # atualiza memória inicial (simples)
        mem = carregar_memoria(user_id) or {}
        recent = mem.get("recent_messages", [])
        recent.append({"at": datetime.datetime.now().isoformat(), "text": user_text})
        mem["recent_messages"] = recent[-50:]
        mem["summary"] = f"Última: {recent[-1]['text']}" if recent else ""
        salvar_memoria(user_id, mem)

        # obtém (ou cria) chat do Gemini para o usuário
        chat = obter_chat_usuario(user_id)

        # envia mensagem ao Gemini (chat)
        logger.info("✉️ Enviando para Gemini...")
        response = chat.send_message(user_text)
        logger.info("💬 Gemini respondeu (raw).")

        final_reply = None

        # extrair candidates/parts
        try:
            candidates = getattr(response, "candidates", None)
            if candidates and len(candidates) > 0:
                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None)
                if parts:
                    for part in parts:
                        # se function_call
                        if getattr(part, "function_call", None):
                            fc = part.function_call
                            fname = fc.name
                            # args podem vir como dict ou string
                            args = fc.args
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except:
                                    # tenta extrair substring válido
                                    try:
                                        args = json.loads(args.strip().strip("'").strip('"'))
                                    except:
                                        args = {}
                            if not isinstance(args, dict):
                                args = dict(args) if args else {}

                            logger.info("⚙️ Gemini solicitou função: %s | args: %s", fname, args)

                            if fname in FUNCTION_MAP:
                                # converter tipos básicos
                                safe_args = {}
                                for k, v in (args.items() if isinstance(args, dict) else []):
                                    if isinstance(k, str) and k.lower() in ["quantidade","duracao_minutos","quantity","amount"]:
                                        try:
                                            safe_args[k] = int(float(v))
                                        except:
                                            safe_args[k] = v
                                    else:
                                        safe_args[k] = v

                                try:
                                    result = FUNCTION_MAP[fname](**safe_args)
                                except TypeError:
                                    try:
                                        result = FUNCTION_MAP[fname](**{k:v for k,v in safe_args.items()})
                                    except Exception as e:
                                        logger.exception("Erro calling function %s: %s", fname, e)
                                        result = {"status":"erro","mensagem":str(e)}
                                logger.info("📊 Resultado da função: %s", result)

                                # enviar resultado de volta ao modelo para formular resposta natural
                                followup_msg = f"Resultado da função {fname}: {result}"
                                followup = chat.send_message(followup_msg)

                                # tentar extrair resposta amigável do followup
                                text_candidate = None
                                try:
                                    text_candidate = getattr(followup, "text", None)
                                except:
                                    text_candidate = None
                                if not text_candidate:
                                    try:
                                        cand2 = getattr(followup, "candidates", None)
                                        if cand2 and len(cand2) > 0:
                                            ccontent = getattr(cand2[0], "content", None)
                                            parts2 = getattr(ccontent, "parts", None)
                                            if parts2:
                                                for p2 in parts2:
                                                    if getattr(p2, "text", None):
                                                        text_candidate = p2.text
                                                        break
                                    except Exception:
                                        text_candidate = None

                                if text_candidate:
                                    final_reply = text_candidate
                                else:
                                    if isinstance(result, dict):
                                        final_reply = result.get("mensagem") or result.get("message") or str(result)
                                    else:
                                        final_reply = str(result)
                            else:
                                final_reply = f"⚠️ O sistema tentou usar a função '{fname}', que não está implementada."
                        else:
                            # parte de texto
                            if getattr(part, "text", None):
                                final_reply = part.text

        except Exception as e:
            logger.exception("Erro processando resposta Gemini: %s", e)

        # fallback final
        if not final_reply:
            try:
                final_reply = getattr(response, "text", None)
            except:
                final_reply = None
        if not final_reply:
            final_reply = "Desculpa, não consegui processar sua solicitação. Tenta reformular?"

        # salvar memória adicional
        mem = carregar_memoria(user_id) or {}
        recent = mem.get("recent_messages", [])
        mem["last_reply"] = final_reply
        mem["recent_messages"] = recent[-50:]
        mem["summary"] = f"Última interação: {final_reply[:200]}"
        salvar_memoria(user_id, mem)

        # responder no Telegram
        enviar_mensagem_telegram(user_id, final_reply)
        logger.info("✅ Resposta enviada ao usuário %s", user_id)

    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("❌ Erro no webhook handler: %s\n%s", e, tb)
    return jsonify(ok=True), 200

# ---------------------------
# Run (local dev)
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info("🚀 Assistente de Estoque IA rodando na porta %s", port)
    # debug True apenas em dev; Render usará gunicorn no deploy
    app.run(host="0.0.0.0", port=port, debug=True)

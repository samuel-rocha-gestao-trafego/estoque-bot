# ============================================================
# 🤖 Assistente de Estoque IA v2.4 - Estrutura Segura para Render (Worker)
# Gemini 2.5 Flash + Telegram + Google Sheets + Google Calendar
# ============================================================

# Bibliotecas (remova o !pip install)
import os
import json
import datetime
import traceback
import nest_asyncio
import asyncio
from typing import Any, Dict

# Importações de terceiros
import gspread
# MUDANÇA CRUCIAL: Trocamos oauth2client por google.oauth2 (a biblioteca moderna)
from google.oauth2 import service_account 
from googleapiclient.discovery import build
import google.generativeai as genai

# Importações do Telegram (Assíncronas)
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# 🔒 CONFIGURAÇÃO - LENDO VARIÁVEIS DE AMBIENTE (RENDER)
# =========================

# Variáveis sensíveis e IDs
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOME_PLANILHA = os.getenv("NOME_PLANILHA", "EstoqueDepositoBebidas") # Default para evitar erro
CALENDAR_ID = os.getenv("CALENDAR_ID")

# O segredo: Lendo o JSON de credenciais diretamente como uma string
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Paths internos
ABA_ESTOQUE = "Estoque"
ABA_MOV = "Movimentacoes"
MEMORY_FOLDER = "/tmp/memory_users" # Usamos /tmp no Render para armazenamento efêmero e temporário

# 1. Checa se as variáveis críticas estão definidas
if not all([TOKEN_TELEGRAM, GEMINI_API_KEY, GOOGLE_CREDENTIALS_JSON, CALENDAR_ID]):
    # Corrigido GOOGLE_CREDENTIALS para GOOGLE_CREDENTIALS_JSON
    raise ValueError("❌ ERRO DE CONFIGURAÇÃO: Verifique as variáveis de ambiente (TELEGRAM_TOKEN, GEMINI_API_KEY, CALENDAR_ID, GOOGLE_CREDENTIALS_JSON) no Render.")

os.makedirs(MEMORY_FOLDER, exist_ok=True)

# =========================
# 🔑 Conexão Google (Sheets + Calendar) - SEM ARQUIVO
# =========================
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar.events'
]

try:
    # Transforma a string JSON em um objeto Python
    creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    
    # --- MUDANÇA CRUCIAL: USANDO service_account.Credentials ---
    # Cria o objeto de credenciais usando a biblioteca google-auth moderna
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    
    # gspread ainda pode ser autorizado com o objeto de credenciais moderno
    gc = gspread.authorize(creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    print("✅ Conectado ao Google (Sheets + Calendar) via Variavel de Ambiente.")
except Exception as e:
    print(f"❌ Erro ao conectar ao Google. Verifique a variável GOOGLE_CREDENTIALS_JSON: {e}")
    # Esta linha deve ser mantida para que o Render encerre a implantação em caso de erro
    raise 

def abrir_aba(nome_aba: str):
    """Abre a aba (Worksheet) e lança erro informativo se não existir."""
    try:
        sh = gc.open(NOME_PLANILHA)
    except Exception as e:
        # Se NOME_PLANILHA estiver errado ou credencial não tiver acesso
        raise RuntimeError(f"Não foi possível abrir a planilha '{NOME_PLANILHA}'. Verifique o nome e as permissões: {e}")
    try:
        ws = sh.worksheet(nome_aba)
    except gspread.WorksheetNotFound:
        raise RuntimeError(f"Aba '{nome_aba}' não encontrada. Crie manualmente: {ABA_ESTOQUE} e {ABA_MOV}.")
    return ws

# =========================================================================
# 🧩 Funções de negócio (Sheets + Calendar) - Lógica de Estoque e Agenda
# =========================================================================

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
        return {"status":"vazio","mensagem":f"O produto '{produto}' não foi encontrado no estoque."}
    except Exception as e:
        return {"status":"erro","mensagem": str(e)}

def registrar_movimentacao(produto: str, quantidade: int, tipo: str, responsavel: str="", observacao: str="") -> Dict[str, Any]:
    try:
        ws = abrir_aba(ABA_MOV)
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = [agora, produto, quantidade, tipo, responsavel or "", observacao or ""]
        ws.append_row(linha)
        return {"status":"sucesso","mensagem":"Movimentação registrada","linha":linha}
    except Exception as e:
        return {"status":"erro","mensagem":str(e)}

def atualizar_saldo(produto: str, quantidade: int, acao: str, responsavel: str="", observacao: str="") -> Dict[str, Any]:
    """
    acao: 'COMPRA' / 'ENTRADA' / 'VENDA' / 'SAIDA' / 'AJUSTE'
    """
    try:
        ws = abrir_aba(ABA_ESTOQUE)
        rows = ws.get_all_records()
        produto_norm = produto.strip()
        encontrado = False
        for idx, r in enumerate(rows, start=2):  # linha 2 em diante
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
                    # ajuste: quantidade pode ser positiva/negativa
                    novo = atual + int(quantidade)
                    tipo_mov = acao.capitalize()
                ws.update_cell(idx, 2, novo)
                ws.update_cell(idx, 3, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                mv = registrar_movimentacao(nome, int(quantidade), tipo_mov, responsavel, observacao)
                return {"status":"sucesso","produto":nome,"quantidade":int(quantidade),"novo_saldo":novo,"movimentacao":mv}
        # não encontrado -> adicionar novo
        if not encontrado:
            tipo_mov = "Entrada" if str(acao).strip().upper() in ["COMPRA","ENTRADA"] else acao
            ws.append_row([produto_norm, int(quantidade), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            mv = registrar_movimentacao(produto_norm, int(quantidade), tipo_mov, responsavel, observacao)
            return {"status":"sucesso","produto":produto_norm,"quantidade":int(quantidade),"novo_saldo":int(quantidade),"movimentacao":mv,"mensagem":f"Produto '{produto_norm}' novo adicionado ao estoque."}
    except Exception as e:
        return {"status":"erro","mensagem":str(e)}

def registrar_evento_calendar(titulo: str, descricao: str, data: str, hora: str, duracao_minutos: int = 60) -> Dict[str, Any]:
    """
    data: 'YYYY-MM-DD'
    hora: 'HH:MM' (24h)
    """
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
        return {"status":"sucesso", "mensagem": f"Evento criado no calendário: {ev.get('summary','(sem título)')}", "link": ev.get('htmlLink','')}
    except Exception as e:
        return {"status":"erro","mensagem": str(e)}

# =========================
# Map de funções e Configuração Gemini
# =========================
FUNCTION_MAP = {
    "atualizar_saldo": atualizar_saldo,
    "obter_saldo": obter_saldo,
    "registrar_evento": registrar_evento_calendar,
    "registrar_movimentacao": registrar_movimentacao
}

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "Você é o 'ESTOQUE BOT', um assistente amigável para gerenciar estoque de bebidas. "
    "Compreende linguagem natural, pode registrar compras, vendas, consultar saldos, registrar movimentações "
    "e agendar eventos no calendário. Use as funções quando necessário e sempre responda de forma clara e curta."
)

# Funções de Memória (para contexto persistente)
def caminho_memoria(user_id: int) -> str:
    return os.path.join(MEMORY_FOLDER, f"memory_{user_id}.json")

def carregar_memoria(user_id: int):
    path = caminho_memoria(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_memoria(user_id: int, mem_obj):
    path = caminho_memoria(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mem_obj, f, ensure_ascii=False, indent=2)

conversas_usuarios = {}

def criar_chat_para_usuario(user_id: int):
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
    chat = model.start_chat(history=[])
    # injetar memória persistente (se houver) como mensagem inicial para contexto
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

# =========================
# Handler Telegram (Lógica Function Calling)
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or ""
    print(f"\n🗣️ [{user_name} | {user_id}] {user_text}")

    # Atualiza memória simples
    mem = carregar_memoria(user_id) or {}
    recent = mem.get("recent_messages", [])
    recent.append({"at": datetime.datetime.now().isoformat(), "text": user_text})
    mem["recent_messages"] = recent[-50:]
    mem["summary"] = f"Última: {recent[-1]['text']}" if recent else ""
    salvar_memoria(user_id, mem)

    chat = obter_chat_usuario(user_id)

    try:
        response = chat.send_message(user_text)
        final_reply = None

        if response.candidates and response.candidates[0].content and getattr(response.candidates[0].content, "parts", None):
            parts = response.candidates[0].content.parts
            for part in parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    fname = fc.name
                    args = dict(fc.args) if fc.args else {}
                    print(f"⚙️ Gemini solicitou função: {fname} | args: {args}")

                    if fname in FUNCTION_MAP:
                        safe_args = {}
                        for k,v in args.items():
                            if k.lower() in ["quantidade","duracao_minutos","quantity","amount"]:
                                try:
                                    safe_args[k] = int(float(v))
                                except:
                                    safe_args[k] = v
                            else:
                                safe_args[k] = v
                        try:
                            if 'responsavel' in FUNCTION_MAP[fname].__annotations__ and 'responsavel' not in safe_args:
                                safe_args['responsavel'] = user_name

                            result = FUNCTION_MAP[fname](**safe_args)
                        except TypeError as te:
                            try:
                                result = FUNCTION_MAP[fname](**{k:v for k,v in safe_args.items()})
                            except Exception as e:
                                result = {"status":"erro","mensagem":f"Erro ao executar função: {e}"}
                        
                        print("📊 Resultado da função:", result)
                        followup_msg = f"Resultado da função {fname}: {result}"
                        followup = chat.send_message(followup_msg)
                        
                        text_candidate = getattr(followup, "text", None)
                        if not text_candidate:
                             try:
                                 if followup.candidates and followup.candidates[0].content and getattr(followup.candidates[0].content, "parts", None):
                                     for p2 in followup.candidates[0].content.parts:
                                         if getattr(p2, "text", None):
                                             text_candidate = p2.text
                                             break
                             except Exception:
                                 pass
                                 
                        if text_candidate:
                            final_reply = text_candidate
                        else:
                            if isinstance(result, dict):
                                final_reply = result.get("mensagem") or result.get("message") or str(result)
                            else:
                                final_reply = str(result)
                    else:
                        final_reply = f"⚠️ O sistema tentou usar a função '{fname}', mas ela não está implementada no bot."
                else:
                    if getattr(part, "text", None):
                        final_reply = part.text

        if not final_reply:
            try:
                final_reply = getattr(response, "text", None)
            except:
                final_reply = "Desculpa, não consegui processar sua solicitação. Tenta reformular?"

        mem = carregar_memoria(user_id) or {}
        mem["last_reply"] = final_reply
        mem["summary"] = f"Última interação: {final_reply[:200]}"
        salvar_memoria(user_id, mem)

        await update.message.reply_text(final_reply)
        print("✅ Resposta enviada.")
    except Exception as e:
        tb = traceback.format_exc()
        print("❌ Erro no handler:", e, tb)
        await update.message.reply_text("⚠️ Ocorreu um erro interno. Veja logs no console.")


# =========================
# 🚀 Inicialização do Worker (Polling)
# =========================
nest_asyncio.apply()

async def main():
    # Inicializa o bot com o token lido da variável de ambiente
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
    # Adiciona o handler para todas as mensagens de texto que não são comandos
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("🤖 Assistente de Estoque IA v2.4 rodando como Worker (Polling).")
    # O Polling mantém a conexão aberta, ideal para Workers de background
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Erro ao iniciar:", e)

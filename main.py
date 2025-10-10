# =========================
# Assistente de Estoque IA v2.2 - Render Edition
# Gemini 2.5 Flash + Telegram + Google Sheets + Google Calendar
# Compatível com Python 3.13 (Render)
# =========================

import os
import json
import datetime
import traceback
import asyncio
from typing import Any, Dict

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import google.generativeai as genai

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIGURAÇÕES
# =========================
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID")
NOME_PLANILHA = os.getenv("NOME_PLANILHA", "EstoqueDepositoBebidas")
ABA_ESTOQUE = os.getenv("ABA_ESTOQUE", "Estoque")
ABA_MOV = os.getenv("ABA_MOV", "Movimentacoes")
MEMORY_FOLDER = "memory_users"

os.makedirs(MEMORY_FOLDER, exist_ok=True)

# Credenciais Google (em variável de ambiente JSON)
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
if not GOOGLE_CREDENTIALS:
    raise ValueError("❌ Variável de ambiente GOOGLE_CREDENTIALS não encontrada!")

creds_dict = json.loads(GOOGLE_CREDENTIALS)
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar.events'
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
gc = gspread.authorize(creds)
calendar_service = build('calendar', 'v3', credentials=creds)
print("✅ Conectado ao Google (Planilhas + Calendário)")

# =========================
# Funções de Sheets e Calendar
# =========================
def abrir_aba(nome_aba: str):
    try:
        sh = gc.open(NOME_PLANILHA)
        return sh.worksheet(nome_aba)
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir aba '{nome_aba}': {e}")

def obter_saldo(produto: str) -> Dict[str, Any]:
    try:
        ws = abrir_aba(ABA_ESTOQUE)
        rows = ws.get_all_records()
        for r in rows:
            nome = str(r.get("Produto", "")).strip()
            if produto.strip().lower() in nome.lower():
                qtd = int(r.get("Quantidade", 0) or 0)
                return {"status": "sucesso", "produto": nome, "quantidade": qtd}
        return {"status": "vazio", "mensagem": f"{produto} não encontrado."}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

def registrar_movimentacao(produto: str, quantidade: int, tipo: str, responsavel: str="", observacao: str=""):
    try:
        ws = abrir_aba(ABA_MOV)
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([agora, produto, quantidade, tipo, responsavel, observacao])
        return {"status": "sucesso", "mensagem": "Movimentação registrada"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

def atualizar_saldo(produto: str, quantidade: int, acao: str, responsavel: str="", observacao: str=""):
    try:
        ws = abrir_aba(ABA_ESTOQUE)
        rows = ws.get_all_records()
        produto_norm = produto.strip()
        encontrado = False
        for idx, r in enumerate(rows, start=2):
            nome = str(r.get("Produto", "")).strip()
            if produto_norm.lower() in nome.lower():
                encontrado = True
                atual = int(r.get("Quantidade", 0) or 0)
                act_upper = acao.strip().upper()
                if act_upper in ["COMPRA", "ENTRADA", "IN", "+"]:
                    novo = atual + int(quantidade)
                    tipo_mov = "Entrada"
                elif act_upper in ["VENDA", "SAIDA", "OUT", "-"]:
                    novo = atual - int(quantidade)
                    tipo_mov = "Saída"
                else:
                    novo = atual + int(quantidade)
                    tipo_mov = acao.capitalize()
                ws.update_cell(idx, 2, novo)
                ws.update_cell(idx, 3, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                registrar_movimentacao(nome, quantidade, tipo_mov, responsavel, observacao)
                return {"status": "sucesso", "produto": nome, "novo_saldo": novo}
        if not encontrado:
            ws.append_row([produto_norm, quantidade, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            registrar_movimentacao(produto_norm, quantidade, acao, responsavel, observacao)
            return {"status": "sucesso", "mensagem": "Produto novo adicionado"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

def registrar_evento_calendar(titulo, descricao, data, hora, duracao_minutos=60):
    try:
        dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        inicio = dt.isoformat()
        fim = (dt + datetime.timedelta(minutes=duracao_minutos)).isoformat()
        evento = {
            'summary': titulo,
            'description': descricao,
            'start': {'dateTime': inicio, 'timeZone': 'America/Sao_Paulo'},
            'end': {'dateTime': fim, 'timeZone': 'America/Sao_Paulo'},
        }
        ev = calendar_service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
        return {"status": "sucesso", "mensagem": f"Evento criado: {ev.get('summary')}"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

FUNCTION_MAP = {
    "atualizar_saldo": atualizar_saldo,
    "obter_saldo": obter_saldo,
    "registrar_evento": registrar_evento_calendar,
    "registrar_movimentacao": registrar_movimentacao
}

# =========================
# Configura Gemini
# =========================
genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "Você é o 'ESTOQUE BOT', um assistente para gerenciar estoque de bebidas. "
    "Pode registrar compras, vendas, consultar saldos e agendar eventos."
)

def caminho_memoria(uid): return os.path.join(MEMORY_FOLDER, f"memory_{uid}.json")
def carregar_memoria(uid):
    try:
        if os.path.exists(caminho_memoria(uid)):
            return json.load(open(caminho_memoria(uid), "r", encoding="utf-8"))
    except: pass
    return {}
def salvar_memoria(uid, data):
    with open(caminho_memoria(uid), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

conversas_usuarios = {}

def criar_chat(uid):
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
    )
    chat = model.start_chat(history=[])
    mem = carregar_memoria(uid)
    if "summary" in mem:
        chat.send_message(f"[MEMÓRIA] {mem['summary']}")
    conversas_usuarios[uid] = chat
    return chat

def obter_chat(uid):
    return conversas_usuarios.get(uid) or criar_chat(uid)

# =========================
# Handler Telegram
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    uid = update.effective_user.id
    uname = update.effective_user.first_name
    print(f"🗣️ [{uname} | {uid}] {user_text}")

    mem = carregar_memoria(uid)
    mem["summary"] = user_text
    salvar_memoria(uid, mem)

    chat = obter_chat(uid)
    try:
        resp = chat.send_message(user_text)
        reply = getattr(resp, "text", None)
        if not reply and resp.candidates:
            reply = resp.candidates[0].content.parts[0].text
        await update.message.reply_text(reply or "Não consegui entender isso ainda.")
        print("✅ Resposta enviada.")
    except Exception as e:
        print("❌ Erro:", e)
        await update.message.reply_text("Erro interno ao processar.")

# =========================
# Inicialização Render
# =========================
import nest_asyncio
nest_asyncio.apply()

async def main():
    print("🚀 Inicializando bot...")
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("🤖 Assistente de Estoque IA v2.2 rodando. Fale com o bot no Telegram.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except Exception as e:
        print("❌ Erro ao iniciar:", e)

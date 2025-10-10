# =========================
# Assistente de Estoque IA v2.3 - versão Render
# Gemini 2.5 Flash + Telegram + Google Sheets + Google Calendar
# =========================

import os
import json
import datetime
import traceback
import nest_asyncio
import asyncio
from typing import Any, Dict

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import google.generativeai as genai

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIGURAÇÕES VIA ENV
# =========================
TOKEN_TELEGRAM = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CALENDAR_ID = os.environ.get("CALENDAR_ID")
NOME_PLANILHA = "EstoqueDepositoBebidas"
ABA_ESTOQUE = "Estoque"
ABA_MOV = "Movimentacoes"

MEMORY_FOLDER = "./memory_users"  # pasta persistente
os.makedirs(MEMORY_FOLDER, exist_ok=True)

# =========================
# Conexão Google (Sheets + Calendar) via ENV
# =========================
creds_json = os.environ.get("GOOGLE_CREDENTIALS")
if not creds_json:
    raise RuntimeError("⚠️ Variável GOOGLE_CREDENTIALS não encontrada!")

creds_dict = json.loads(creds_json)
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar.events'
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
gc = gspread.authorize(creds)
calendar_service = build('calendar', 'v3', credentials=creds)

print("✅ Conectado ao Google (Sheets + Calendar)")

# =========================
# Funções auxiliares
# =========================
def abrir_aba(nome_aba: str):
    try:
        sh = gc.open(NOME_PLANILHA)
        ws = sh.worksheet(nome_aba)
        return ws
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir aba '{nome_aba}': {e}")

def obter_saldo(produto: str) -> Dict[str, Any]:
    ws = abrir_aba(ABA_ESTOQUE)
    rows = ws.get_all_records()
    for r in rows:
        nome = str(r.get("Produto","")).strip()
        if produto.strip().lower() in nome.lower():
            return {"status":"sucesso","produto":nome,"quantidade":int(r.get("Quantidade",0))}
    return {"status":"vazio","mensagem":f"{produto} não encontrado."}

def registrar_movimentacao(produto: str, quantidade: int, tipo: str, responsavel: str="", observacao: str="") -> Dict[str, Any]:
    ws = abrir_aba(ABA_MOV)
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = [agora, produto, quantidade, tipo, responsavel or "", observacao or ""]
    ws.append_row(linha)
    return {"status":"sucesso","mensagem":"Movimentação registrada","linha":linha}

def atualizar_saldo(produto: str, quantidade: int, acao: str, responsavel: str="", observacao: str="") -> Dict[str, Any]:
    ws = abrir_aba(ABA_ESTOQUE)
    rows = ws.get_all_records()
    produto_norm = produto.strip()
    for idx, r in enumerate(rows, start=2):
        nome = str(r.get("Produto","")).strip()
        if produto_norm.lower() in nome.lower():
            atual = int(r.get("Quantidade",0))
            novo = atual + int(quantidade) if acao.upper() in ["COMPRA","ENTRADA","IN","+"] else atual - int(quantidade)
            ws.update_cell(idx, 2, novo)
            ws.update_cell(idx, 3, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            registrar_movimentacao(nome, quantidade, acao, responsavel, observacao)
            return {"status":"sucesso","produto":nome,"novo_saldo":novo}
    # se não encontrou, adiciona
    ws.append_row([produto_norm, quantidade, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    registrar_movimentacao(produto_norm, quantidade, acao, responsavel, observacao)
    return {"status":"sucesso","produto":produto_norm,"novo_saldo":quantidade,"mensagem":"Produto novo adicionado"}

def registrar_evento_calendar(titulo: str, descricao: str, data: str, hora: str, duracao_minutos: int = 60):
    dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    evento = {
        'summary': titulo,
        'description': descricao or "",
        'start': {'dateTime': dt.isoformat(), 'timeZone': 'America/Sao_Paulo'},
        'end': {'dateTime': (dt+datetime.timedelta(minutes=duracao_minutos)).isoformat(), 'timeZone': 'America/Sao_Paulo'},
    }
    ev = calendar_service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
    return {"status":"sucesso","mensagem":f"Evento criado: {ev.get('summary')}"}

FUNCTION_MAP = {
    "atualizar_saldo": atualizar_saldo,
    "obter_saldo": obter_saldo,
    "registrar_evento": registrar_evento_calendar,
    "registrar_movimentacao": registrar_movimentacao
}

# =========================
# Gemini Config
# =========================
genai.configure(api_key=GEMINI_API_KEY)
SYSTEM_INSTRUCTION = "Você é o ESTOQUE BOT..."

from google.generativeai.types import FunctionDeclaration

def criar_chat():
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[]
    )
    return model.start_chat(history=[])

chat = criar_chat()

# =========================
# Telegram Handler
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"🗣️ {update.effective_user.first_name}: {user_text}")
    try:
        response = chat.send_message(user_text)
        reply = getattr(response, "text", None) or "Não consegui entender."
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text("⚠️ Erro interno.")
        print("Erro:", traceback.format_exc())

# =========================
# Main
# =========================
nest_asyncio.apply()
async def main():
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("🤖 Bot rodando...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

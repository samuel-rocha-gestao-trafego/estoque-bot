# ======================================================
# Assistente de Estoque IA v3.0
# Gemini 2.5 Flash + Telegram + Google Sheets + Calendar
# Compatível com Render (asyncio + nest_asyncio)
# ======================================================

import os
import json
import datetime
import asyncio
import traceback
import nest_asyncio
from typing import Any, Dict

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# =========================
# VERIFICA VARIÁVEIS DE AMBIENTE
# =========================
print("🔍 Verificando variáveis de ambiente...")

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
NOME_PLANILHA = os.getenv("NOME_PLANILHA", "EstoqueDepositoBebidas")
ABA_ESTOQUE = os.getenv("ABA_ESTOQUE", "Estoque")
ABA_MOV = os.getenv("ABA_MOV", "Movimentacoes")
CALENDAR_ID = os.getenv("CALENDAR_ID", "")

if not TOKEN_TELEGRAM:
    print("⚠️ TOKEN_TELEGRAM não foi encontrado no ambiente! Usando fallback local (para teste).")

if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY não encontrado!")

if not GOOGLE_CREDENTIALS:
    raise RuntimeError("❌ GOOGLE_CREDENTIALS não encontrado!")

print("✅ GEMINI_API_KEY carregado.")
print("✅ GOOGLE_CREDENTIALS carregado (conteúdo omitido por segurança).")

# =========================
# CONEXÃO GOOGLE (Sheets + Calendar)
# =========================
try:
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/calendar.events"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    raise RuntimeError(f"❌ Erro ao conectar ao Google: {e}")

# =========================
# FUNÇÕES DO GOOGLE SHEETS
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
        if produto.lower() in str(r.get("Produto", "")).lower():
            qtd = int(r.get("Quantidade", 0))
            return {"status": "sucesso", "produto": r.get("Produto"), "quantidade": qtd}
    return {"status": "erro", "mensagem": f"Produto '{produto}' não encontrado."}

def registrar_movimentacao(produto, quantidade, tipo, responsavel="", observacao=""):
    ws = abrir_aba(ABA_MOV)
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([agora, produto, quantidade, tipo, responsavel, observacao])
    return {"status": "sucesso", "mensagem": "Movimentação registrada"}

def atualizar_saldo(produto, quantidade, acao, responsavel="", observacao=""):
    ws = abrir_aba(ABA_ESTOQUE)
    rows = ws.get_all_records()
    produto = produto.strip()
    for i, r in enumerate(rows, start=2):
        if produto.lower() in str(r.get("Produto", "")).lower():
            atual = int(r.get("Quantidade", 0))
            if acao.lower() in ["compra", "entrada", "in"]:
                novo = atual + quantidade
                tipo = "Entrada"
            elif acao.lower() in ["venda", "saida", "out"]:
                novo = atual - quantidade
                tipo = "Saída"
            else:
                novo = atual + quantidade
                tipo = acao
            ws.update_cell(i, 2, novo)
            registrar_movimentacao(produto, quantidade, tipo, responsavel, observacao)
            return {"status": "sucesso", "novo_saldo": novo}
    ws.append_row([produto, quantidade, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    registrar_movimentacao(produto, quantidade, acao, responsavel, observacao)
    return {"status": "sucesso", "mensagem": "Produto adicionado."}

def registrar_evento_calendar(titulo, descricao, data, hora, duracao_minutos=60):
    try:
        dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        inicio = dt.isoformat()
        fim = (dt + datetime.timedelta(minutes=duracao_minutos)).isoformat()
        evento = {
            "summary": titulo,
            "description": descricao,
            "start": {"dateTime": inicio, "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": fim, "timeZone": "America/Sao_Paulo"},
        }
        ev = calendar_service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
        return {"status": "sucesso", "mensagem": f"Evento criado: {ev.get('summary')}"}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

# =========================
# CONFIGURAÇÃO GEMINI
# =========================
genai.configure(api_key=GEMINI_API_KEY)
print("✅ Gemini configurado com sucesso.")

SYSTEM_INSTRUCTION = (
    "Você é o 'ESTOQUE BOT', um assistente de controle de estoque integrado ao Google Sheets e Calendar. "
    "Pode registrar compras, vendas, consultar saldo e agendar eventos."
)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION,
)

# =========================
# HANDLER TELEGRAM
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        texto = update.message.text
        user = update.effective_user.first_name
        print(f"💬 [{user}] {texto}")
        response = model.generate_content(texto)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")
        print("❌ Erro no handler:", e)

# =========================
# MAIN
# =========================
async def main():
    print("🚀 Inicializando bot...")
    app = Application.builder().token(TOKEN_TELEGRAM).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    await app.run_polling()
    print("✅ Bot rodando...")

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except Exception as e:
        print(f"❌ Erro ao iniciar o bot: {e}")

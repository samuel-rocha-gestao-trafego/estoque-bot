import os
import json
import datetime
import traceback
import asyncio
import nest_asyncio
from typing import Any, Dict

import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIGURAÇÕES
# =========================
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

NOME_PLANILHA = os.getenv("NOME_PLANILHA", "EstoqueDepositoBebidas")
ABA_ESTOQUE = os.getenv("ABA_ESTOQUE", "Estoque")
ABA_MOV = os.getenv("ABA_MOV", "Movimentacoes")
CALENDAR_ID = os.getenv("CALENDAR_ID")

MEMORY_FOLDER = "memory_users"
os.makedirs(MEMORY_FOLDER, exist_ok=True)

# =========================
# Conexão Google (Sheets + Calendar)
# =========================
SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar.events'
]

if not GOOGLE_CREDENTIALS:
    raise RuntimeError("⚠️ Variável GOOGLE_CREDENTIALS não encontrada!")

try:
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    calendar_service = build('calendar', 'v3', credentials=credentials)
    print("✅ Conectado ao Google (Sheets + Calendar)")
except Exception as e:
    print("❌ Erro ao conectar ao Google:", e)
    raise

# =========================
# Funções de negócio (Sheets + Calendar)
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
            nome = str(r.get("Produto","")).strip()
            if produto.lower() in nome.lower():
                qtd = int(r.get("Quantidade", 0))
                return {"status":"sucesso","produto":nome,"quantidade":qtd}
        return {"status":"vazio","mensagem":f"{produto} não encontrado."}
    except Exception as e:
        return {"status":"erro","mensagem":str(e)}

def registrar_movimentacao(produto, quantidade, tipo, responsavel="", observacao=""):
    try:
        ws = abrir_aba(ABA_MOV)
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = [agora, produto, quantidade, tipo, responsavel, observacao]
        ws.append_row(linha)
        return {"status":"sucesso","mensagem":"Movimentação registrada","linha":linha}
    except Exception as e:
        return {"status":"erro","mensagem":str(e)}

def atualizar_saldo(produto, quantidade, acao, responsavel="", observacao=""):
    try:
        ws = abrir_aba(ABA_ESTOQUE)
        rows = ws.get_all_records()
        produto_norm = produto.strip()
        for idx, r in enumerate(rows, start=2):
            nome = str(r.get("Produto","")).strip()
            if produto_norm.lower() in nome.lower():
                atual = int(r.get("Quantidade",0))
                if acao.upper() in ["COMPRA","ENTRADA","+"]:
                    novo = atual + int(quantidade)
                    tipo_mov = "Entrada"
                elif acao.upper() in ["VENDA","SAIDA","-"]:
                    novo = atual - int(quantidade)
                    tipo_mov = "Saída"
                else:
                    novo = atual + int(quantidade)
                    tipo_mov = acao
                ws.update_cell(idx, 2, novo)
                ws.update_cell(idx, 3, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                registrar_movimentacao(nome, quantidade, tipo_mov, responsavel, observacao)
                return {"status":"sucesso","produto":nome,"novo_saldo":novo}
        # Se não encontrou o produto
        ws.append_row([produto_norm, quantidade, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        registrar_movimentacao(produto_norm, quantidade, acao, responsavel, observacao)
        return {"status":"sucesso","mensagem":"Produto novo adicionado ao estoque"}
    except Exception as e:
        return {"status":"erro","mensagem":str(e)}

def registrar_evento_calendar(titulo, descricao, data, hora, duracao_minutos=60):
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
        return {"status":"sucesso","mensagem":f"Evento criado: {ev.get('summary')}"}
    except Exception as e:
        return {"status":"erro","mensagem":str(e)}

# =========================
# Map de funções
# =========================
FUNCTION_MAP = {
    "atualizar_saldo": atualizar_saldo,
    "obter_saldo": obter_saldo,
    "registrar_evento": registrar_evento_calendar,
    "registrar_movimentacao": registrar_movimentacao
}

# =========================
# Gemini + Telegram
# =========================
genai.configure(api_key=GEMINI_API_KEY)
SYSTEM_INSTRUCTION = (
    "Você é o 'ESTOQUE BOT', um assistente amigável para gerenciar estoque de bebidas. "
    "Pode registrar compras, vendas, consultar saldos e agendar eventos no calendário."
)

conversas_usuarios = {}

def obter_chat_usuario(user_id: int):
    if user_id in conversas_usuarios:
        return conversas_usuarios[user_id]
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_INSTRUCTION
    )
    chat = model.start_chat(history=[])
    conversas_usuarios[user_id] = chat
    return chat

# =========================
# Handler Telegram
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    print(f"\n🗣️ [{user_name}] {user_text}")

    chat = obter_chat_usuario(user_id)
    try:
        response = chat.send_message(user_text)
        reply = getattr(response, "text", None)
        if not reply:
            reply = "Desculpe, não consegui processar sua solicitação."
        await update.message.reply_text(reply)
        print("✅ Resposta enviada.")
    except Exception as e:
        tb = traceback.format_exc()
        print("❌ Erro no handler:", e, tb)
        await update.message.reply_text("Erro interno, veja logs.")

# =========================
# Start bot
# =========================
nest_asyncio.apply()

async def main():
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("🤖 Bot rodando no Render!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

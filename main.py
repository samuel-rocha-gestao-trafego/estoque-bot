# ================================================================
# ASSISTENTE DE ESTOQUE IA (Telegram + Gemini + Google Sheets)
# Versão compatível com python-telegram-bot 21.6
# ================================================================

import os
import json
import asyncio
import datetime
import gspread
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import nest_asyncio

nest_asyncio.apply()

# ================================================================
# 🔍 VERIFICAÇÃO DE VARIÁVEIS DE AMBIENTE
# ================================================================
print("🔍 Verificando variáveis de ambiente...")

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

if not TOKEN_TELEGRAM:
    raise RuntimeError("⚠️ Variável TOKEN_TELEGRAM não encontrada!")
if not GEMINI_API_KEY:
    raise RuntimeError("⚠️ Variável GEMINI_API_KEY não encontrada!")
if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("⚠️ Variável GOOGLE_CREDENTIALS não encontrada!")

print("✅ Todas as variáveis de ambiente foram carregadas.")

# ================================================================
# 🔐 AUTENTICAÇÃO GOOGLE (Sheets + Calendar)
# ================================================================
print("✅ Conectando ao Google (Planilhas + Calendário)...")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar"
]

creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDENTIALS_JSON), scopes=scopes)
gc = gspread.authorize(creds)

print("✅ Conectado ao Google (Planilhas + Calendário)")

# ================================================================
# 💡 CONFIGURAÇÃO GEMINI
# ================================================================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ================================================================
# 🤖 FUNÇÕES DO BOT TELEGRAM
# ================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá! 👋 Eu sou seu assistente de estoque IA. Envie uma mensagem para começar!")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    await update.message.reply_text("⏳ Processando com IA...")

    resposta = model.generate_content(f"O usuário disse: {texto_usuario}. Responda de forma breve e natural.")
    await update.message.reply_text(resposta.text or "Não consegui gerar uma resposta agora.")

# ================================================================
# 🚀 INICIALIZAÇÃO DO BOT
# ================================================================
async def main():
    print("🚀 Inicializando bot...")
    app = Application.builder().token(TOKEN_TELEGRAM).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 Bot em execução. Aguardando mensagens...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Erro ao iniciar: {e}")

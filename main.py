import os
import json
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Flask app
app = Flask(__name__)

# ======== CONFIGURAÇÕES ========
TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not TELEGRAM_TOKEN:
    raise RuntimeError("⚠️ Variável TOKEN_TELEGRAM não encontrada!")
if not GEMINI_API_KEY:
    raise RuntimeError("⚠️ Variável GEMINI_API_KEY não encontrada!")
if not GOOGLE_CREDENTIALS:
    raise RuntimeError("⚠️ Variável GOOGLE_CREDENTIALS não encontrada!")

# ======== GOOGLE AUTH ========
try:
    google_creds_dict = json.loads(GOOGLE_CREDENTIALS)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar",
    ]
    credentials = Credentials.from_service_account_info(google_creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    print(f"❌ Erro Google: {e}")

# ======== GEMINI ========
try:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo = genai.GenerativeModel("gemini-1.5-flash")
    print("✅ Gemini configurado com sucesso.")
except Exception as e:
    print(f"❌ Erro ao configurar Gemini: {e}")

# ======== TELEGRAM ========
app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá 👋! Sou seu bot de estoque conectado ao Google!")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    resposta = modelo.generate_content(texto)
    await update.message.reply_text(resposta.text)

app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

# ======== FLASK WEBHOOK ========
@app.route("/")
def index():
    return "🤖 Bot rodando com sucesso!"

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, app_telegram.bot)
        asyncio.run(app_telegram.process_update(update))
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
    return "ok", 200

if __name__ == "__main__":
    print("🌐 Servidor Flask rodando na porta 10000")
    app.run(host="0.0.0.0", port=10000)

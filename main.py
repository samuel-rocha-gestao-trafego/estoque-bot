import os
import nest_asyncio
import google.generativeai as genai
import gspread
from flask import Flask, request
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ========= VARIÁVEIS DE AMBIENTE =========
TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://estoque-bot-1.onrender.com")

# ========= GOOGLE =========
try:
    import json
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/calendar"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    print("❌ Erro ao conectar ao Google:", e)

# ========= GEMINI =========
try:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo = genai.GenerativeModel("gemini-2.5-flash")
    print("✅ Gemini configurado com sucesso.")
except Exception as e:
    print("❌ Erro ao configurar Gemini:", e)

# ========= TELEGRAM =========
nest_asyncio.apply()
app_telegram = Application.builder().token(TOKEN_TELEGRAM).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá 👋! Seu bot está ativo no Render com webhook!")

app_telegram.add_handler(CommandHandler("start", start))

# ========= FLASK (WEBHOOK) =========
server = Flask(__name__)

@server.route("/")
def home():
    return "✅ Bot ativo via Webhook!"

@server.route(f"/webhook/{TOKEN_TELEGRAM}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_telegram.bot)
    app_telegram.update_queue.put_nowait(update)
    return "ok", 200

async def setup_webhook():
    webhook_url = f"{RENDER_URL}/webhook/{TOKEN_TELEGRAM}"
    await app_telegram.bot.set_webhook(url=webhook_url)
    print(f"🌐 Webhook configurado em: {webhook_url}")

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_webhook())

    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Servidor Flask ativo na porta {port}")
    server.run(host="0.0.0.0", port=port)

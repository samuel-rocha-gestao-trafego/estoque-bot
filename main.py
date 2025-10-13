import os
import asyncio
import nest_asyncio
from flask import Flask
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ========= VARIÁVEIS DE AMBIENTE =========
TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not TOKEN_TELEGRAM:
    print("⚠️ TOKEN_TELEGRAM não encontrado no ambiente!")
if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY não encontrada!")
if not GOOGLE_CREDENTIALS:
    print("⚠️ GOOGLE_CREDENTIALS não encontrada!")

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
    modelo = genai.GenerativeModel("gemini-1.5-flash")
    print("✅ Gemini configurado com sucesso.")
except Exception as e:
    print("❌ Erro ao configurar Gemini:", e)

# ========= TELEGRAM =========
nest_asyncio.apply()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá! 🤖 O bot está rodando com sucesso no Render!")

async def main():
    if not TOKEN_TELEGRAM:
        raise ValueError("⚠️ Você deve passar o TOKEN_TELEGRAM válido!")
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
    app.add_handler(CommandHandler("start", start))
    print("🚀 Inicializando bot Telegram...")
    await app.run_polling()

# ========= FLASK KEEP-ALIVE =========
server = Flask(__name__)

@server.route("/")
def home():
    return "✅ Bot do Telegram ativo no Render!"

def start_flask():
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Servidor Flask rodando na porta {port}")
    server.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    start_flask()

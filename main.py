import os
import json
import logging
from flask import Flask, request
import google.generativeai as genai
import gspread
from tinydb import TinyDB, Query
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURAÇÕES ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
SHEET_NAME = os.getenv("SHEET_NAME", "EstoqueDepositoBebidas")

# --- VERIFICA VARIÁVEIS ---
if not TELEGRAM_TOKEN:
    raise ValueError("❌ Variável TELEGRAM_TOKEN não definida no ambiente!")
if not GEMINI_API_KEY:
    raise ValueError("❌ Variável GEMINI_API_KEY não definida no ambiente!")
if not GOOGLE_CREDENTIALS:
    raise ValueError("❌ Variável GOOGLE_CREDENTIALS não definida no ambiente!")

# --- CONFIG GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- CONECTA GOOGLE SHEETS ---
try:
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet = gc.open(SHEET_NAME)
    logging.info(f"✅ Conectado à planilha '{SHEET_NAME}' com sucesso!")
except Exception as e:
    logging.error(f"❌ Erro ao conectar à planilha: {e}")
    sheet = None

# --- MEMÓRIA PERSISTENTE ---
db = TinyDB("memory.json")
Memory = Query()

# --- FUNÇÕES DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Eu sou o assistente do estoque. Como posso ajudar?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text.strip()

    # Recupera histórico
    history = db.get(Memory.user_id == user_id)
    if not history:
        history = {"user_id": user_id, "conversation": []}

    # Adiciona mensagem ao histórico
    history["conversation"].append({"role": "user", "content": user_message})

    # Envia ao Gemini
    context_text = "\n".join([m["content"] for m in history["conversation"][-6:]])
    prompt = f"Contexto do chat:\n{context_text}\nUsuário disse: {user_message}"

    try:
        response = model.generate_content(prompt)
        ai_reply = response.text
    except Exception as e:
        ai_reply = f"⚠️ Erro na IA: {e}"

    # Adiciona resposta e salva no banco
    history["conversation"].append({"role": "assistant", "content": ai_reply})
    db.upsert(history, Memory.user_id == user_id)

    # Retorna resposta
    await update.message.reply_text(ai_reply)

# --- INICIA TELEGRAM ---
app_telegram = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- FLASK ROUTES ---
@app.route("/")
def home():
    return "✅ Estoque Bot rodando!"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_telegram.bot)
    app_telegram.process_update(update)
    return "OK", 200

if __name__ == "__main__":
    logging.info("🚀 Servidor Flask rodando na porta 10000")
    app.run(host="0.0.0.0", port=10000, debug=True)

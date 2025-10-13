import os
import json
import asyncio
from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.auth.transport.requests
import requests
from dotenv import load_dotenv
import google.auth
import logging

# ==============================
# CONFIGURAÇÕES INICIAIS
# ==============================
load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not TELEGRAM_TOKEN:
    print("⚠️ TOKEN_TELEGRAM não encontrado no ambiente!")
if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY não encontrado no ambiente!")
if not GOOGLE_CREDENTIALS:
    print("⚠️ GOOGLE_CREDENTIALS não encontrado no ambiente!")

# ==============================
# GOOGLE SERVICES (SHEETS + CALENDAR)
# ==============================
try:
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/calendar",
        ],
    )
    sheets_service = build("sheets", "v4", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    print("❌ Erro ao conectar ao Google:", e)

# ==============================
# GEMINI (IA)
# ==============================
def gerar_resposta_gemini(texto_usuario):
    try:
        url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": texto_usuario}]}]}
        params = {"key": GEMINI_API_KEY}
        response = requests.post(url, headers=headers, params=params, json=payload)
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("Erro Gemini:", e)
        return "Desculpe, ocorreu um erro ao gerar a resposta."

print("✅ Gemini configurado com sucesso.")

# ==============================
# TELEGRAM BOT
# ==============================
bot = Bot(token=TELEGRAM_TOKEN)
app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

async def responder(update: Update, context):
    texto_usuario = update.message.text
    resposta = gerar_resposta_gemini(texto_usuario)
    await update.message.reply_text(resposta)

app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

# ==============================
# WEBHOOK FLASK
# ==============================
@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        asyncio.run(app_telegram.process_update(update))
    except Exception as e:
        print(f"❌ Erro ao processar update: {e}")
        return "Erro", 500
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Bot de estoque ativo 🚀"})


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Servidor Flask rodando na porta {port}")
    app.run(host="0.0.0.0", port=port)

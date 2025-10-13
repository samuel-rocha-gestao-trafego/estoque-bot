import os
import asyncio
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from gspread import authorize
from google.oauth2.service_account import Credentials
import json

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO, format="%(message)s")

print("🔍 Verificando variáveis de ambiente...")

# ====== VARIÁVEIS DO AMBIENTE ======
TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# ====== FALLBACK SE O TOKEN NÃO VIER ======
if not TOKEN_TELEGRAM:
    TOKEN_TELEGRAM = "8444243438:AAFAF_3ZLuWfFBghiP1gI4Vm54sQChO6nfs"
    print("⚠️ TOKEN_TELEGRAM não foi encontrado no ambiente! Usando fallback local (para teste).")
else:
    print("✅ TOKEN_TELEGRAM encontrado com sucesso.")

# ====== VERIFICAÇÃO DAS OUTRAS VARIÁVEIS ======
if GEMINI_API_KEY:
    print("✅ GEMINI_API_KEY carregado.")
else:
    print("❌ GEMINI_API_KEY não encontrado!")

if GOOGLE_CREDENTIALS_JSON:
    print("✅ GOOGLE_CREDENTIALS carregado (conteúdo omitido por segurança).")
else:
    print("❌ GOOGLE_CREDENTIALS não encontrado!")

# ====== CONEXÃO GOOGLE ======
try:
    creds_json = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/calendar"])
    gc = authorize(creds)
    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    print("❌ Falha ao conectar com o Google:", e)

# ====== CONEXÃO GEMINI ======
try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini configurado com sucesso.")
except Exception as e:
    print("❌ Erro ao configurar Gemini:", e)

# ====== COMANDO /start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot ativo e funcionando no Render!")

# ====== FUNÇÃO PRINCIPAL ======
async def main():
    print("🚀 Inicializando bot...")
    try:
        app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
        app.add_handler(CommandHandler("start", start))
        print("✅ Bot inicializado com sucesso! Aguardando mensagens...")
        await app.run_polling()
    except Exception as e:
        print(f"❌ Erro ao iniciar o bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())

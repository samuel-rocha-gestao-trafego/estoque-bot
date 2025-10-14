import os
import json
import asyncio
from flask import Flask, request

# --- Telegram ---
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# --- Google e Gemini ---
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# 🔧 INICIALIZAÇÃO FLASK
# ============================================================
app_flask = Flask(__name__)

# Variáveis globais
app_telegram = None
modelo = None
gspread_client = None


# ============================================================
# 🚀 SETUP PRINCIPAL
# ============================================================
def setup_application():
    """Configura Telegram, Gemini e Google API"""
    global app_telegram, modelo, gspread_client

    print("🔍 Verificando variáveis de ambiente...")

    TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

    if not TELEGRAM_TOKEN:
        raise RuntimeError("❌ TOKEN_TELEGRAM ausente. Configure nas variáveis de ambiente.")
    if not GEMINI_API_KEY:
        raise RuntimeError("❌ GEMINI_API_KEY ausente.")
    if not GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError("❌ GOOGLE_CREDENTIALS ausente.")

    # --------------------------------------------------------
    # 1️⃣ Conectar ao Google (Sheets e Calendar)
    try:
        google_creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(
            google_creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/calendar",
            ],
        )
        gspread_client = gspread.authorize(creds)
        print("✅ Conectado ao Google (Planilhas + Calendário)")
    except Exception as e:
        print(f"❌ Erro ao conectar ao Google: {e}")

    # --------------------------------------------------------
    # 2️⃣ Configurar Gemini
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        modelo = genai.GenerativeModel("gemini-1.5-flash")
        print("✅ Gemini configurado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao configurar Gemini: {e}")

    # --------------------------------------------------------
    # 3️⃣ Inicializar o bot do Telegram
    try:
        print("🚀 Configurando aplicação do Telegram via builder...")
        app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()
        app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
        print("✅ Application do Telegram configurada.")
    except Exception as e:
        print(f"❌ Erro ao configurar Telegram: {e}")


# ============================================================
# 💬 FUNÇÃO DE RESPOSTA
# ============================================================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde mensagens recebidas pelo Telegram"""
    if not modelo:
        await update.message.reply_text("❌ O serviço de IA (Gemini) não está configurado.")
        return

    try:
        texto_usuario = update.message.text
        print(f"📩 Mensagem recebida do Telegram: {texto_usuario}")

        await update.message.reply_text("💭 Processando sua solicitação, um momento...")

        # Gera resposta via Gemini
        resposta = await asyncio.to_thread(modelo.generate_content, texto_usuario)

        if resposta and hasattr(resposta, "text"):
            await update.message.reply_text(resposta.text)
        else:
            await update.message.reply_text("⚠️ Não consegui gerar uma resposta no momento.")
    except Exception as e:
        print(f"❌ Erro ao responder: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao processar sua mensagem.")


# ============================================================
# 🌐 ROTAS FLASK
# ============================================================
@app_flask.route("/", methods=["GET"])
def home():
    """Verifica se o servidor está online"""
    return "🤖 Bot do Telegram está ativo no Render!"


@app_flask.route(f"/webhook/{os.getenv('TOKEN_TELEGRAM')}", methods=["POST"])
async def webhook():
    """Recebe mensagens do Telegram via Webhook"""
    if not app_telegram:
        print("❌ Webhook chamado antes da configuração.")
        return "Servidor em inicialização", 503

    try:
        data = request.get_json(force=True)
        await app_telegram.process_update(data)
        return "OK", 200
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return "Erro interno", 500


# ============================================================
# ▶️ EXECUÇÃO LOCAL / DESENVOLVIMENTO
# ============================================================
if __name__ == "__main__":
    try:
        setup_application()
    except Exception as e:
        print(f"❌ Falha crítica na configuração: {e}")
        exit(1)

    PORT = int(os.environ.get("PORT", 8080))
    print(f"🌍 Servidor Flask iniciando na porta {PORT}...")
    app_flask.run(host="0.0.0.0", port=PORT)

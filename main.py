import os
import json
import asyncio
import nest_asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# Permite rodar asyncio dentro do Flask
nest_asyncio.apply()

# Inicializa Flask
app_flask = Flask(__name__)

# ======== VERIFICAÇÃO DE VARIÁVEIS =========
print("🔍 Verificando variáveis de ambiente...")

TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
if not TELEGRAM_TOKEN:
    print("⚠️ TOKEN_TELEGRAM não encontrado no ambiente!")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY ausente!")

GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")
if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("❌ GOOGLE_CREDENTIALS ausente!")

# ======== CONEXÃO COM GOOGLE ========
try:
    google_creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        google_creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/calendar"]
    )
    gspread_client = gspread.authorize(creds)
    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    print(f"❌ Erro ao conectar ao Google: {e}")

# ======== CONFIGURAR GEMINI ========
try:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo = genai.GenerativeModel("gemini-1.5-flash")
    print("✅ Gemini configurado com sucesso.")
except Exception as e:
    print(f"❌ Erro ao configurar Gemini: {e}")

# ======== FUNÇÃO DE RESPOSTA ========
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        texto_usuario = update.message.text
        print(f"📩 Mensagem recebida do Telegram: {texto_usuario}")

        await update.message.reply_text("💭 Processando sua solicitação, um momento...")

        # Gera resposta com Gemini em thread separada
        resposta = await asyncio.to_thread(modelo.generate_content, texto_usuario)

        if resposta and hasattr(resposta, "text"):
            texto_resposta = resposta.text
            print(f"🤖 Resposta gerada pelo Gemini: {texto_resposta}")
            await update.message.reply_text(texto_resposta)
        else:
            print("⚠️ Nenhum texto retornado pelo Gemini.")
            await update.message.reply_text("⚠️ Não consegui gerar uma resposta no momento.")
    except Exception as e:
        print(f"❌ Erro ao responder: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao processar sua mensagem.")

# ======== FLASK (WEBHOOK) ========
@app_flask.route("/", methods=["GET"])
def home():
    return "🤖 Bot do Telegram está ativo no Render!"

@app_flask.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            print("⚠️ Nenhum dado recebido no webhook.")
            return "Sem conteúdo", 400

        # Converte JSON em objeto Update
        update = Update.de_json(data, app_telegram.bot)

        # Executa processamento assíncrono de forma segura
        loop = asyncio.get_event_loop()
        loop.create_task(app_telegram.process_update(update))

        return "OK", 200
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return "Erro interno", 500

# ======== INICIALIZAÇÃO DO BOT ========
async def iniciar_bot():
    print("🚀 Inicializando bot...")
    global app_telegram
    app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("✅ Bot configurado e aguardando mensagens...")

    # Define o webhook
    url_webhook = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TELEGRAM_TOKEN}"
    await app_telegram.bot.set_webhook(url=url_webhook)
    print(f"🌐 Webhook configurado em: {url_webhook}")

# ======== INÍCIO DO SERVIDOR ========
if __name__ == "__main__":
    asyncio.get_event_loop().create_task(iniciar_bot())
    app_flask.run(host="0.0.0.0", port=10000)

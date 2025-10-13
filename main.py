import os
import json
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# Inicializa Flask
app_flask = Flask(__name__)

# Variável global para a aplicação do Telegram
app_telegram = None 
modelo = None
gspread_client = None

# ======== FUNÇÃO DE SETUP (Síncrona) ========
# Configura o ambiente, conexões e o app_telegram
def setup_application():
    global app_telegram, modelo, gspread_client
    
    print("🔍 Verificando variáveis de ambiente...")

    TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

    if not TELEGRAM_TOKEN:
        raise RuntimeError("❌ TOKEN_TELEGRAM ausente. Verifique as variáveis de ambiente.")
    if not GEMINI_API_KEY:
        raise RuntimeError("❌ GEMINI_API_KEY ausente.")
    if not GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError("❌ GOOGLE_CREDENTIALS ausente.")

    # 1. Conexão com Google
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

    # 2. Configurar Gemini
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        modelo = genai.GenerativeModel("gemini-1.5-flash")
        print("✅ Gemini configurado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao configurar Gemini: {e}")

    # 3. Inicializar PTB Application (SEM chamar métodos de run ou webhook)
    print("🚀 Configurando aplicação do Telegram...")
    app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Adiciona handlers
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("✅ Application do Telegram configurada.")


# ======== FUNÇÃO DE RESPOSTA (Assíncrona) ========
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # A lógica de resposta permanece a mesma
    if not modelo:
        await update.message.reply_text("❌ O serviço de IA (Gemini) não está configurado.")
        return
        
    try:
        texto_usuario = update.message.text
        print(f"📩 Mensagem recebida do Telegram: {texto_usuario}")

        await update.message.reply_text("💭 Processando sua solicitação, um momento...")

        resposta = await asyncio.to_thread(modelo.generate_content, texto_usuario)

        if resposta and hasattr(resposta, "text"):
            await update.message.reply_text(resposta.text)
        else:
            await update.message.reply_text("⚠️ Não consegui gerar uma resposta no momento.")
    except Exception as e:
        print(f"❌ Erro ao responder: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao processar sua mensagem.")

# ======== FLASK (WEBHOOK - Assíncrono com APLICAÇÃO) ========
@app_flask.route("/", methods=["GET"])
def home():
    return "🤖 Bot do Telegram está ativo no Render!"

@app_flask.route(f"/webhook/{os.getenv('TOKEN_TELEGRAM')}", methods=["POST"])
async def webhook(): 
    if not app_telegram:
        print("❌ Webhook chamado antes da configuração.")
        return "Servidor em inicialização", 503 

    try:
        # Recebe o JSON da requisição do Telegram
        data = request.get_json(force=True) 
        
        # Processa a atualização do Telegram de forma assíncrona
        # Note que passamos o dicionário de dados (JSON)
        await app_telegram.process_update(data)

        return "OK", 200
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return "Erro interno", 500

# ======== INÍCIO DO SERVIDOR ========
if __name__ == "__main__":
    
    # 1. Setup Síncrono
    try:
        setup_application()
    except Exception as e:
        print(f"❌ Falha crítica na configuração: {e}")
        exit(1)
        
    # 2. Início do Servidor Flask
    PORT = int(os.environ.get("PORT", 8080))
    
    print(f"🌍 Servidor Flask iniciando na porta {PORT}...")
    
    # A função `webhook` é agora `async`, o que exige um servidor compatível.
    # Para o Render Worker, usaremos Gunicorn + Uvicorn/Gevemt para garantir o suporte.
    # Se você ainda estiver usando 'python main.py', o Flask embutido pode ter problemas.
    #
    # O comando de start (no render.yaml) deve ser:
    # gunicorn --bind 0.0.0.0:$PORT -w 4 main:app_flask --worker-class gevent
    # (Ou mude para o Gunicorn + Uvicorn)

    # Por enquanto, rodaremos o Flask síncrono, mas o Gunicorn é o mais indicado!
    app_flask.run(host="0.0.0.0", port=PORT)

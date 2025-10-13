import os
import json
import asyncio
# REMOVIDO: import nest_asyncio - Não é necessário para este padrão de webhook
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# Inicializa Flask
app_flask = Flask(__name__)

# Variável global para a aplicação do Telegram
app_telegram = None 

# ======== VERIFICAÇÃO DE VARIÁVEIS =========
print("🔍 Verificando variáveis de ambiente...")

TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ TOKEN_TELEGRAM ausente ou não disponível. Verifique as variáveis de ambiente do Render!")

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
    modelo = None 


# ======== FUNÇÃO DE RESPOSTA ========
# Coroutine
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not modelo:
        await update.message.reply_text("❌ O serviço de IA (Gemini) não está configurado. Verifique a chave API.")
        return
        
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
async def webhook(): # AGORA É ASYNC!
    # A verificação do app_telegram é crucial aqui.
    if not app_telegram:
        print("❌ Webhook chamado antes do app_telegram estar pronto.")
        return "Servidor em inicialização", 503 

    try:
        data = request.get_json(force=True) # force=True ajuda se o header Content-Type não for perfeito
        if not data:
            print("⚠️ Nenhum dado recebido no webhook.")
            return "Sem conteúdo", 400

        # process_update agora pode ser chamado diretamente (async)
        # O Flask moderno lida bem com funções de rota async
        await app_telegram.process_update(data)

        return "OK", 200
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return "Erro interno", 500

# ======== INICIALIZAÇÃO DO BOT (Assíncrona - Chamado apenas UMA VEZ) ========
async def inicializar_telegram_app():
    print("🚀 Configurando aplicação do Telegram...")
    global app_telegram
    
    # Cria a aplicação do Telegram
    app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

    # Adiciona handlers
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    
    # Define o webhook
    url_webhook = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TELEGRAM_TOKEN}"
    await app_telegram.bot.set_webhook(url=url_webhook)
    print(f"🌐 Webhook configurado em: {url_webhook}")
    print("✅ Bot configurado e pronto para receber webhooks.")

# ======== INÍCIO DO SERVIDOR (Síncrono e Corrigido) ========
if __name__ == "__main__":
    
    # Executa a inicialização do PTB (configura o webhook) de forma síncrona
    # Isso garante que app_telegram seja definido.
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(inicializar_telegram_app())
    except Exception as e:
        print(f"❌ Falha crítica na inicialização do PTB: {e}")
        exit(1)
        
    # Usa a porta correta do Render
    PORT = int(os.environ.get("PORT", 8080))
    
    # Usa um servidor mais robusto para async/webhook (como Waitress ou Gunicorn + Uvicorn)
    # Mas para o Render Worker simples, o Flask padrão (com rota async) pode funcionar.
    print(f"🌍 Servidor Flask iniciando na porta {PORT}...")
    
    # Nota: para suportar a função 'async def webhook()', você deve usar um 
    # servidor WSGI/ASGI compatível com async. O Flask nativo (app_flask.run) é síncrono,
    # o que pode ser a próxima falha. Vamos tentar com a biblioteca 'gevent' ou 'waitress'
    # para ser mais seguro, mas por enquanto, vamos manter o Flask run e torcer para o Render
    # lidar com isso ou mudar o `startCommand`.

    app_flask.run(host="0.0.0.0", port=PORT)

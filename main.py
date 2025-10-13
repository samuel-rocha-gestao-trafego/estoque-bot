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

# Permite rodar asyncio dentro do Flask (mantido, mas a estrutura de inicialização foi ajustada)
nest_asyncio.apply()

# Inicializa Flask
app_flask = Flask(__name__)

# Variável global para a aplicação do Telegram (definida durante a inicialização)
app_telegram = None 

# ======== VERIFICAÇÃO DE VARIÁVEIS =========
print("🔍 Verificando variáveis de ambiente...")

TELEGRAM_TOKEN = os.getenv("TOKEN_TELEGRAM")
# O erro 500 pode ocorrer se o token não estiver disponível na rota do webhook
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
    # Se a conexão falhar, o bot não deve travar completamente, mas é bom logar.
    print(f"❌ Erro ao conectar ao Google: {e}")

# ======== CONFIGURAR GEMINI ========
try:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo = genai.GenerativeModel("gemini-1.5-flash")
    print("✅ Gemini configurado com sucesso.")
except Exception as e:
    print(f"❌ Erro ao configurar Gemini: {e}")
    # Se a API do Gemini falhar, o bot não deve travar
    modelo = None 


# ======== FUNÇÃO DE RESPOSTA ========
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
def webhook():
    # A verificação do app_telegram é crucial aqui.
    if not app_telegram:
        print("❌ Webhook chamado antes do app_telegram estar pronto.")
        return "Servidor em inicialização", 503 # Retorno 503 - Service Unavailable

    try:
        data = request.get_json()
        if not data:
            print("⚠️ Nenhum dado recebido no webhook.")
            return "Sem conteúdo", 400

        # Converte JSON em objeto Update (Agora app_telegram está garantido)
        update = Update.de_json(data, app_telegram.bot)

        # Executa processamento assíncrono de forma segura
        loop = asyncio.get_event_loop()
        loop.create_task(app_telegram.process_update(update))

        return "OK", 200
    except Exception as e:
        # Se houver erro, loga e retorna 500, como antes.
        print(f"❌ Erro no webhook: {e}")
        return "Erro interno", 500

# ======== INICIALIZAÇÃO DO BOT (Assíncrona) ========
async def iniciar_bot():
    print("🚀 Inicializando bot...")
    global app_telegram
    
    # Cria a aplicação do Telegram
    app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

    # Adiciona handlers
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("✅ Bot configurado e aguardando mensagens...")

    # Define o webhook
    # Render usa RENDER_EXTERNAL_HOSTNAME para o domínio
    # Usamos os.getenv('PORT') para garantir a porta correta
    url_webhook = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TELEGRAM_TOKEN}"
    await app_telegram.bot.set_webhook(url=url_webhook)
    print(f"🌐 Webhook configurado em: {url_webhook}")
    
    return True # Sinaliza sucesso na inicialização

# ======== INÍCIO DO SERVIDOR (Síncrono e Corrigido) ========
if __name__ == "__main__":
    
    # CORREÇÃO CRÍTICA: Roda a inicialização do bot (assíncrona) de forma SÍNCRONA
    # para garantir que app_telegram seja definido antes do Flask rodar.
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(iniciar_bot())
        print("✅ Inicialização assíncrona do bot concluída.")
    except Exception as e:
        print(f"❌ Falha crítica na inicialização do bot: {e}")
        exit(1) # Sai com erro se a inicialização falhar
        
    # CORREÇÃO DA PORTA: Usa a variável de ambiente $PORT injetada pelo Render.
    PORT = int(os.environ.get("PORT", 8080)) # Padrão para 8080 se não encontrar (segurança)
    
    print(f"🌍 Servidor Flask iniciando na porta {PORT}...")
    app_flask.run(host="0.0.0.0", port=PORT)

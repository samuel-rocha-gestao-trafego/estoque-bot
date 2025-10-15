import os
import json
from flask import Flask, request
import telegram
from telegram.ext import CommandHandler, MessageHandler, filters, ApplicationBuilder, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from tinydb import TinyDB, Query

# ============================
# Configurações iniciais
# ============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY or not GOOGLE_CREDENTIALS_JSON:
    raise ValueError("⚠️ Variáveis de ambiente ausentes (TELEGRAM_TOKEN, GEMINI_API_KEY, GOOGLE_CREDENTIALS)")

# ============================
# Configuração do Gemini 2.5 Flash
# ============================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ============================
# Configuração do Google Sheets
# ============================
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

gc = gspread.authorize(creds)
spreadsheet = gc.open("EstoqueDepositoBebidas")
sheet = spreadsheet.sheet1  # primeira aba

# ============================
# Persistência de Memória
# ============================
db = TinyDB("memory.json")

# ============================
# Configuração do Bot do Telegram
# ============================
bot = telegram.Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Olá! Assistente de Estoque IA conectado com Google Sheets!")

async def registrar(update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dados = " ".join(context.args)
        if not dados:
            await update.message.reply_text("⚠️ Envie os dados no formato: /registrar Produto Quantidade")
            return

        partes = dados.split()
        produto = partes[0]
        quantidade = partes[1] if len(partes) > 1 else "0"

        sheet.append_row([produto, quantidade])
        db.insert({"produto": produto, "quantidade": quantidade})
        await update.message.reply_text(f"✅ {produto} adicionado com {quantidade} unidades.")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao registrar: {e}")

async def responder(update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = update.message.text
    resposta = model.generate_content(mensagem).text
    await update.message.reply_text(resposta)

# ============================
# Inicialização do Telegram Bot
# ============================
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("registrar", registrar))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

@app.route("/")
def index():
    return "🤖 Assistente de Estoque IA rodando!"

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(application.run_polling())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

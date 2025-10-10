import os
import json
import asyncio
import traceback
import nest_asyncio

from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------------
# 🔧 APLICAÇÃO DE PATCH PARA LOOP ASYNCIO NO RENDER
# -------------------------------------------------------
nest_asyncio.apply()

# -------------------------------------------------------
# 🔑 CARREGAMENTO DAS CREDENCIAIS DO GOOGLE
# -------------------------------------------------------
try:
    google_credentials_json = os.getenv("GOOGLE_CREDENTIALS")
    if not google_credentials_json:
        raise RuntimeError("⚠️ Variável GOOGLE_CREDENTIALS não encontrada!")

    credentials_dict = json.loads(google_credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/calendar",
        ],
    )

    sheets_client = gspread.authorize(credentials)
    calendar_service = build("calendar", "v3", credentials=credentials)

    print("✅ Conectado ao Google (Planilhas + Calendário)")
except Exception as e:
    print("❌ Erro ao autenticar Google:", e)
    traceback.print_exc()
    raise SystemExit(1)

# -------------------------------------------------------
# 💬 CONFIGURAÇÃO DO TELEGRAM
# -------------------------------------------------------
TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
if not TOKEN_TELEGRAM:
    raise RuntimeError("⚠️ Variável TOKEN_TELEGRAM não encontrada!")

# -------------------------------------------------------
# 🤖 LÓGICA DO BOT
# -------------------------------------------------------
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a mensagens recebidas no Telegram."""
    try:
        texto_usuario = update.message.text.strip().lower()

        if "oi" in texto_usuario or "olá" in texto_usuario:
            await update.message.reply_text("👋 Olá! Eu sou o assistente de estoque.")
        elif "estoque" in texto_usuario:
            await update.message.reply_text("📦 Consultando estoque...")
            # Exemplo de leitura de planilha:
            try:
                planilha = sheets_client.open("Controle de Estoque").sheet1
                dados = planilha.get_all_records()
                await update.message.reply_text(f"Encontrei {len(dados)} itens na planilha.")
            except Exception as e:
                await update.message.reply_text(f"Erro ao acessar planilha: {e}")
        else:
            await update.message.reply_text("🤖 Não entendi, tente algo como 'ver estoque'.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ocorreu um erro: {e}")
        traceback.print_exc()

# -------------------------------------------------------
# 🚀 INICIALIZAÇÃO DO BOT
# -------------------------------------------------------
async def main():
    print("🚀 Inicializando bot...")
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()

    # Adiciona o handler principal
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 Assistente de Estoque IA v2.2 rodando. Fale com o bot no Telegram.")
    await app.run_polling(close_loop=False)

# -------------------------------------------------------
# ▶️ EXECUÇÃO PRINCIPAL
# -------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ Erro ao iniciar:", e)
        traceback.print_exc()

import os
import requests
import logging
from flask import Flask, request, jsonify

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.route('/')
def home():
    return "🤖 Bot de Estoque ativo e pronto!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json(force=True, silent=True)

    logger.info("🟢 RAW UPDATE RECEBIDO:")
    logger.info(update)

    if not update:
        logger.warning("⚠️ Nenhum dado recebido no update!")
        return "sem dados", 200

    message = (
        update.get("message")
        or update.get("edited_message")
        or update.get("channel_post")
        or update.get("callback_query")
    )

    if not message:
        logger.warning("⚠️ Nenhum campo de mensagem encontrado.")
        return "sem mensagem", 200

    chat_id = None
    text = None

    if "callback_query" in update:
        chat_id = update["callback_query"]["message"]["chat"]["id"]
        text = update["callback_query"]["data"]
    else:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

    logger.info(f"💬 CHAT_ID: {chat_id}")
    logger.info(f"💬 TEXTO: {text}")

    if chat_id:
        resposta = f"👋 Recebi sua mensagem: {text if text else '(vazio)'}"
        enviar_mensagem(chat_id, resposta)

    return jsonify(success=True), 200


def enviar_mensagem(chat_id, texto):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    try:
        r = requests.post(url, json=payload)
        logger.info(f"📤 Enviando para Telegram: {payload}")
        logger.info(f"📬 Resposta Telegram: {r.status_code} -> {r.text}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem: {e}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    logger.info(f"🚀 Servidor Flask rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=True)

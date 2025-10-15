from flask import Flask, request
import requests
import os
import logging

app = Flask(__name__)

# Configuração básica de logs
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# 🔒 Token seguro (vem do Render)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ Variável TELEGRAM_TOKEN não definida nas Environment Variables do Render!")

# URL base da API Telegram
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot do Telegram ativo no Render!"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    logging.info("🟢 RAW UPDATE RECEBIDO:\n%s", update)

    if not update:
        return "Sem conteúdo", 200

    # Verifica se existe mensagem
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        logging.info("💬 CHAT_ID: %s", chat_id)
        logging.info("💬 TEXTO: %s", text)

        # Resposta simples
        resposta = f"👋 Recebi sua mensagem: {text}"

        payload = {
            "chat_id": chat_id,
            "text": resposta
        }

        try:
            r = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
            logging.info("📤 Enviando para Telegram: %s", payload)
            logging.info("📬 Resposta Telegram: %s -> %s", r.status_code, r.text)
        except Exception as e:
            logging.error("❌ Erro ao enviar mensagem: %s", e)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info("🚀 Servidor Flask rodando na porta %s", port)
    app.run(host="0.0.0.0", port=port, debug=True)

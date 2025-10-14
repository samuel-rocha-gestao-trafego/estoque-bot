import os
import json
from flask import Flask, request
import requests

app = Flask(__name__)

# Pega o token do ambiente, sem deixar visível
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.route('/')
def home():
    return "✅ Bot ativo e aguardando mensagens."

@app.route(f'/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        app.logger.info(f"📩 Recebido do Telegram: {json.dumps(data, indent=2)}")

        if "message" not in data:
            return "Sem mensagem válida", 200

        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        resposta = f"Você disse: {text}"
        enviar_mensagem(chat_id, resposta)

        return "OK", 200

    except Exception as e:
        app.logger.error(f"❌ Erro no webhook: {str(e)}", exc_info=True)
        return "Erro interno", 500


def enviar_mensagem(chat_id, texto):
    try:
        url = f"{TELEGRAM_URL}/sendMessage"
        payload = {"chat_id": chat_id, "text": texto}
        response = requests.post(url, json=payload)
        app.logger.info(f"📤 Enviando resposta: {response.text}")
    except Exception as e:
        app.logger.error(f"❌ Falha ao enviar mensagem: {str(e)}", exc_info=True)


if __name__ == '__main__':
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.route('/')
def home():
    return "🤖 Bot de Estoque está ativo!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    print("📩 Update recebido:", update)  # <-- debug no log Render

    message = None
    chat_id = None

    # Detecta a mensagem de forma mais ampla
    if "message" in update:
        message = update["message"]
    elif "edited_message" in update:
        message = update["edited_message"]
    elif "channel_post" in update:
        message = update["channel_post"]

    # Se encontrou mensagem, tenta responder
    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        print(f"💬 Mensagem recebida de {chat_id}: {text}")

        # Teste: responde simples
        if text:
            resposta = f"👋 Oi! Você me disse: {text}"
        else:
            resposta = "Recebi algo, mas não consegui ler o texto 😅"

        enviar_mensagem(chat_id, resposta)

    return "ok", 200


def enviar_mensagem(chat_id, texto):
    """Função para enviar mensagens"""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    r = requests.post(url, json=payload)
    print("📤 Enviando resposta:", r.text)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    print(f"🚀 Servidor Flask rodando na porta {port}")
    app.run(host='0.0.0.0', port=port)

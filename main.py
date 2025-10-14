import os
from flask import Flask, request
import requests

app = Flask(__name__)

# 🔐 Lê o token do Telegram da variável de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.route('/')
def home():
    return "🤖 Bot de Estoque ativo!", 200

@app.route(f"/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    # Apenas para debug
    print("📩 Atualização recebida:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # Monta uma resposta simples
        resposta = f"Você disse: {text}"

        # Envia resposta pro Telegram
        enviar_mensagem(chat_id, resposta)

    return "ok", 200


def enviar_mensagem(chat_id, texto):
    """Envia mensagem via API do Telegram"""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    requests.post(url, json=payload)


if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 10000))
    print(f"🌍 Servidor Flask iniciado na porta {PORT}...")
    app.run(host="0.0.0.0", port=PORT)

import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.route('/')
def home():
    return "🤖 Bot de Estoque ativo e pronto!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json(force=True, silent=True)

    print("🟢 RAW UPDATE RECEBIDO:")
    print(update)  # 👈 isso vai mostrar no log do Render o conteúdo exato

    if not update:
        print("⚠️ Nenhum dado recebido no update!")
        return "sem dados", 200

    # Pega o objeto de mensagem (independente do tipo)
    message = (
        update.get("message")
        or update.get("edited_message")
        or update.get("channel_post")
        or update.get("callback_query")
    )

    if not message:
        print("⚠️ Nenhum campo de mensagem encontrado.")
        return "sem mensagem", 200

    chat_id = None
    text = None

    # Caso especial: callback_query (botão)
    if "callback_query" in update:
        chat_id = update["callback_query"]["message"]["chat"]["id"]
        text = update["callback_query"]["data"]
    else:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

    print(f"💬 CHAT_ID: {chat_id}")
    print(f"💬 TEXTO: {text}")

    if chat_id:
        resposta = f"👋 Recebi sua mensagem: {text if text else '(vazio)'}"
        enviar_mensagem(chat_id, resposta)

    return jsonify(success=True), 200


def enviar_mensagem(chat_id, texto):
    """Função para enviar mensagens e exibir log completo"""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto}
    try:
        r = requests.post(url, json=payload)
        print(f"📤 Requisição enviada ao Telegram: {payload}")
        print(f"📬 Resposta do Telegram: {r.status_code} -> {r.text}")
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    print(f"🚀 Servidor Flask rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=True)

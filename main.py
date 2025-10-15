import os
import json
import requests
from flask import Flask, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.generativeai as genai

# ============================================================
# 🔧 Configurações iniciais
# ============================================================

# Variáveis de ambiente (Render → Environment)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ Variável TELEGRAM_TOKEN não definida no Render!")
if not GOOGLE_CREDENTIALS:
    raise ValueError("❌ Variável GOOGLE_CREDENTIALS não definida no Render!")
if not GEMINI_API_KEY:
    raise ValueError("❌ Variável GEMINI_API_KEY não definida no Render!")

# Inicializa Flask
app = Flask(__name__)

# Configura Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Cria cliente Google
creds = service_account.Credentials.from_service_account_info(json.loads(GOOGLE_CREDENTIALS))
sheets_service = build("sheets", "v4", credentials=creds)
calendar_service = build("calendar", "v3", credentials=creds)

# IDs das planilhas e calendários (opcional: também podem vir das envs)
SHEET_ID = os.getenv("ABA_ESTOQUE")
CALENDAR_ID = os.getenv("CALENDAR_ID")


# ============================================================
# 🔹 Funções auxiliares
# ============================================================

def enviar_mensagem(chat_id, texto):
    """Envia mensagem de texto ao usuário pelo Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": texto}
    requests.post(url, json=data)


def processar_mensagem(usuario, texto):
    """Usa o Gemini para interpretar e decidir o que fazer"""
    try:
        prompt = f"""
        Você é um assistente de controle de estoque e agenda.
        O usuário disse: "{texto}"

        - Se ele quiser adicionar, retirar ou consultar produtos, use o Google Sheets.
        - Se for algo sobre compromissos, eventos ou horários, use o Google Calendar.
        - Retorne uma resposta natural e clara, explicando o que foi feito.

        Use um raciocínio prático, com base no contexto.
        """

        resposta = model.generate_content(prompt)
        resposta_texto = resposta.text.strip()

        # Aqui você pode personalizar o comportamento, por exemplo:
        # - chamar funções que realmente atualizam ou consultam o Sheets
        # - criar eventos no Calendar
        # - retornar resultados personalizados
        #
        # Por enquanto, ele apenas responde com o texto da IA
        return resposta_texto

    except Exception as e:
        return f"⚠️ Ocorreu um erro ao processar sua mensagem: {e}"


# ============================================================
# 🔹 Webhook do Telegram
# ============================================================

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    if update and "message" in update:
        chat_id = update["message"]["chat"]["id"]
        texto = update["message"].get("text", "")

        resposta = processar_mensagem(chat_id, texto)
        enviar_mensagem(chat_id, resposta)

    return "ok", 200


@app.route("/", methods=["GET"])
def home():
    return "🤖 API do Assistente de Estoque está ativa!", 200


# ============================================================
# 🚀 Inicialização
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor Flask rodando na porta {port}")
    app.run(host="0.0.0.0", port=port, debug=True)

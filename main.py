import os
import json
import datetime
import traceback
from flask import Flask, request, Response
from tinydb import TinyDB, Query
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================
# CONFIGURAÇÕES INICIAIS
# ==========================
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Variáveis do ambiente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")
NOME_PLANILHA = "EstoqueDepositoBebidas"

# Banco de memória local
db = TinyDB("memoria.json")

# ==========================
# CONFIGURAÇÃO GOOGLE SHEETS
# ==========================
if not GOOGLE_CREDENTIALS_JSON:
    raise ValueError("❌ Variável GOOGLE_CREDENTIALS não encontrada no ambiente.")

try:
    google_creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, SCOPES)
    gc = gspread.authorize(creds)
    planilha = gc.open(NOME_PLANILHA)
    aba_estoque = planilha.worksheet("Estoque")
    aba_mov = planilha.worksheet("Movimentacoes")
    print(f"✅ Conectado à planilha '{NOME_PLANILHA}' com sucesso.")
except Exception as e:
    print(f"❌ Erro ao conectar à planilha '{NOME_PLANILHA}': {e}")
    aba_estoque = None
    aba_mov = None

# ==========================
# CONFIG GEMINI
# ==========================
if not GEMINI_API_KEY:
    print("🚨 GEMINI_API_KEY não encontrada. Configure nas variáveis de ambiente.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=(
            "Você é o 'Assistente de Estoque IA'. Ajuda o usuário a gerenciar estoque, "
            "registrar entradas e saídas e consultar saldos. "
            "Use linguagem natural e mantenha as respostas curtas e diretas."
        ),
    )
    print("✅ Gemini configurado com sucesso.")

# ==========================
# FUNÇÕES DE NEGÓCIO (Sheets)
# ==========================
def obter_saldo(produto: str):
    if not aba_estoque:
        return {"status": "erro", "mensagem": "Aba de estoque não conectada."}
    registros = aba_estoque.get_all_records()
    for item in registros:
        nome = str(item.get("Produto", "")).strip()
        if produto.lower() in nome.lower():
            qtd = int(item.get("Quantidade", 0))
            return {"status": "sucesso", "produto": nome, "quantidade": qtd}
    return {"status": "vazio", "mensagem": f"{produto} não encontrado."}

def registrar_movimentacao(produto, quantidade, tipo, responsavel="", observacao=""):
    if not aba_mov:
        return {"status": "erro", "mensagem": "Aba de movimentações não conectada."}
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = [agora, produto, quantidade, tipo, responsavel, observacao]
    aba_mov.append_row(linha)
    return {"status": "sucesso", "mensagem": f"Movimentação registrada: {tipo} de {quantidade}x {produto}"}

def atualizar_saldo(produto, quantidade, acao, responsavel="", observacao=""):
    if not aba_estoque:
        return {"status": "erro", "mensagem": "Aba de estoque não conectada."}
    registros = aba_estoque.get_all_records()
    encontrado = False
    for idx, item in enumerate(registros, start=2):
        nome = str(item.get("Produto", "")).strip()
        if produto.lower() in nome.lower():
            atual = int(item.get("Quantidade", 0))
            if acao.lower() in ["compra", "entrada", "in", "+"]:
                novo = atual + int(quantidade)
                tipo_mov = "Entrada"
            elif acao.lower() in ["venda", "saida", "out", "-"]:
                novo = atual - int(quantidade)
                tipo_mov = "Saída"
            else:
                novo = atual + int(quantidade)
                tipo_mov = acao.capitalize()
            aba_estoque.update_cell(idx, 2, novo)
            registrar_movimentacao(produto, quantidade, tipo_mov, responsavel, observacao)
            return {"status": "sucesso", "mensagem": f"{tipo_mov} registrada. Novo saldo: {novo}"}
    # Produto novo
    aba_estoque.append_row([produto, int(quantidade), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    registrar_movimentacao(produto, quantidade, "Entrada", responsavel, observacao)
    return {"status": "sucesso", "mensagem": f"Produto '{produto}' adicionado ao estoque com {quantidade} unidades."}

# ==========================
# ENDPOINT TELEGRAM WEBHOOK
# ==========================
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return Response("Sem conteúdo", status=200)

        user_id = data["message"]["from"]["id"]
        text = data["message"].get("text", "")
        print(f"📩 Mensagem recebida de {user_id}: {text}")

        # Processamento de lógica
        resposta = model.generate_content(f"O usuário disse: {text}. Ajude com ações de estoque.")
        reply_text = resposta.text or "Não consegui gerar resposta."

        # Enviar resposta
        send_message(user_id, reply_text)
        return Response("OK", status=200)
    except Exception as e:
        print("❌ Erro no webhook:", e, traceback.format_exc())
        return Response("Erro interno", status=500)

# ==========================
# ENVIAR MENSAGEM TELEGRAM
# ==========================
import requests

def send_message(chat_id, text):
    if not TELEGRAM_TOKEN:
        print("🚫 TELEGRAM_TOKEN ausente.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Erro ao enviar mensagem:", e)

# ==========================
# ROTA DE STATUS
# ==========================
@app.route("/")
def home():
    return "🤖 Estoque IA rodando com integração Google Sheets!"

# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

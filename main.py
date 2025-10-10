import os
import json
import sys
import datetime
import traceback
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from googleapiclient.discovery import build

# =========================
# Carrega variáveis de ambiente
# =========================
def carregar_variaveis():
    print("\n🔍 Verificando variáveis de ambiente...")

    TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

    if not TOKEN_TELEGRAM:
        print("❌ ERRO: Variável TOKEN_TELEGRAM não encontrada!")
    else:
        print("✅ TOKEN_TELEGRAM carregado.")

    if not GEMINI_API_KEY:
        print("❌ ERRO: Variável GEMINI_API_KEY não encontrada!")
    else:
        print("✅ GEMINI_API_KEY carregado.")

    if not GOOGLE_CREDENTIALS:
        print("❌ ERRO: Variável GOOGLE_CREDENTIALS não encontrada!")
    else:
        print("✅ GOOGLE_CREDENTIALS carregado (conteúdo omitido por segurança).")

    if not all([TOKEN_TELEGRAM, GEMINI_API_KEY, GOOGLE_CREDENTIALS]):
        print("\n⚠️ Algumas variáveis estão ausentes. Corrija-as no painel do Render antes de continuar.\n")
        sys.exit(1)

    return TOKEN_TELEGRAM, GEMINI_API_KEY, GOOGLE_CREDENTIALS

# Carrega as variáveis
TOKEN_TELEGRAM, GEMINI_API_KEY, GOOGLE_CREDENTIALS = carregar_variaveis()

# =========================
# Configura credenciais Google
# =========================
try:
    print("\n🔑 Configurando autenticação Google...")
    creds_json = json.loads(GOOGLE_CREDENTIALS)

    SCOPES = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/calendar.events"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, SCOPES)
    gc = gspread.authorize(creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    print("✅ Conectado ao Google (Planilhas + Calendário)")

except Exception as e:
    print("❌ Erro ao conectar ao Google. Verifique as credenciais.")
    traceback.print_exc()
    sys.exit(1)

import os
import json
import gspread
from google.oauth2 import service_account

# 🔍 Etapa 1: Ler variável de ambiente
google_credentials_json = os.getenv("GOOGLE_CREDENTIALS")

# 🔍 Etapa 2: Validar se a variável existe
if not google_credentials_json:
    raise RuntimeError("⚠️ Variável GOOGLE_CREDENTIALS não encontrada! "
                       "Verifique nas Environment Variables do Render.")

# 🔍 Etapa 3: Converter o texto JSON em dicionário Python
try:
    creds_dict = json.loads(google_credentials_json)
except json.JSONDecodeError as e:
    raise RuntimeError("❌ Erro ao interpretar GOOGLE_CREDENTIALS como JSON. "
                       "Certifique-se de que o conteúdo foi copiado corretamente.") from e

# 🔍 Etapa 4: Criar credenciais e autenticar no Google Sheets
try:
    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    gc = gspread.authorize(credentials)
    print("✅ Autenticação Google concluída com sucesso!")
except Exception as e:
    raise RuntimeError(f"❌ Erro ao autenticar com Google: {e}")

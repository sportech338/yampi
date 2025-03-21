import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json
from datetime import datetime, timedelta

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")

# 🗓️ Data de ontem no formato YYYY-MM-DD
ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# URL com filtro da data
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts?created_at_from={ontem}"

# Cabeçalhos de autenticação
headers = {
    "User-token": TOKEN,
    "User-Secret-Key": SECRET_KEY,
    "Accept": "application/json"
}

# Requisição à API da Yampi
response = requests.get(URL, headers=headers)

if response.status_code == 200:
    carts_data = response.json().get("data", [])
    print(f"Carrinhos abandonados encontrados: {len(carts_data)}")
else:
    print("Erro ao buscar carrinhos:", response.status_code)
    print(response.text)
    carts_data = []

# Autenticar no Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
credentials_dict = json.loads(creds_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(credentials)

# Conectar à planilha
SPREADSHEET_ID = '1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E'
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1

# Adicionar cabeçalho se a planilha estiver vazia
if len(sheet.get_all_values()) == 0:
    sheet.append_row(["ID", "Token", "Total", "UTM Source", "UTM Campaign", "Produto"])

# Inserir os dados dos carrinhos abandonados
for cart in carts_data:
    try:
        cart_id = cart.get("id")
        token = cart.get("token")
        total = cart.get("totalizers", {}).get("total", 0)
        utm_source = cart.get("utm_source", "Não informado")
        utm_campaign = cart.get("utm_campaign", "Não informado")

        # Pegar nome do produto
        items_data = cart.get("items", {}).get("data", [])
        if items_data:
            product_name = items_data[0].get("sku", {}).get("data", {}).get("title", "Sem título")
        else:
            product_name = "Sem produto"

        # Adicionar à planilha
        sheet.append_row([cart_id, token, total, utm_source, utm_campaign, product_name])
        print(f"Carrinho {cart_id} adicionado com sucesso.")
    except Exception as e:
        import traceback
        print(f"Erro ao processar carrinho {cart.get('id', 'sem ID')}:")
        traceback.print_exc()

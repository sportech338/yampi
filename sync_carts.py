import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")

# URL da API - OBS: NÃO USAR "/export", pois esse endpoint só envia um e-mail com a planilha
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"

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

# Autenticar no Google Sheets usando o JSON da variável de ambiente
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
credentials_dict = json.loads(creds_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(credentials)

# Conectar à planilha
SPREADSHEET_ID = '1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E'
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1

# Inserir os dados dos carrinhos abandonados
for cart in carts_data:
    try:
        customer_name = cart.get('tracking_data', {}).get('name', 'Desconhecido')
        customer_email = cart.get('tracking_data', {}).get('email', 'Sem email')
        items = cart.get('items', [])
        product_name = items[0]['sku']['data']['title'] if items else 'Sem produto'
        total = cart.get('totalizers', {}).get('total', 0)

        sheet.append_row([customer_name, customer_email, product_name, total])
        print(f"Carrinho de {customer_name} adicionado com sucesso.")
    except Exception as e:
        import traceback
        print("Erro ao processar um carrinho:")
        traceback.print_exc()

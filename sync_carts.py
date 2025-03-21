import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")

# URL da API
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"

headers = {
    "User-token": TOKEN,
    "User-Secret-Key": SECRET_KEY,
    "Accept": "application/json"
}

# Requisição para a Yampi
response = requests.get(URL, headers=headers)

if response.status_code == 200:
    carts_data = response.json().get("data", [])
    print(f"Carrinhos abandonados encontrados: {len(carts_data)}")
else:
    print("Erro ao buscar carrinhos:", response.status_code)
    print(response.text)
    carts_data = []

# Salvar o JSON da API para debug
with open("debug.json", "w", encoding="utf-8") as f:
    json.dump(carts_data, f, indent=4, ensure_ascii=False)

print("Arquivo debug.json salvo com sucesso.")

# Autenticação com Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
credentials_dict = json.loads(creds_json)
credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(credentials)

# Planilha
SPREADSHEET_ID = '1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E'
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1

# Inserir os dados
for cart in carts_data:
    try:
        cart_id = cart.get("id")
        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")

        # Tenta obter o telefone a partir das várias fontes possíveis
        phone_area_code = ""
        phone_number = ""
        phone_formatted = ""

        phone_data = tracking.get("phone")
        if isinstance(phone_data, dict):
            phone_area_code = phone_data.get("area_code", "")
            phone_number = phone_data.get("number", "")
            phone_formatted = phone_data.get("formated_number", "")
        elif isinstance(phone_data, str):
            phone_number = phone_data
            phone_formatted = phone_data

        # Se ainda não tem telefone, tenta pegar de customer_phone direto
        if not phone_number:
            customer_phone = cart.get("customer_phone", "")
            phone_number = customer_phone
            phone_formatted = customer_phone

        # Produto
        items_data = cart.get("items", {}).get("data", [])
        if items_data:
            first_item = items_data[0]
            product_name = first_item.get("sku", {}).get("data", {}).get("title", "Sem título")
            quantity = first_item.get("quantity", 1)
        else:
            product_name = "Sem produto"
            quantity = 0

        total = cart.get("totalizers", {}).get("total", 0)

        # Envia para o Google Sheets
        sheet.append_row([
            cart_id,
            customer_name,
            customer_email,
            phone_area_code,
            phone_number,
            phone_formatted,
            product_name,
            quantity,
            total
        ])

        print(f"Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("Erro ao processar um carrinho:")
        traceback.print_exc()

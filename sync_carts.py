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

# Mapeamento das etapas do abandono
step_map = {
    "register": "Dados cadastrais",
    "shipment": "Entrega",
    "payment": "Pagamento"
}

# Inserir os dados
for cart in carts_data:
    try:
        print("\nDEBUG - Carrinho recebido da API:", cart)  # Debug

        cart_id = cart.get("id")

        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")

        # Extraindo telefone corretamente de dois lugares possíveis
        phone_data = tracking.get("phone", {})
        phone_area_code = phone_data.get("area_code", "N/A")
        phone_number = phone_data.get("number", "N/A")
        phone_formatted = phone_data.get("formated_number", "N/A")

        # Caso o telefone também esteja em "customer_phone"
        customer_phone = cart.get("customer_phone", "N/A")
        if customer_phone != "N/A":
            phone_number = customer_phone  # Usa o número alternativo, se existir

        items_data = cart.get("items", {}).get("data", [])
        if items_data:
            first_item = items_data[0]
            product_name = first_item.get("sku", {}).get("data", {}).get("title", "Sem título")
            quantity = first_item.get("quantity", 1)
        else:
            product_name = "Sem produto"
            quantity = 0

        total = cart.get("totalizers", {}).get("total", 0)

        # Pegando o momento do abandono corretamente
        abandoned_step = cart.get("abandoned_step", "Desconhecido")
        abandoned_step_name = step_map.get(abandoned_step, abandoned_step)  # Traduz para PT-BR

        # Adiciona os dados na planilha
        sheet.append_row([
            cart_id,         # ID do carrinho
            customer_name,   # Nome do cliente
            customer_email,  # Email
            phone_area_code, # Código de área (DDD)
            phone_number,    # Número do telefone
            phone_formatted, # Número formatado com DDD
            product_name,    # Nome do produto
            quantity,        # Quantidade
            total,           # Valor total
            abandoned_step_name  # Etapa do abandono
        ])

        print(f"Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("Erro ao processar um carrinho:")
        traceback.print_exc()

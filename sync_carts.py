import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import re

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

# Auxiliar: extrai número de telefone de string
def extrair_telefone(texto):
    match = re.search(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', texto)
    if match:
        return match.group()
    return ""

# Auxiliar: formata número no padrão brasileiro
def formatar_telefone(numero):
    digitos = re.sub(r'\D', '', numero)  # remove tudo que não for número
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    elif len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    else:
        return numero  # retorna do jeito que veio se não bater o padrão

# Inserir os dados
for cart in carts_data:
    try:
        cart_id = cart.get("id")
        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")

        # Tentando puxar telefone de várias fontes
        phone_area_code = ""
        phone_number = ""
        phone_formatted = ""

        phone_data = tracking.get("phone")

        # Caso seja objeto
        if isinstance(phone_data, dict):
            phone_area_code = phone_data.get("area_code", "")
            phone_number = phone_data.get("number", "")
            phone_formatted = phone_data.get("formated_number", "")
        # Caso seja string simples
        elif isinstance(phone_data, str):
            phone_number = phone_data
            phone_formatted = phone_data

        # tracking_data.customer_phone
        if not phone_number:
            tracking_phone = tracking.get("customer_phone")
            if isinstance(tracking_phone, str):
                phone_number = tracking_phone
                phone_formatted = tracking_phone

        # cart.customer_phone
        if not phone_number:
            customer_phone = cart.get("customer_phone")
            if isinstance(customer_phone, str):
                phone_number = customer_phone
                phone_formatted = customer_phone

        # Última tentativa: buscar qualquer número dentro de tracking_data como string
        if not phone_number:
            tracking_json_str = json.dumps(tracking)
            telefone_extraido = extrair_telefone(tracking_json_str)
            if telefone_extraido:
                phone_number = telefone_extraido
                phone_formatted = telefone_extraido

        # Aplica formatação final
        phone_formatted = formatar_telefone(phone_formatted)

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

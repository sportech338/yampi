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

# Funções auxiliares
def extrair_cpf(texto):
    match = re.search(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', texto)
    if match:
        cpf = re.sub(r'\D', '', match.group())
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return "Não encontrado"

def extrair_telefone(texto):
    matches = re.findall(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', texto)
    for numero in matches:
        apenas_digitos = re.sub(r'\D', '', numero)
        if len(apenas_digitos) in [10, 11] and not re.match(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', numero):
            return numero
    return ""

def formatar_telefone(numero):
    digitos = re.sub(r'\D', '', numero)
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    elif len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return ""

# Domínio correto para o checkout abandonado
dominio_loja = "seguro.lojasportech.com"

# Loop dos carrinhos
for cart in carts_data:
    try:
        cart_id = cart.get("id")
        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")

        # Texto completo do carrinho para busca de CPF e telefone
        cart_json_str = json.dumps(cart)

        # CPF
        cpf = extrair_cpf(cart_json_str)

        # Telefone
        telefone_cru = extrair_telefone(cart_json_str)
        telefone_formatado = formatar_telefone(telefone_cru)

        # Link do checkout abandonado
        token = cart.get("token", "")
        if token:
            link_checkout = f"https://{dominio_loja}/checkout/token/{token}"
        else:
            link_checkout = "Não encontrado"

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
            cart_id,                            # CARRINHO
            customer_name,                      # NOME DO CLIENTE
            customer_email,                     # EMAIL
            cpf,                                # CPF
            telefone_cru or "Não encontrado",   # NÚMERO
            telefone_formatado or "Não encontrado",  # FORMATO
            link_checkout,                      # LINK DO CHECKOUT
            product_name,                       # PRODUTO
            quantity,                           # QTD
            total                               # VALOR
        ])

        print(f"Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("Erro ao processar um carrinho:")
        traceback.print_exc()

import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")

# URL da API (sem /export!)
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
    1: "Dados cadastrais",
    2: "Entrega",
    3: "Pagamento"
}

# Inserir os dados
for cart in carts_data:
    try:
        print("\nDEBUG - Carrinho recebido da API:", cart)  # Debug

        cart_id = cart.get("id")

        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")
        customer_phone = tracking.get("phone", "Sem telefone")  # Pegando telefone corretamente

        items_data = cart.get("items", {}).get("data", [])
        if items_data:
            first_item = items_data[0]
            product_name = first_item.get("sku", {}).get("data", {}).get("title", "Sem título")
            quantity = first_item.get("quantity", 1)
        else:
            product_name = "Sem produto"
            quantity = 0

        total = cart.get("totalizers", {}).get("total", 0)

        # Momento do abandono
        checkout_step = cart.get("checkout_step")  # Verificar se está vindo como int
        abandoned_at = step_map.get(checkout_step, "Desconhecido")
        
        print(f"DEBUG - Etapa de abandono: {checkout_step} -> {abandoned_at}")  # Debug

        # Adiciona os dados na planilha
        sheet.append_row([
            cart_id,
            customer_name,
            customer_phone,
            customer_email,
            product_name,
            quantity,
            total,
            abandoned_at
        ])

        print(f"Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("Erro ao processar um carrinho:")
        traceback.print_exc()

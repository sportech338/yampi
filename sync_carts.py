import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# CONFIGURAÇÕES
ALIAS = "sportech"  # Substitua pelo alias da sua loja
TOKEN = os.getenv("YAMPI_API_TOKEN")  # Token da Yampi vindo dos secrets
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")  # Chave secreta da Yampi vinda dos secrets

# URL da API (endpoint para obter carrinhos abandonados)
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"

# Definindo os cabeçalhos corretos para autenticação
headers = {
    "User-token": TOKEN,           # Token da Yampi
    "User-Secret-Key": SECRET_KEY, # Chave secreta da Yampi
    "Accept": "application/json"
}

# Realizando a requisição para a API Yampi
response = requests.get(URL, headers=headers)

# Se a resposta for bem-sucedida (status 200)
if response.status_code == 200:
    carts_data = response.json().get("data", [])
    print(f"Carrinhos abandonados: {carts_data}")
else:
    print("Erro ao buscar carrinhos:", response.status_code)
    print(response.text)

# Autenticar com o Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(credentials)

# Conectar à planilha com o ID
SPREADSHEET_ID = '1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E'
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1  # Selecionar a primeira aba da planilha

# Inserir dados na planilha
for cart in carts_data:
    customer_name = cart['tracking_data']['name']
    customer_email = cart['tracking_data']['email']
    product_name = cart['items'][0]['sku']['data']['title']
    total = cart['totalizers']['total']

    # Adicionar uma nova linha com os dados dos carrinhos abandonados
    sheet.append_row([customer_name, customer_email, product_name, total])
    print(f"Carrinho de {customer_name} adicionado com sucesso.")

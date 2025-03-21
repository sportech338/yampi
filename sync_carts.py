import requests
import json
import gspread
import datetime
import pytz
from oauth2client.service_account import ServiceAccountCredentials
import os

# CONFIGURAÇÕES
ALIAS = "sportech"  # Substitua pelo alias da sua loja
TOKEN = os.getenv("YAMPI_API_TOKEN")
print(f"Token Yampi: {TOKEN}")
SHEET_ID = "1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E"
# URL da API
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"

# Filtrar dados das últimas 24h
tz_brasil = pytz.timezone("America/Sao_Paulo")
agora = datetime.datetime.now(tz_brasil)
ontem = agora - datetime.timedelta(days=1)

data_inicio = ontem.strftime("%Y-%m-%dT00:00:00-03:00")
data_fim = ontem.strftime("%Y-%m-%dT23:59:59-03:00")

params = {
    "limit": 100,
    "start_date": data_inicio,
    "end_date": data_fim
}

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}

response = requests.get(URL, headers=headers, params=params)

if response.status_code == 200:
    carts_data = response.json().get("data", [])
    rows = []
    for cart in carts_data:
        rows.append([
            cart.get("id", ""),
            cart.get("token", ""),
            cart["totalizers"].get("total", ""),
            cart["totalizers"].get("subtotal", ""),
            cart["totalizers"].get("total_items", ""),
            cart.get("utm_source", "Não informado"),
            cart.get("utm_campaign", "Não informado"),
            data_inicio
        ])

    # Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    creds_dict = json.loads(CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).sheet1

    for row in rows:
        sheet.append_row(row)

    print(f"✅ {len(rows)} carrinhos abandonados adicionados na planilha!")
else:
    print("Erro ao buscar carrinhos:", response.status_code)
    print(response.text)

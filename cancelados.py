import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import re
import time
from datetime import datetime, timedelta
import pytz

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")
SPREADSHEET_ID = '1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E'

# Fuso horário
tz = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(tz)
inicio_hoje = tz.localize(datetime.combine(agora.date(), datetime.min.time()))

# API Yampi - pedidos cancelados
BASE_URL = f"https://api.dooki.com.br/v2/{ALIAS}/orders"
headers = {
    "User-token": TOKEN,
    "User-Secret-Key": SECRET_KEY,
    "Accept": "application/json"
}

# Google Sheets
descoped_credentials = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(descoped_credentials, scopes=scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

try:
    sheet = spreadsheet.worksheet("Pix abandonado")
except gspread.exceptions.WorksheetNotFound:
    sheet = spreadsheet.add_worksheet(title="Pix abandonado", rows="1000", cols="20")

# Emails existentes (coluna E = índice 4)
valores_planilha = sheet.get_all_values()[1:]
emails_existentes = {linha[4].strip().lower() for linha in valores_planilha if len(linha) >= 5}

def extrair_telefone(texto):
    matches = re.findall(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', texto)
    for numero in matches:
        apenas_digitos = re.sub(r'\D', '', numero)
        if len(apenas_digitos) in [10, 11]:
            ddd = apenas_digitos[:2]
            telefone = apenas_digitos[2:]
            if len(telefone) == 8:
                telefone = '9' + telefone
            numero_formatado = f"0{ddd}{telefone}"
            if numero_formatado.count(numero_formatado[1]) == len(numero_formatado) - 1:
                return ""
            return numero_formatado
    return ""

# Paginação
orders_cancelados = []
page = 1
while True:
    url = f"{BASE_URL}?status=cancelled&page={page}"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            break
        for order in data:
            updated_at = order.get("updated_at", {}).get("date")
            if updated_at:
                try:
                    dt = tz.localize(datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%f"))
                except:
                    dt = tz.localize(datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S"))
                if inicio_hoje <= dt <= agora:
                    order["data_cancelamento"] = dt.strftime("%d/%m/%Y %H:%M")
                    orders_cancelados.append(order)
        print(f"📄 Página {page} carregada com pedidos cancelados.")
        page += 1
        time.sleep(0.5)  # Evita erro 429
    except Exception as e:
        print(f"❌ Erro ao buscar pedidos página {page}: {e}")
        break

# Inserção
linhas_para_inserir = []
adicionados = 0
ignorados = 0
houve_erro_real = False

for order in orders_cancelados:
    try:
        nome = order.get("customer", {}).get("name", "Desconhecido").strip()
        email = order.get("customer", {}).get("email", "Sem email").strip().lower()

        if email in emails_existentes:
            ignorados += 1
            continue

        telefone = extrair_telefone(json.dumps(order))
        item = order.get("items", [{}])[0]
        produto = item.get("title", "Sem título")
        qtd = item.get("quantity", 1)
        total = order.get("total", 0)

        # Identificar forma de pagamento
        forma_pagamento = "Desconhecido"
        transacoes = order.get("transactions", {}).get("data", [])
        for transacao in transacoes:
            metodo = transacao.get("payment_method")
            if metodo == "pix":
                forma_pagamento = "Pix"
                break
            elif metodo == "credit_card":
                forma_pagamento = "Cartão de crédito"
                break
            elif metodo == "boleto":
                forma_pagamento = "Boleto"
                break

        status_final = f"❌ Cancelado ({forma_pagamento})"

        linhas_para_inserir.append([
            order.get("data_cancelamento", ""), "", "Pedido cancelado", nome,
            email, telefone or "Não encontrado", produto,
            qtd, total, status_final, "", "", "", "", "", ""
        ])
        adicionados += 1

    except Exception as e:
        houve_erro_real = True
        print(f"❌ Erro ao processar pedido {order.get('id', 'sem id')}: {e}")

if linhas_para_inserir:
    sheet.insert_rows(linhas_para_inserir, row=2)
    print(f"✅ {adicionados} pedidos cancelados adicionados.")

# Logs
try:
    aba_logs = spreadsheet.worksheet("Logs")
except gspread.exceptions.WorksheetNotFound:
    aba_logs = spreadsheet.add_worksheet(title="Logs", rows="1000", cols="5")
    aba_logs.append_row(["Data", "Total do dia", "Adicionados", "Ignorados", "Erro?"])

data_execucao = agora.strftime("%d/%m/%Y %H:%M")
houve_erro = "Sim" if houve_erro_real else "Não"
aba_logs.append_row([data_execucao, len(orders_cancelados), adicionados, ignorados, houve_erro])

# Print final
print(f"""
📜 LOG DE EXECUÇÃO (PEDIDOS CANCELADOS)

📅 Data: {data_execucao}
❌ Cancelados filtrados: {len(orders_cancelados)}
✅ Adicionados: {adicionados}
🔀 Ignorados (já estavam na planilha): {ignorados}
❗ Houve erro? {houve_erro}
""")

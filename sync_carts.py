import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import re
from datetime import datetime, timedelta
import pytz

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")

# Filtro de datas - intervalo de ontem (horário de São Paulo)
tz = pytz.timezone("America/Sao_Paulo")
ontem = datetime.now(tz) - timedelta(days=1)
data_inicio = ontem.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
data_fim = ontem.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

# URL da API com filtro de data
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts/export?updated_at[start]={data_inicio}&updated_at[end]={data_fim}"

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

# Buscar todos os IDs já existentes na planilha para evitar duplicatas
ids_existentes = [str(row[0]) for row in sheet.get_all_values()[1:] if row]

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

# Domínio correto do checkout funcional
dominio_loja = "seguro.lojasportech.com"

# Loop dos carrinhos
for cart in carts_data:
    try:
        cart_id = str(cart.get("id"))
        token = cart.get("token", "")

        # Evitar duplicação
        if cart_id in ids_existentes:
            print(f"⚠️ Carrinho {cart_id} já está na planilha. Pulando.")
            continue

        print(f"\n🛒 CARRINHO ID: {cart_id}")
        print(f"🔐 TOKEN: {token}")
        print(f"🔗 LINK GERADO: https://{dominio_loja}/cart?cart_token={token}")
        print("📦 CONTEÚDO DO CARRINHO:")
        print(json.dumps(cart, indent=2, ensure_ascii=False)[:2000])

        # Nome e email
        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")

        # CPF e telefone
        cart_json_str = json.dumps(cart)
        cpf = extrair_cpf(cart_json_str)
        telefone = extrair_telefone(cart_json_str)
        telefone_formatado = formatar_telefone(telefone)

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

        link_checkout = f"https://{dominio_loja}/cart?cart_token={token}" if token else "Não encontrado"

        # Envia para o Google Sheets
        sheet.append_row([
            cart_id,
            customer_name,
            customer_email,
            cpf,
            telefone_formatado or "Não encontrado",
            product_name,
            quantity,
            total,
            link_checkout
        ])

        print(f"✅ Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("❌ Erro ao processar um carrinho:")
        traceback.print_exc()

# Criar ou acessar aba de logs
try:
    aba_logs = spreadsheet.worksheet("Logs")
except gspread.exceptions.WorksheetNotFound:
    aba_logs = spreadsheet.add_worksheet(title="Logs", rows="1000", cols="5")
    aba_logs.append_row(["Data", "Quantidade de carrinhos recebidos", "Quantidade adicionados", "Quantidade ignorados", "Erro?"])

from datetime import datetime

data_execucao = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
qtd_recebidos = len(carts_data)
qtd_ignorados = len([c for c in carts_data if str(c.get("id")) in ids_existentes])
qtd_adicionados = qtd_recebidos - qtd_ignorados
houve_erro = "Sim" if qtd_recebidos == 0 else "Não"

# Escreve o log na planilha
aba_logs.append_row([data_execucao, qtd_recebidos, qtd_adicionados, qtd_ignorados, houve_erro])

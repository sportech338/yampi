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
DOMINIO_LOJA = "seguro.lojasportech.com"

# Fuso horário de São Paulo
tz = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(tz)

# Intervalo do dia anterior no fuso de São Paulo
ontem_inicio = tz.localize(datetime.combine((agora - timedelta(days=1)).date(), datetime.min.time()))
ontem_fim = tz.localize(datetime.combine((agora - timedelta(days=1)).date(), datetime.max.time()))

# URL base da API (sem export)
BASE_URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"
headers = {
    "User-token": TOKEN,
    "User-Secret-Key": SECRET_KEY,
    "Accept": "application/json"
}

# Paginação: busca todas as páginas de carrinhos
carts_data = []
page = 1
while True:
    paginated_url = f"{BASE_URL}?page={page}"
    try:
        response = requests.get(paginated_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            break
        carts_data.extend(data)
        print(f"📄 Página {page} carregada com {len(data)} carrinhos.")
        page += 1
    except Exception as e:
        print(f"❌ Erro ao buscar página {page} da Yampi: {e}")
        break

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

# Buscar carrinhos já adicionados
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

# Filtrar carrinhos com updated_at de ontem
carrinhos_filtrados = []
for cart in carts_data:
    updated_at = cart.get("updated_at")
    if isinstance(updated_at, dict):
        data_str = updated_at.get("date")
        if data_str:
            try:
                dt = tz.localize(datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S.%f"))
                if ontem_inicio <= dt <= ontem_fim:
                    carrinhos_filtrados.append(cart)
            except Exception as e:
                print(f"⚠️ Erro ao converter data do carrinho {cart.get('id')}: {e}")

print(f"🛒 Carrinhos filtrados para o dia anterior: {len(carrinhos_filtrados)}")

# Enviar para planilha
adicionados = 0
ignorados = 0

for cart in carrinhos_filtrados:
    try:
        cart_id = str(cart.get("id"))
        token = cart.get("token", "")

        if cart_id in ids_existentes:
            ignorados += 1
            print(f"⚠️ Carrinho {cart_id} já existe na planilha. Ignorado.")
            continue

        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido")
        customer_email = tracking.get("email", "Sem email")

        cart_json_str = json.dumps(cart)
        cpf = extrair_cpf(cart_json_str)
        telefone = extrair_telefone(cart_json_str)
        telefone_formatado = formatar_telefone(telefone)

        items_data = cart.get("items", {}).get("data", [])
        if items_data:
            first_item = items_data[0]
            product_name = first_item.get("sku", {}).get("data", {}).get("title", "Sem título")
            quantity = first_item.get("quantity", 1)
        else:
            product_name = "Sem produto"
            quantity = 0

        total = cart.get("totalizers", {}).get("total", 0)
        link_checkout = f"https://{DOMINIO_LOJA}/cart?cart_token={token}" if token else "Não encontrado"
        abandonou_em = cart.get("abandoned_step", "Desconhecido")

        # Agora com o campo "abandonou_em"
        sheet.append_row([
            cart_id,
            customer_name,
            customer_email,
            cpf,
            telefone_formatado or "Não encontrado",
            product_name,
            quantity,
            total,
            link_checkout,
            abandonou_em
        ])

        print(f"✅ Carrinho {cart_id} adicionado com sucesso.")
        adicionados += 1

    except Exception as e:
        print(f"❌ Erro ao processar carrinho {cart.get('id')}: {e}")

# Logs
try:
    aba_logs = spreadsheet.worksheet("Logs")
except gspread.exceptions.WorksheetNotFound:
    aba_logs = spreadsheet.add_worksheet(title="Logs", rows="1000", cols="5")
    aba_logs.append_row(["Data", "Total do dia", "Adicionados", "Ignorados", "Erro?"])

data_execucao = agora.strftime("%d/%m/%Y %H:%M")
houve_erro = "Não" if adicionados > 0 else "Sim"

aba_logs.append_row([data_execucao, len(carrinhos_filtrados), adicionados, ignorados, houve_erro])

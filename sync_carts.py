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
    print(f"📦 Total de carrinhos retornados pela Yampi: {len(carts_data)}")
else:
    print("❌ Erro ao buscar carrinhos:", response.status_code)
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

# Domínio do checkout
dominio_loja = "seguro.lojasportech.com"

# Fuso horário do Brasil
fuso_sp = pytz.timezone("America/Sao_Paulo")

# Intervalo de ontem no fuso de São Paulo
agora_sp = datetime.now(fuso_sp)
ontem_sp_inicio = (agora_sp - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
ontem_sp_fim = ontem_sp_inicio + timedelta(days=1)

# Converte os limites de São Paulo para UTC
ontem_inicio_utc = ontem_sp_inicio.astimezone(pytz.UTC)
ontem_fim_utc = ontem_sp_fim.astimezone(pytz.UTC)

# Lista dos carrinhos válidos
carrinhos_filtrados = []

print("\n📋 DEBUG DAS DATAS DOS CARRINHOS:")

for cart in carts_data:
    cart_id = cart.get("id")
    abandoned_str = cart.get("abandoned_at")
    updated_raw = cart.get("updated_at")

    print(f"- Carrinho ID {cart_id}")
    print(f"  abandoned_at: {abandoned_str}")
    print(f"  updated_at:   {updated_raw}")

    abandoned_at = None
    updated_at = None
    motivo = ""
    data_ref = None

    try:
        if abandoned_str:
            abandoned_at = datetime.fromisoformat(abandoned_str.replace("Z", "+00:00"))
            if ontem_inicio_utc <= abandoned_at < ontem_fim_utc:
                motivo = "abandonado"
                data_ref = abandoned_at

        if isinstance(updated_raw, dict) and "date" in updated_raw and not data_ref:
            updated_str = updated_raw["date"]
            updated_naive = datetime.strptime(updated_str, "%Y-%m-%d %H:%M:%S.%f")
            updated_local = fuso_sp.localize(updated_naive)
            updated_at = updated_local.astimezone(pytz.UTC)

            if ontem_inicio_utc <= updated_at < ontem_fim_utc:
                motivo = "modificado"
                data_ref = updated_at

        if data_ref:
            carrinhos_filtrados.append((cart, data_ref, motivo))

    except Exception as e:
        print(f"  ⚠️ Erro ao processar datas do carrinho {cart_id}: {e}")

# LOG final
print(f"\n📅 Carrinhos abandonados ou modificados em {ontem_sp_inicio.date()} (horário de São Paulo): {len(carrinhos_filtrados)}")

if len(carrinhos_filtrados) == 0:
    print("ℹ️ Nenhum carrinho será enviado para a planilha.")
else:
    print("🚀 Enviando carrinhos para a planilha...\n")

# Envia para o Google Sheets
for cart, data_ref, motivo in carrinhos_filtrados:
    try:
        cart_id = cart.get("id")
        token = cart.get("token", "")

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

        link_checkout = f"https://{dominio_loja}/cart?cart_token={token}" if token else "Não encontrado"

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

        print(f"✅ Carrinho {cart_id} ({motivo} às {data_ref.strftime('%H:%M')}) adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("❌ Erro ao processar um carrinho:")
        traceback.print_exc()

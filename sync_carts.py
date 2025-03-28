import requests
import gspread
from google.oauth2.service_account import Credentials
import os
import json
import re
from datetime import datetime, timedelta
import pytz
import time

# CONFIGURAÇÕES
ALIAS = "sportech"
TOKEN = os.getenv("YAMPI_API_TOKEN")
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")
DOMINIO_LOJA = "seguro.lojasportech.com"

# Fuso horário de São Paulo
tz = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(tz)

# Limites: carrinhos de hoje e abandonados há pelo menos 10 minutos
inicio_hoje = tz.localize(datetime.combine(agora.date(), datetime.min.time()))
limite_abandono = agora - timedelta(minutes=10)

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
        
        # Verificando se o erro 429 foi retornado
        if response.status_code == 429:
            print("❌ Limite de requisições atingido. Aguardando 60 segundos...")
            time.sleep(60)  # Pausa de 60 segundos para evitar o erro 429
            continue
        
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            break
        carts_data.extend(data)
        print(f"📄 Página {page} carregada com {len(data)} carrinhos.")
        page += 1
        time.sleep(1)  # Pausa de 1 segundo entre as requisições para evitar atingir o limite

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
telefones_existentes = [str(row[5]) for row in sheet.get_all_values()[1:] if len(row) > 5 and row[5]]

# Funções auxiliares
def extrair_cpf(cart):
    try:
        cpf = cart.get("customer", {}).get("data", {}).get("cpf")
        if isinstance(cpf, str):
            cpf = re.sub(r'\D', '', cpf)
            if len(cpf) == 11:
                return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    except Exception:
        pass
    return "Não encontrado"

def extrair_telefone(cart):
    try:
        telefone = cart.get("customer", {}).get("data", {}).get("phone", {}).get("full_number")
        if telefone:
            telefone = re.sub(r'\D', '', telefone)
        else:
            telefone = cart.get("spreadsheet", {}).get("data", {}).get("customer_phone", "")
            telefone = re.sub(r'\D', '', telefone)

        if not telefone:
            return ""

        if len(telefone) == 10 and telefone[2] == '9':
            telefone = telefone[:2] + '9' + telefone[2:]

        return f"0{telefone}"
    except Exception:
        return ""

# Mapeamento das etapas de abandono
etapas = {
    "personal_data": "👤 Dados pessoais",
    "shipping": "🚞 Entrega",
    "shippment": "🚞 Entrega",
    "entrega": "🚞 Entrega",
    "payment": "💳 Pagamento",
    "pagamento": "💳 Pagamento"
}

# Filtrar carrinhos válidos
carrinhos_filtrados = []
for cart in carts_data:
    updated_at = cart.get("updated_at")
    if isinstance(updated_at, dict):
        data_str = updated_at.get("date")
        if data_str:
            try:
                try:
                    dt = tz.localize(datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S.%f"))
                except ValueError:
                    dt = tz.localize(datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S"))

                if inicio_hoje <= dt <= limite_abandono:
                    transacoes = cart.get("transactions", {}).get("data", [])
                    tem_transacao_aprovada = any(t.get("status") == "paid" for t in transacoes)
                    if tem_transacao_aprovada:
                        print(f"⛔ Carrinho {cart.get('id')} ignorado (transação aprovada).")
                        continue
                    cart["data_atualizacao"] = dt.strftime("%d/%m/%Y %H:%M")
                    carrinhos_filtrados.append(cart)
            except Exception as e:
                print(f"⚠️ Erro ao converter data do carrinho {cart.get('id')}: {e}")

print(f"🧲 Carrinhos filtrados prontos para planilha: {len(carrinhos_filtrados)}")

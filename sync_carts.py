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

# Limites: carrinhos de hoje e abandonados há pelo menos 15 minutos
inicio_hoje = tz.localize(datetime.combine(agora.date(), datetime.min.time()))
limite_abandono = agora - timedelta(minutes=15)

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
ids_existentes = [str(row[1]) for row in sheet.get_all_values()[1:] if row]

# Funções auxiliares
def extrair_cpf(cart):
    cpfs_encontrados = set()
    caminhos_possiveis = [
        ("customer", "document"),
        ("customer_data", "document"),
        ("customer_data", "data", "document"),
        ("customer", "data", "document")
    ]
    for caminho in caminhos_possiveis:
        try:
            valor = cart
            for chave in caminho:
                valor = valor.get(chave, {})
            if isinstance(valor, str):
                cpf_limpo = re.sub(r'\D', '', valor)
                if len(cpf_limpo) == 11:
                    cpfs_encontrados.add(cpf_limpo)
        except Exception:
            continue

    if not cpfs_encontrados:
        json_text = json.dumps(cart)
        matches = re.findall(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', json_text)
        for match in matches:
            cpf = re.sub(r'\D', '', match)
            if len(cpf) == 11:
                cpfs_encontrados.add(cpf)

    for cpf in cpfs_encontrados:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return "Não encontrado"

def extrair_telefone(cart):
    caminhos_possiveis = [
        ("customer", "phone"),
        ("customer_data", "phone"),
        ("customer_data", "data", "phone"),
        ("customer", "data", "phone")
    ]
    numeros = []

    for caminho in caminhos_possiveis:
        try:
            valor = cart
            for chave in caminho:
                valor = valor.get(chave, {})
            if isinstance(valor, str):
                digitos = re.sub(r'\D', '', valor)
                if 10 <= len(digitos) <= 11:
                    numeros.append(digitos)
        except Exception:
            continue

    if not numeros:
        json_text = json.dumps(cart)
        matches = re.findall(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', json_text)
        for numero in matches:
            apenas_digitos = re.sub(r'\D', '', numero)
            if 10 <= len(apenas_digitos) <= 11:
                numeros.append(apenas_digitos)

    for num in numeros:
        if len(num) == 11:
            return num
    if numeros:
        return numeros[0]
    return ""

def formatar_telefone(numero):
    digitos = re.sub(r'\D', '', numero)
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    elif len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return ""

# Mapeamento das etapas de abandono
etapas = {
    "personal_data": "🙋‍♂️ Dados pessoais",
    "shipping": "📦 Entrega",
    "shippment": "📦 Entrega",
    "entrega": "📦 Entrega",
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

print(f"🧮 Carrinhos filtrados prontos para planilha: {len(carrinhos_filtrados)}")

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

        cpf = extrair_cpf(cart)
        telefone = extrair_telefone(cart)
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

        abandonou_em = "🙋‍♂️ Dados pessoais"
        for origem in [
            cart.get("abandoned_step"),
            cart.get("spreadsheet", {}).get("data", {}).get("abandoned_step"),
            cart.get("search", {}).get("data", {}).get("abandoned_step")
        ]:
            if origem:
                etapa = etapas.get(origem.strip().lower())
                if etapa and etapa in ["📦 Entrega", "💳 Pagamento"]:
                    abandonou_em = etapa
                    break

        data_abandono_str = cart.get("data_atualizacao", "Não encontrado")

        sheet.insert_row([
            data_abandono_str,
            cart_id,
            customer_name,
            customer_email,
            cpf,
            telefone_formatado or "Não encontrado",
            product_name,
            quantity,
            total,
            abandonou_em,
            link_checkout
        ], index=2)

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

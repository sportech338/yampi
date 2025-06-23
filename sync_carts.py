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
SPREADSHEET_ID = '1OBKs2RpmRNqHDn6xE3uMOU-bwwnO_JY1ZhqctZGpA3E'
MINUTOS_ATE_CONSIDERAR_ABANDONO = 20

# Fuso horário
tz = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(tz)
inicio_hoje = tz.localize(datetime.combine(agora.date(), datetime.min.time()))
limite_abandono = agora - timedelta(minutes=MINUTOS_ATE_CONSIDERAR_ABANDONO)

# API Yampi
BASE_URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"
headers = {
    "User-token": TOKEN,
    "User-Secret-Key": SECRET_KEY,
    "Accept": "application/json"
}

# Paginação de carrinhos
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

# Google Sheets
descoped_credentials = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(descoped_credentials, scopes=scope)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.sheet1

# Nomes existentes
valores_planilha = sheet.get_all_values()[1:]
nomes_existentes = {linha[3].strip().lower() for linha in valores_planilha if len(linha) >= 4}

def extrair_telefone(texto):
    matches = re.findall(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', texto)
    for numero in matches:
        apenas_digitos = re.sub(r'\D', '', numero)
        if len(apenas_digitos) in [10, 11] and not re.match(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', numero):
            ddd = apenas_digitos[:2]
            telefone = apenas_digitos[2:]
            if len(telefone) == 8:
                telefone = '9' + telefone
            numero_formatado = f"0{ddd}{telefone}"
            if numero_formatado.count(numero_formatado[1]) == len(numero_formatado) - 1:
                return ""
            return numero_formatado
    return ""

etapas = {
    "personal_data": "🧛‍♂️ Dados pessoais",
    "shipping": "🚎 Entrega",
    "shippment": "🚎 Entrega",
    "entrega": "🚎 Entrega",
    "payment": "💳 Pagamento",
    "pagamento": "💳 Pagamento"
}

# Filtrar carrinhos
carrinhos_filtrados = []
for cart in carts_data:
    try:
        updated_at = cart.get("updated_at", {}).get("date")
        if updated_at:
            try:
                dt = tz.localize(datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%f"))
            except:
                dt = tz.localize(datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S"))

            if inicio_hoje <= dt <= limite_abandono:
                if any(t.get("status") == "paid" for t in cart.get("transactions", {}).get("data", [])):
                    continue
                cart["data_atualizacao"] = dt.strftime("%d/%m/%Y %H:%M")
                carrinhos_filtrados.append(cart)
    except Exception as e:
        print(f"⚠️ Erro ao processar data: {e}")

# Coletar pedidos cancelados
orders_cancelados = []
page = 1
while True:
    url = f"https://api.dooki.com.br/v2/{ALIAS}/orders?status=cancelled&page={page}"
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
        print(f"📄 Página {page} de pedidos cancelados carregada.")
        page += 1
    except Exception as e:
        print(f"❌ Erro ao buscar pedidos cancelados página {page}: {e}")
        break

# Inserir dados na planilha
linhas_para_inserir = []
adicionados = 0
ignorados = 0
houve_erro_real = False

# Carrinhos abandonados
for cart in carrinhos_filtrados:
    try:
        token = cart.get("token", "")
        link_checkout = f"https://{DOMINIO_LOJA}/cart?cart_token={token}" if token else "Não encontrado"

        tracking = cart.get("tracking_data", {})
        customer_name = tracking.get("name", "Desconhecido").strip()
        nome_normalizado = customer_name.lower()

        if nome_normalizado in nomes_existentes:
            ignorados += 1
            continue

        email = tracking.get("email", "Sem email")
        telefone = extrair_telefone(json.dumps(cart))
        items = cart.get("items", {}).get("data", [])
        item = items[0] if items else {}
        produto = item.get("sku", {}).get("data", {}).get("title", "Sem título")
        quantidade = item.get("quantity", 1)
        total = cart.get("totalizers", {}).get("total", 0)

        abandonou_em = "🧛‍♂️ Dados pessoais"
        for chave in [
            cart.get("abandoned_step"),
            cart.get("spreadsheet", {}).get("data", {}).get("abandoned_step"),
            cart.get("search", {}).get("data", {}).get("abandoned_step")
        ]:
            etapa = etapas.get(str(chave).strip().lower())
            if etapa in ["🚎 Entrega", "💳 Pagamento"]:
                abandonou_em = etapa
                break

        linhas_para_inserir.append([
            cart.get("data_atualizacao", ""), "", "Carrinho abandonado", customer_name,
            email, telefone or "Não encontrado", produto,
            quantidade, total, abandonou_em, "", "", "", "", link_checkout, ""
        ])
        adicionados += 1

    except Exception as e:
        houve_erro_real = True
        print(f"❌ Erro ao processar carrinho {cart.get('id')}: {e}")

# Pedidos cancelados
for order in orders_cancelados:
    try:
        nome = order.get("customer", {}).get("name", "Desconhecido")
        nome_normalizado = nome.lower()
        if nome_normalizado in nomes_existentes:
            ignorados += 1
            continue

        email = order.get("customer", {}).get("email", "Sem email")
        telefone = extrair_telefone(json.dumps(order))
        item = order.get("items", [{}])[0]
        produto = item.get("title", "Sem título")
        qtd = item.get("quantity", 1)
        total = order.get("total", 0)

        linhas_para_inserir.append([
            order.get("data_cancelamento", ""), "", "Pedido cancelado", nome,
            email, telefone or "Não encontrado", produto,
            qtd, total, "❌ Cancelado", "", "", "", "", "", ""
        ])
        adicionados += 1

    except Exception as e:
        houve_erro_real = True
        print(f"❌ Erro ao processar pedido cancelado {order.get('id')}: {e}")

# Inserir na planilha
if linhas_para_inserir:
    sheet.insert_rows(linhas_para_inserir, row=2)
    print(f"✅ {adicionados} linhas adicionadas.")

# Logs
try:
    aba_logs = spreadsheet.worksheet("Logs")
except gspread.exceptions.WorksheetNotFound:
    aba_logs = spreadsheet.add_worksheet(title="Logs", rows="1000", cols="5")
    aba_logs.append_row(["Data", "Total do dia", "Adicionados", "Ignorados", "Erro?"])

data_execucao = agora.strftime("%d/%m/%Y %H:%M")
houve_erro = "Sim" if houve_erro_real else "Não"

total_do_dia = len(carrinhos_filtrados) + len(orders_cancelados)
aba_logs.append_row([data_execucao, total_do_dia, adicionados, ignorados, houve_erro])

# Print final
print(f"""
📜 LOG DE EXECUÇÃO

🗓️ Data de execução: {data_execucao}
📦 Carrinhos filtrados: {len(carrinhos_filtrados)}
📦 Pedidos cancelados: {len(orders_cancelados)}
✅ Linhas adicionadas: {adicionados}
🔀 Linhas ignoradas (já estavam na planilha): {ignorados}
❗ Houve erro? {houve_erro}
""")

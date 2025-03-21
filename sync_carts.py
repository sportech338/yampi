import os
import requests
import datetime
import gspread
from google.oauth2.service_account import Credentials

# Credenciais da API Yampi (obtidas do ambiente para segurança)
YAMPI_ALIAS = os.getenv("YAMPI_ALIAS")  # alias da loja na Yampi (substitua pelo seu alias, se necessário)
YAMPI_USER_TOKEN = os.getenv("YAMPI_USER_TOKEN")
YAMPI_SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")

if not YAMPI_USER_TOKEN or not YAMPI_SECRET_KEY or not YAMPI_ALIAS:
    raise EnvironmentError("Credenciais da API Yampi não definidas nas variáveis de ambiente.")

# Cabeçalhos de autenticação na Yampi API
headers = {
    "User-Token": YAMPI_USER_TOKEN,
    "User-Secret-Key": YAMPI_SECRET_KEY,
    "Content-Type": "application/json"
}

# Determina a data de ontem (dia anterior)
hoje = datetime.date.today()
ontem = hoje - datetime.timedelta(days=1)
ontem_str = ontem.strftime("%Y-%m-%d")  # formata em AAAA-MM-DD

# Monta a URL base para listar carrinhos abandonados
base_url = f"https://api.dooki.com.br/v2/{YAMPI_ALIAS}/carts"

# Lista para acumular os registros (linhas) a serem inseridos
linhas_para_inserir = []

# Paginação da API Yampi (limite de 100 por requisição conforme doc)
page = 1
mais_paginas = True

while mais_paginas:
    # Requisição dos carrinhos abandonados (página atual)
    url = f"{base_url}?limit=100&page={page}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        # Em caso de erro na chamada da API, encerra o script apropriadamente
        raise Exception(f"Erro ao chamar API Yampi: {response.status_code} - {response.text}")
    data = response.json()
    # Se a resposta vier envolvida em um campo "data"
    carts = data.get("data", data)  # alguns endpoints retornam {"data": [...]} 
    if not isinstance(carts, list):
        carts = [carts]
    if not carts:
        break  # sem resultados nesta página, saí do loop
    
    # Processa cada carrinho retornado
    for cart in carts:
        # Extrai data de atualização e verifica se é de ontem
        updated_info = cart.get("updated_at")
        if updated_info:
            # O updated_at pode vir como string ou como objeto com 'date'
            if isinstance(updated_info, dict) and "date" in updated_info:
                updated_date_str = updated_info["date"][:10]
            else:
                # Se for string no formato ISO ou similar
                updated_date_str = str(updated_info)[:10]
        else:
            updated_date_str = ""
        # Compara com a data de ontem
        if updated_date_str != ontem_str:
            continue  # pula carrinhos que não sejam do dia anterior
        
        # Extrai campos do cliente
        nome = cart.get("customer_name") or cart.get("name") or ""
        # Alguns objetos podem ter first_name/last_name separados
        if not nome:
            first = cart.get("first_name") or ""
            last = cart.get("last_name") or ""
            nome = f"{first} {last}".strip()
        email = cart.get("customer_email") or cart.get("email") or ""
        # Telefone: combinar código do país + DDD + número
        telefone_completo = ""
        whatsapp_link = ""
        phone_data = cart.get("phone") or cart.get("customer_phone") or cart.get("customer", {}).get("phone")
        if phone_data:
            # Se a API fornecer formatado, usamos, senão formatamos nós mesmos
            if isinstance(phone_data, dict):
                area = phone_data.get("area_code") or ""
                num = phone_data.get("number") or ""
                formatted = phone_data.get("formated_number") or phone_data.get("formatted_number")
                if formatted:
                    # Garante que tenha o formato (DD) XXXXX-XXXX
                    telefone_completo = f"+55 {formatted}"
                else:
                    # Formata manualmente se possível
                    if area and num:
                        # Formata com separador de telefone brasileiro
                        if len(num) >= 9:
                            telefone_completo = f"+55 ({area}) {num[:-4]}-{num[-4:]}"
                        else:
                            telefone_completo = f"+55 ({area}) {num}"
                    else:
                        telefone_completo = f"+55 {area}{num}"
            else:
                # Se phone_data não for dict (caso raro), usa como string direta
                telefone_completo = str(phone_data)
            # Remove espaços e caracteres não numéricos para o link WhatsApp
            digits = "".join(filter(str.isdigit, telefone_completo))
            if digits.startswith("55"):
                whatsapp_link = f"https://wa.me/{digits}"
            else:
                # garante código do país
                whatsapp_link = f"https://wa.me/55{digits}"
        else:
            telefone_completo = ""
            whatsapp_link = ""
        
        # CPF do cliente (armazenar no campo "ip" da planilha, se disponível)
        cpf = cart.get("cpf") or cart.get("customer_cpf") or cart.get("customer", {}).get("cpf") or ""
        # Se CPF vier formatado (com pontos/traço), mantém como está. Se for número puro, podemos formatar se necessário.
        
        # Etapa em que abandonou e serviço de envio
        abandoned_step = cart.get("abandoned_step") or ""
        shipping_service = cart.get("shipping_service") or ""
        
        # Links de simulação e compra
        simulate_url = cart.get("simulate_url") or ""
        purchase_url = cart.get("purchase_url") or ""
        
        # Data/hora da última atualização (como string legível)
        # Podemos usar o próprio updated_info já obtido antes:
        updated_at_str = ""
        if updated_info:
            if isinstance(updated_info, dict) and "date" in updated_info:
                updated_at_str = updated_info["date"]
            else:
                updated_at_str = str(updated_info)
        
        # Monta a lista de campos na ordem especificada
        linha = [
            cart.get("id") or cart.get("cart_id") or "",   # cart_id
            nome,                                         # customer_name
            email,                                        # customer_email
            telefone_completo,                            # customer_phone (com código do país e DDD)
            whatsapp_link,                                # whatsapp_link
            cpf,                                          # CPF do cliente (coluna "ip" na planilha)
            abandoned_step,                               # abandoned_step
            shipping_service,                             # shipping_service
            simulate_url,                                 # simulate_url
            purchase_url,                                 # purchase_url
            updated_at_str                                # updated_at
        ]
        linhas_para_inserir.append(linha)
    # Verifica se deve continuar para a próxima página
    # Se menos de 100 resultados foram retornados, provavelmente não há mais páginas
    if len(carts) < 100:
        mais_paginas = False
    else:
        page += 1

# Autenticação no Google Sheets usando as credenciais do serviço
credentials = Credentials.from_service_account_file(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
client = gspread.authorize(credentials)

# Abrindo a planilha pelo ID (substitua pelo seu ID ou use variável de ambiente)
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")  # ID da planilha Google (como no URL da planilha)
if not GOOGLE_SHEET_ID:
    raise EnvironmentError("ID da planilha do Google Sheets não especificado.")
sheet = client.open_by_key(GOOGLE_SHEET_ID)

# Seleciona a primeira aba da planilha (ou especifique por nome se necessário)
worksheet = sheet.get_worksheet(0)

# Inserção das linhas na planilha
if linhas_para_inserir:
    worksheet.append_rows(linhas_para_inserir, value_input_option="USER_ENTERED")
else:
    print("Nenhum carrinho abandonado encontrado para o dia anterior.")

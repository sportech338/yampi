import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import os

# Função para autenticar com o Google Sheets usando a chave de serviço
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")  # Usando a variável de ambiente
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    return client

# Função para obter os carrinhos abandonados via API
def get_abandoned_carts():
    url = "https://api.dooki.com.br/v2/sportech/checkout/carts"
    headers = {
        "Authorization": f"Bearer {os.getenv('YAMPI_API_TOKEN')}"  # Usando a variável de ambiente para o token
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()  # Retorna os dados dos carrinhos abandonados
    else:
        print(f"Erro ao obter os carrinhos abandonados. Código de status: {response.status_code}")
        return None

# Função para salvar os dados no Google Sheets
def save_to_google_sheets(carts_data):
    client = authenticate_google_sheets()

    # Abra a planilha pelo nome ou crie uma nova
    try:
        sheet = client.open("Carrinhos Abandonados").sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        sheet = client.create("Carrinhos Abandonados").sheet1

    # Defina os cabeçalhos da planilha
    headers = ["ID do Carrinho", "Nome do Cliente", "Email", "Telefone", "Produtos", "Total", "Status de Pagamento"]
    sheet.append_row(headers)

    # Adicionar cada carrinho na planilha
    for cart in carts_data:
        cart_id = cart['id']
        customer_name = cart['tracking_data']['name']
        customer_email = cart['tracking_data']['email']
        customer_phone = cart['tracking_data']['phone']['formated_number']
        products = ", ".join([item['sku']['title'] for item in cart['items']['data']])
        total = cart['totalizers']['total']
        payment_status = cart['last_transaction_status']['alias'] if cart['last_transaction_status'] else "Não realizado"

        row = [cart_id, customer_name, customer_email, customer_phone, products, total, payment_status]
        sheet.append_row(row)

# Função principal
def main():
    carts_data = get_abandoned_carts()
    if carts_data:
        save_to_google_sheets(carts_data['data'])
        print("Dados exportados com sucesso para o Google Sheets!")
    else:
        print("Nenhum dado encontrado ou erro ao obter dados.")

if __name__ == "__main__":
    main()

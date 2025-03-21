import requests
import json
import os

# CONFIGURAÇÕES
ALIAS = "sportech"  # Substitua pelo alias da sua loja
TOKEN = os.getenv("YAMPI_API_TOKEN")  # Token da Yampi vindo dos secrets
SECRET_KEY = os.getenv("YAMPI_SECRET_KEY")  # Chave secreta da Yampi vinda dos secrets

# URL da API (endpoint para obter carrinhos abandonados)
URL = f"https://api.dooki.com.br/v2/{ALIAS}/checkout/carts"

# Definindo os cabeçalhos corretos para autenticação
headers = {
    "User-token": TOKEN,           # Token da Yampi
    "User-Secret-Key": SECRET_KEY, # Chave secreta da Yampi
    "Accept": "application/json"
}

# Realizando a requisição para a API Yampi
response = requests.get(URL, headers=headers)

# Se a resposta for bem-sucedida (status 200)
if response.status_code == 200:
    carts_data = response.json().get("data", [])
    print(f"Carrinhos abandonados: {carts_data}")
else:
    print("Erro ao buscar carrinhos:", response.status_code)
    print(response.text)

# ... (mantém todas as importações e configurações anteriores)

# Timezone São Paulo
tz_sp = pytz.timezone("America/Sao_Paulo")
hoje_sp = datetime.now(tz_sp).date()
ontem_sp = hoje_sp - timedelta(days=1)

# 🔄 Lê todos os IDs já inseridos na planilha para evitar duplicações
print("🔍 Buscando carrinhos já existentes na planilha para evitar duplicações...")
try:
    ids_existentes = set()
    valores = sheet.get_all_values()
    for row in valores[1:]:  # pula o cabeçalho
        if row and row[0].isdigit():
            ids_existentes.add(int(row[0]))
    print(f"🔒 {len(ids_existentes)} carrinhos já estão na planilha.")
except Exception as e:
    print("⚠️ Não foi possível verificar carrinhos existentes. Continuando sem filtro de duplicatas.")
    ids_existentes = set()

# Loop dos carrinhos
for cart in carts_data:
    try:
        updated_at_raw = cart.get("updated_at", {})
        updated_at_str = updated_at_raw.get("date")
        if not updated_at_str:
            continue

        try:
            updated_at_sp = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            updated_at_sp = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")

        updated_at_sp = tz_sp.localize(updated_at_sp)
        data_cart = updated_at_sp.date()
        if data_cart != ontem_sp:
            continue

        # Verifica duplicata
        cart_id = cart.get("id")
        if cart_id in ids_existentes:
            print(f"⏩ Carrinho {cart_id} já está na planilha. Pulando.")
            continue

        token = cart.get("token", "")
        print(f"\n🛒 CARRINHO ID: {cart_id}")
        print(f"🔐 TOKEN: {token}")
        print(f"🕒 Atualizado em: {updated_at_sp.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"🔗 LINK GERADO: https://{dominio_loja}/cart?cart_token={token}")
        print("📦 CONTEÚDO DO CARRINHO:")
        print(json.dumps(cart, indent=2, ensure_ascii=False)[:2000])

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
            link_checkout,
            updated_at_sp.strftime("%d/%m/%Y %H:%M:%S")
        ])

        print(f"✅ Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("❌ Erro ao processar um carrinho:")
        traceback.print_exc()

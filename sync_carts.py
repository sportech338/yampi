# Controlar duplicados no mesmo run
carrinhos_adicionados_hoje = set()

# Loop dos carrinhos
for cart in carts_data:
    try:
        cart_id = cart.get("id")
        if cart_id in ids_existentes or cart_id in carrinhos_adicionados_hoje:
            print(f"⏩ Carrinho {cart_id} já registrado. Pulando.")
            continue

        carrinhos_adicionados_hoje.add(cart_id)  # Marca como salvo nesta execução

        token = cart.get("token", "")
        print(f"\n🛒 CARRINHO ID: {cart_id}")
        print(f"🔐 TOKEN: {token}")
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
            link_checkout
        ])

        print(f"✅ Carrinho {cart_id} adicionado com sucesso.")

    except Exception as e:
        import traceback
        print("❌ Erro ao processar um carrinho:")
        traceback.print_exc()

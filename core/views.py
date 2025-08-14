# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Sale, SaleItem
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib import messages

def product_list(request):
    products = Product.objects.all() # Pega todos os produtos do banco de dados
    context = {
        'products': products
    }
    return render(request, 'core/product_list.html', context)

@require_POST # Garante que esta view só aceite requisições POST
def add_to_cart(request):
    product_id = request.POST.get("product_id")
    quantity = int(request.POST.get("quantity", 1)) # Pega a quantidade, padrão 1

    product = get_object_or_404(Product, id=product_id)

    cart = request.session.get("cart", {}) # Pega o carrinho da sessão ou cria um vazio

    # Adiciona ou atualiza o produto no carrinho
    # O carrinho será um dicionário: {"product_id": quantidade}
    cart_item_quantity = cart.get(str(product.id), 0) # Pega a quantidade atual do item no carrinho
    cart_item_quantity += quantity # Adiciona a nova quantidade

    # Garante que a quantidade não exceda o estoque disponível
    if cart_item_quantity > product.stock:
        messages.error(request, f"Not enough stock for {product.name}. Added maximum available: {product.stock}.")
        cart_item_quantity = product.stock # Limita à quantidade em estoque

    cart[str(product.id)] = cart_item_quantity

    request.session["cart"] = cart # Salva o carrinho de volta na sessão
    request.session.modified = True # Informa ao Django que a sessão foi modificada

    return redirect("product_list") # Redireciona de volta para a lista de produtos

def cart_detail(request):
    cart = request.session.get("cart", {}) # Pega o carrinho da sessão
    cart_items = []
    total_price = 0

    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        item_price = product.price * quantity
        total_price += item_price
        cart_items.append({
            "product": product,
            "quantity": quantity,
            "item_price": item_price
        })

    context = {
        "cart_items": cart_items,
        "total_price": total_price
    }
    return render(request, "core/cart_detail.html", context)



@require_POST
def checkout(request):
    cart = request.session.get("cart", {}) # Pega o carrinho da sessão

    if not cart: # Se o carrinho estiver vazio, redireciona
        return redirect("product_list")

    try:
        with transaction.atomic(): # Garante que todas as operações sejam bem-sucedidas ou nenhuma seja
            total_price = 0
            sale_items_to_create = []
            products_to_update = []

            # Primeiro, verifica estoque e calcula o total
            for product_id, quantity in cart.items():
                product = get_object_or_404(Product, id=product_id)

                if product.stock < quantity:
                    # Se o estoque for insuficiente, levanta um erro
                    # Opcional: Adicionar uma mensagem de erro para o usuário
                    # from django.contrib import messages
                    # messages.error(request, f"Estoque insuficiente para {product.name}.")
                    raise ValueError(f"Estoque insuficiente para {product.name}.")

                item_price = product.price * quantity
                total_price += item_price

                # Prepara os dados para criar SaleItem
                sale_items_to_create.append({
                    "product": product,
                    "quantity": quantity,
                    "price_at_time_of_sale": product.price # Usa o preço atual do produto
                })

                # Prepara o produto para atualização de estoque
                product.stock -= quantity
                products_to_update.append(product)

            # Cria a venda principal
            sale = Sale.objects.create(total_price=total_price)

            # Cria os itens da venda
            for item_data in sale_items_to_create:
                SaleItem.objects.create(
                    sale=sale,
                    product=item_data["product"],
                    quantity=item_data["quantity"],
                    price_at_time_of_sale=item_data["price_at_time_of_sale"]
                )

            # Atualiza o estoque dos produtos
            for product in products_to_update:
                product.save()

        # Limpa o carrinho da sessão após a venda ser bem-sucedida
        del request.session["cart"]
        request.session.modified = True

        return redirect("checkout_success") # Redireciona para uma página de sucesso

    except ValueError as e:
        messages.error(request, str(e))
        return redirect("cart_detail")
    except Exception as e:
        messages.error(request, "An unexpected error occurred while processing your order.")
        return redirect("cart_detail")

def checkout_success(request):
    return render(request, "core/checkout_success.html")

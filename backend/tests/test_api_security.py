
from app.core.config import settings


API = settings.api_v1_prefix


def product_payload():
    return {
        "category_id": 1,
        "name": "Test Sardine",
        "slug": "test-sardine",
        "description": "Test product",
        "price_per_kg": "150.00",
        "is_active": True,
    }


def category_payload():
    return {
        "name": "Test Fish",
        "slug": "test-fish",
        "description": "Test category",
        "is_active": True,
    }


def inventory_payload():
    return {
        "product_id": 1,
        "available_weight_kg": "10.000",
    }


def test_public_product_and_category_lists(client):
    assert client.get(f"{API}/products/").status_code == 200
    assert client.get(f"{API}/categories/").status_code == 200


def test_customer_can_read_own_profile(client, customer_headers):
    response = client.get(
        f"{API}/auth/me",
        headers=customer_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == 100
    assert response.json()["email"] == "customer@example.com"


def test_customer_cart_is_created_on_first_access(
    client,
    customer_headers,
):
    first_response = client.post(
        f"{API}/cart/100",
        headers=customer_headers,
    )
    second_response = client.post(
        f"{API}/cart/100",
        headers=customer_headers,
    )

    assert first_response.status_code == 200
    assert first_response.json()["items"] == []
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]


def test_anonymous_write_requests_are_rejected(client):
    product_response = client.post(
        f"{API}/products/",
        json=product_payload(),
    )
    category_response = client.post(
        f"{API}/categories/",
        json=category_payload(),
    )
    inventory_response = client.post(
        f"{API}/inventory/",
        json=inventory_payload(),
    )

    assert product_response.status_code == 401
    assert category_response.status_code == 401
    assert inventory_response.status_code == 401

def test_customer_cannot_manage_products(
    client,
    customer_headers,
    admin_headers,
):
    # Create a product as an admin so the product definitely exists.
    category_response = client.post(
        f"{API}/categories/",
        json=category_payload(),
        headers=admin_headers,
    )
    assert category_response.status_code == 201

    product_data = product_payload()
    product_data["category_id"] = category_response.json()["id"]
    product_data["slug"] = "security-test-product"

    product_response = client.post(
        f"{API}/products/",
        json=product_data,
        headers=admin_headers,
    )
    assert product_response.status_code == 201

    product_id = product_response.json()["id"]

    # A customer must not create a product.
    assert client.post(
        f"{API}/products/",
        json=product_payload(),
        headers=customer_headers,
    ).status_code == 403

    # A customer must not update an existing product.
    assert client.patch(
        f"{API}/products/{product_id}",
        json={"name": "Unauthorized change"},
        headers=customer_headers,
    ).status_code == 403

    # A customer must not modify product translations.
    assert client.put(
        f"{API}/products/{product_id}/translations/ta",
        json={
            "language_code": "ta",
            "name": "Test translation",
        },
        headers=customer_headers,
    ).status_code == 403

def test_customer_cannot_read_or_manage_inventory(
    client,
    customer_headers,
):
    assert client.get(
        f"{API}/inventory/1",
        headers=customer_headers,
    ).status_code == 403

    assert client.post(
        f"{API}/inventory/",
        json=inventory_payload(),
        headers=customer_headers,
    ).status_code == 403

    assert client.patch(
        f"{API}/inventory/1",
        json={"available_weight_kg": "5.000"},
        headers=customer_headers,
    ).status_code == 403


def test_admin_can_create_category_product_and_inventory(
    client,
    admin_headers,
):
    category_response = client.post(
        f"{API}/categories/",
        json=category_payload(),
        headers=admin_headers,
    )

    assert category_response.status_code == 201
    category = category_response.json()

    product_data = product_payload()
    product_data["category_id"] = category["id"]
    product_data["slug"] = "admin-test-sardine"

    product_response = client.post(
        f"{API}/products/",
        json=product_data,
        headers=admin_headers,
    )
    assert product_response.status_code == 201
    product = product_response.json()

    product_without_inventory = client.get(
        f"{API}/products/{product['id']}?language_code=en"
    )
    assert product_without_inventory.status_code == 200
    assert product_without_inventory.json()["available_weight_kg"] is None

    inventory_data = inventory_payload()
    inventory_data["product_id"] = product["id"]

    inventory_response = client.post(
        f"{API}/inventory/",
        json=inventory_data,
        headers=admin_headers,
    )

    assert inventory_response.status_code == 201

    inventory_id = product["id"]

    read_response = client.get(
        f"{API}/inventory/{inventory_id}",
        headers=admin_headers,
    )

    assert read_response.status_code == 200
    assert read_response.json()["product_id"] == product["id"]

    listed_product = client.get(
        f"{API}/products/{product['id']}?language_code=en"
    )
    assert listed_product.status_code == 200
    assert listed_product.json()["available_weight_kg"] == "10.000"

    listed_products = client.get(f"{API}/products/?language_code=en")
    matching_product = next(
        item
        for item in listed_products.json()
        if item["id"] == product["id"]
    )
    assert matching_product["available_weight_kg"] == "10.000"


def test_unknown_bearer_token_is_rejected(client):
    response = client.post(
        f"{API}/categories/",
        json=category_payload(),
        headers={"Authorization": "Bearer invalid-test-token"},
    )

    assert response.status_code == 401

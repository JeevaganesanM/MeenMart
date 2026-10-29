from app.core.config import settings

API = settings.api_v1_prefix


def create_test_category(client, admin_headers, name="Sea Fish", slug="sea-fish"):
    response = client.post(
        f"{API}/categories/",
        json={
            "name": name,
            "slug": slug,
            "description": f"Test {name} category",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def test_list_empty_products(client):
    response = client.get(f"{API}/products/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_admin_create_and_get_product(client, admin_headers):
    category = create_test_category(client, admin_headers, "Fish", "fish-cat")

    product_payload = {
        "category_id": category["id"],
        "name": "Vanjaram (Seer Fish)",
        "slug": "vanjaram-seer-fish",
        "description": "Premium king mackerel slice",
        "price_per_kg": "850.00",
        "image_url": "https://example.com/vanjaram.jpg",
        "is_active": True,
    }

    create_res = client.post(
        f"{API}/products/",
        json=product_payload,
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    product_data = create_res.json()
    assert product_data["name"] == "Vanjaram (Seer Fish)"
    assert product_data["slug"] == "vanjaram-seer-fish"

    # Get single product
    get_res = client.get(f"{API}/products/{product_data['id']}?language_code=en")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Vanjaram (Seer Fish)"


def test_get_nonexistent_product_returns_404(client):
    response = client.get(f"{API}/products/999999?language_code=en")
    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_create_product_requires_admin(client, customer_headers):
    product_payload = {
        "category_id": 1,
        "name": "Unauthorized Sardine",
        "slug": "unauthorized-sardine",
        "description": "Test",
        "price_per_kg": "120.00",
        "is_active": True,
    }

    # Anonymous request
    anon_res = client.post(f"{API}/products/", json=product_payload)
    assert anon_res.status_code == 401

    # Customer request
    cust_res = client.post(
        f"{API}/products/",
        json=product_payload,
        headers=customer_headers,
    )
    assert cust_res.status_code == 403


def test_product_translations_workflow(client, admin_headers):
    category = create_test_category(client, admin_headers, "Crabs", "crabs-cat")

    create_res = client.post(
        f"{API}/products/",
        json={
            "category_id": category["id"],
            "name": "Mud Crab",
            "slug": "mud-crab",
            "description": "Fresh mud crab",
            "price_per_kg": "650.00",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    product_id = create_res.json()["id"]

    # Add Tamil translation
    trans_res = client.put(
        f"{API}/products/{product_id}/translations/ta",
        json={
            "language_code": "ta",
            "name": "நண்டு (Mud Crab)",
            "description": "சுவையான நண்டு",
        },
        headers=admin_headers,
    )
    assert trans_res.status_code == 200
    assert trans_res.json()["name"] == "நண்டு (Mud Crab)"

    # Fetch product with Tamil language code
    localized_res = client.get(f"{API}/products/{product_id}?language_code=ta")
    assert localized_res.status_code == 200
    assert localized_res.json()["name"] == "நண்டு (Mud Crab)"

    # Search with Tamil query
    search_res = client.get(f"{API}/products/?language_code=ta&search=நண்டு")
    assert search_res.status_code == 200
    matching = [p for p in search_res.json() if p["id"] == product_id]
    assert len(matching) == 1

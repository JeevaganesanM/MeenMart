
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.address import Address
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User


API = settings.api_v1_prefix


@pytest.fixture
def order_setup(client):
    """Create valid customer records and an order through the API."""

    # Obtain the test database session from the existing override.
    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)

    try:
        customer = User(
            id=100,
            name="Test Customer",
            email="customer-order-test@example.com",
            password_hash="test-only-hash",
            role="customer",
            is_active=True,
        )
        other_customer = User(
            id=101,
            name="Other Customer",
            email="other-order-test@example.com",
            password_hash="test-only-hash",
            role="customer",
            is_active=True,
        )
        admin = User(
            id=200,
            name="Test Admin",
            email="admin-order-test@example.com",
            password_hash="test-only-hash",
            role="admin",
            is_active=True,
        )
        db.add_all([customer, other_customer, admin])
        db.flush()

        address = Address(
            user_id=100,
            recipient_name="Test Customer",
            phone="9000000000",
            address_line="1 Test Street",
            city="Coimbatore",
            postal_code="641001",
        )
        db.add(address)

        category = Category(
            name="Order Test Fish",
            slug="order-test-fish",
            description="Test category",
            is_active=True,
        )
        db.add(category)
        db.flush()

        product = Product(
            category_id=category.id,
            name="Test Sardine",
            slug="order-test-sardine",
            description="Test product",
            price_per_kg=Decimal("150.00"),
            is_active=True,
        )
        db.add(product)
        db.flush()

        inventory = Inventory(
            product_id=product.id,
            available_weight_kg=Decimal("10.000"),
        )
        cart = Cart(user_id=100)
        db.add_all([inventory, cart])
        db.flush()

        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity_kg=Decimal("2.000"),
            )
        )
        db.commit()

        address_id = address.id
        product_id = product.id
        inventory_id = inventory.id

    finally:
        db.close()
        try:
            next(db_dependency)
        except StopIteration:
            pass

    # Create the order through the real API endpoint.
    response = client.post(
        f"{API}/orders/100",
        json={"address_id": address_id},
        headers={"Authorization": "Bearer customer-test-token"},
    )
    assert response.status_code == 201, response.text

    order_id = response.json()["id"]

    # Initiate a sandbox payment through the real API endpoint.
    response = client.post(
        f"{API}/payments/100/{order_id}/initiate",
        json={"provider": "sandbox"},
        headers={"Authorization": "Bearer customer-test-token"},
    )
    assert response.status_code == 200, response.text

    payment_id = response.json()["id"]

    return {
        "order_id": order_id,
        "payment_id": payment_id,
        "product_id": product_id,
        "inventory_id": inventory_id,
        "address_id": address_id,
    }


def test_customer_cannot_initiate_payment_for_another_user(
    client, order_setup, customer_headers
):
    response = client.post(
        f"{API}/payments/101/{order_setup['order_id']}/initiate",
        json={"provider": "sandbox"},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_customer_cannot_confirm_another_users_payment(
    client, order_setup, customer_headers
):
    response = client.post(
        f"{API}/payments/101/{order_setup['order_id']}/confirm/"
        f"{order_setup['payment_id']}",
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_cancelled_order_cannot_be_paid(
    client, order_setup, customer_headers
):
    cancel_response = client.patch(
        f"{API}/orders/100/{order_setup['order_id']}/cancel",
        headers=customer_headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text

    response = client.post(
        f"{API}/payments/100/{order_setup['order_id']}/confirm/"
        f"{order_setup['payment_id']}",
        headers=customer_headers,
    )

    assert response.status_code == 400


def test_payment_amount_must_match_order_total(
    client, order_setup, customer_headers
):
    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)

    try:
        payment = db.get(Payment, order_setup["payment_id"])
        payment.amount = Decimal("1.00")
        db.commit()
    finally:
        db.close()
        try:
            next(db_dependency)
        except StopIteration:
            pass

    response = client.post(
        f"{API}/payments/100/{order_setup['order_id']}/confirm/"
        f"{order_setup['payment_id']}",
        headers=customer_headers,
    )

    assert response.status_code == 409


def test_repeated_payment_confirmation_is_idempotent(
    client, order_setup, customer_headers
):
    url = (
        f"{API}/payments/100/{order_setup['order_id']}/confirm/"
        f"{order_setup['payment_id']}"
    )

    first = client.post(url, headers=customer_headers)
    second = client.post(url, headers=customer_headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["status"] == "paid"

    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)

    try:
        order = db.get(Order, order_setup["order_id"])
        payments = db.scalars(
            select(Payment).where(
                Payment.order_id == order_setup["order_id"]
            )
        ).all()

        assert order.payment_status == "paid"
        assert len(payments) == 1
        assert payments[0].status == "paid"
    finally:
        db.close()
        try:
            next(db_dependency)
        except StopIteration:
            pass


def test_paid_order_cannot_be_cancelled(
    client, order_setup, customer_headers, admin_headers
):
    confirm_response = client.post(
        f"{API}/payments/100/{order_setup['order_id']}/confirm/"
        f"{order_setup['payment_id']}",
        headers=customer_headers,
    )
    assert confirm_response.status_code == 200, confirm_response.text

    # Customer cancellation must be rejected.
    customer_response = client.patch(
        f"{API}/orders/100/{order_setup['order_id']}/cancel",
        headers=customer_headers,
    )
    assert customer_response.status_code == 409

    # Admin cancellation must also be rejected.
    admin_response = client.patch(
        f"{API}/orders/{order_setup['order_id']}/status",
        json={"status": "cancelled"},
        headers=admin_headers,
    )
    assert admin_response.status_code == 409


def test_cancellation_restores_inventory_only_once(
    client, order_setup, customer_headers
):
    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)

    try:
        inventory = db.get(Inventory, order_setup["inventory_id"])
        assert inventory.available_weight_kg == Decimal("8.000")
    finally:
        db.close()
        try:
            next(db_dependency)
        except StopIteration:
            pass

    first = client.patch(
        f"{API}/orders/100/{order_setup['order_id']}/cancel",
        headers=customer_headers,
    )
    assert first.status_code == 200, first.text

    second = client.patch(
        f"{API}/orders/100/{order_setup['order_id']}/cancel",
        headers=customer_headers,
    )
    assert second.status_code == 409

    db_dependency = client.app.dependency_overrides[get_db]()
    db = next(db_dependency)

    try:
        inventory = db.get(Inventory, order_setup["inventory_id"])
        assert inventory.available_weight_kg == Decimal("10.000")

        notifications = db.scalars(
            select(Notification).where(
                Notification.order_id == order_setup["order_id"],
                Notification.title == "Order cancelled",
            )
        ).all()
        assert len(notifications) == 1
    finally:
        db.close()
        try:
            next(db_dependency)
        except StopIteration:
            pass


def test_gateway_order_create_and_verify(client, order_setup, customer_headers):
    order_id = order_setup["order_id"]

    # 1. Create gateway order for GPay / UPI
    response = client.post(
        f"{API}/payments/100/{order_id}/create-gateway-order",
        json={"provider": "razorpay", "payment_method": "upi_gpay"},
        headers=customer_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["order_id"] == order_id
    assert "razorpay_order_id" in data
    assert data["amount"] > 0
    assert data["is_simulation"] is True

    # 2. Verify gateway payment simulation
    verify_res = client.post(
        f"{API}/payments/100/{order_id}/verify-gateway-payment",
        json={
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": "pay_test_gpay_123",
            "razorpay_signature": "sig_test_123",
            "payment_method": "upi_gpay",
        },
        headers=customer_headers,
    )
    assert verify_res.status_code == 200, verify_res.text
    verify_data = verify_res.json()
    assert verify_data["status"] == "paid"
    assert verify_data["payment_method"] == "upi_gpay"

    # 3. Check order is confirmed and paid
    order_res = client.get(
        f"{API}/orders/100/{order_id}",
        headers=customer_headers,
    )
    assert order_res.status_code == 200
    assert order_res.json()["payment_status"] == "paid"
    assert order_res.json()["status"] == "confirmed"


def test_confirm_cash_on_delivery(client, order_setup, customer_headers):
    order_id = order_setup["order_id"]

    # Confirm order with Cash on Delivery
    response = client.post(
        f"{API}/payments/100/{order_id}/confirm-cod",
        headers=customer_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["provider"] == "cod"
    assert data["payment_method"] == "cod"

    # Check order is confirmed with cod_pending status
    order_res = client.get(
        f"{API}/orders/100/{order_id}",
        headers=customer_headers,
    )
    assert order_res.status_code == 200
    assert order_res.json()["payment_status"] == "cod_pending"
    assert order_res.json()["status"] == "confirmed"


def test_cannot_confirm_cod_for_another_user(client, order_setup, customer_headers):
    order_id = order_setup["order_id"]

    # Customer 100 cannot confirm COD for user 101
    response = client.post(
        f"{API}/payments/101/{order_id}/confirm-cod",
        headers=customer_headers,
    )
    assert response.status_code == 403



from fastapi import APIRouter

from app.api.v1 import categories, products, inventory, cart, orders, payments, auth, notifications, delivery

from app.api.v1.addresses import router as addresses_router

api_router = APIRouter()

api_router.include_router(
    categories.router,
    prefix="/categories",
    tags=["Categories"],
)

api_router.include_router(
    products.router,
    prefix="/products",
    tags=["Products"],
)

api_router.include_router(
    inventory.router,
    prefix="/inventory",
    tags=["Inventory"],
)

api_router.include_router(
    cart.router,
    prefix="/cart",
    tags=["Cart"],
)

api_router.include_router(
    orders.router,
    prefix="/orders",
    tags=["Orders"],
)

api_router.include_router(
    payments.router,
    prefix="/payments",
    tags=["Payments"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)

api_router.include_router(
    delivery.router,
    prefix="/delivery",
    tags=["Delivery Management"],
)

api_router.include_router(
    addresses_router,
    prefix="/addresses",
    tags=["Addresses"],
)

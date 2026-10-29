
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.models.user import User

from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.cart import (
    CartItemCreate,
    CartItemRead,
    CartItemUpdate,
    CartRead,
)

router = APIRouter()


def get_or_create_cart(user_id: int, db: Session) -> Cart:
    cart = db.scalars(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.user_id == user_id)
    ).first()

    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()

    return cart


@router.post("/{user_id}", response_model=CartRead)
def get_cart(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's cart",
        )

    cart = get_or_create_cart(user_id, db)
    db.commit()
    db.refresh(cart)
    return cart


@router.post("/{user_id}/items", response_model=CartItemRead)
def add_cart_item(
    user_id: int,
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot modify another user's cart",
        )

    cart = get_or_create_cart(user_id, db)

    product = db.get(Product, payload.product_id)
    if product is None or not product.is_active:
        raise HTTPException(
            status_code=404,
            detail="Active product not found",
        )

    inventory = db.scalars(
        select(Inventory).where(
            Inventory.product_id == payload.product_id
        )
    ).first()

    if inventory is None:
        raise HTTPException(
            status_code=409,
            detail="Inventory has not been configured for this product",
        )

    existing_item = db.scalars(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == payload.product_id,
        )
    ).first()

    new_quantity = payload.quantity_kg
    if existing_item is not None:
        new_quantity += existing_item.quantity_kg

    if new_quantity > inventory.available_weight_kg:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient stock. Available: {inventory.available_weight_kg} kg",
        )

    if existing_item is not None:
        existing_item.quantity_kg = new_quantity
        item = existing_item
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=payload.product_id,
            quantity_kg=payload.quantity_kg,
        )
        db.add(item)

    db.commit()
    db.refresh(item)
    return item


@router.patch("/{user_id}/items/{item_id}", response_model=CartItemRead)
def update_cart_item(
    user_id: int,
    item_id: int,
    payload: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot modify another user's cart",
        )

    cart = get_or_create_cart(user_id, db)

    item = db.scalars(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    ).first()

    if item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")

    inventory = db.scalars(
        select(Inventory).where(
            Inventory.product_id == item.product_id
        )
    ).first()

    if inventory is None or payload.quantity_kg > inventory.available_weight_kg:
        raise HTTPException(
            status_code=409,
            detail="Requested quantity exceeds available stock",
        )

    item.quantity_kg = payload.quantity_kg
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{user_id}/items/{item_id}")
def remove_cart_item(
    user_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot modify another user's cart",
        )

    cart = get_or_create_cart(user_id, db)

    item = db.scalars(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    ).first()

    if item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.delete(item)
    db.commit()

    return {"detail": "Cart item removed successfully"}

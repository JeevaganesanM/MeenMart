
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_admin
from app.models.user import User

from app.db.session import get_db
from app.models.address import Address
from app.models.cart import Cart, CartItem
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.notification_service import create_order_notification

router = APIRouter()


@router.post("/{user_id}", response_model=OrderRead, status_code=201)
def create_order(
    user_id: int,
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot create an order for another user",
        )
    try:
        # Validate delivery address belongs to this user.
        address = db.scalars(
            select(Address).where(
                Address.id == payload.address_id,
                Address.user_id == user_id,
            )
        ).first()

        if address is None:
            raise HTTPException(
                status_code=404,
                detail="Delivery address not found for this user",
            )

        # Load cart and items.
        cart = db.scalars(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.user_id == user_id)
        ).first()

        if cart is None or not cart.items:
            raise HTTPException(
                status_code=400,
                detail="Cart is empty or does not exist",
            )

        # Validate everything and prepare order items before writing.
        prepared_items = []
        total_amount = Decimal("0.00")

        for cart_item in cart.items:
            product = db.scalars(
                select(Product)
                .where(
                    Product.id == cart_item.product_id,
                    Product.is_active.is_(True),
                )
            ).first()

            if product is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Product {cart_item.product_id} is unavailable",
                )

            # Lock inventory row to prevent concurrent orders overselling it.
            inventory = db.scalars(
                select(Inventory)
                .where(Inventory.product_id == product.id)
                .with_for_update()
            ).first()

            if inventory is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Inventory missing for product {product.id}",
                )

            if cart_item.quantity_kg > inventory.available_weight_kg:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Insufficient stock for {product.name}. "
                        f"Available: {inventory.available_weight_kg} kg"
                    ),
                )

            subtotal = (
                cart_item.quantity_kg * product.price_per_kg
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            total_amount += subtotal

            prepared_items.append(
                {
                    "cart_item_id": cart_item.id,
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity_kg": cart_item.quantity_kg,
                    "unit_price_per_kg": product.price_per_kg,
                    "subtotal": subtotal,
                    "inventory": inventory,
                }
            )

        total_amount = total_amount.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        order = Order(
            user_id=user_id,
            address_id=payload.address_id,
            total_amount=total_amount,
            status="pending",
            payment_status="pending",
            delivery_notes=payload.delivery_notes,
        )
        db.add(order)
        db.flush()

        for item in prepared_items:
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    quantity_kg=item["quantity_kg"],
                    unit_price_per_kg=item["unit_price_per_kg"],
                    subtotal=item["subtotal"],
                )
            )

            item["inventory"].available_weight_kg -= item["quantity_kg"]

        # Remove cart items only within the same transaction.
        for item in list(cart.items):
            db.delete(item)

        db.flush()
        db.refresh(order)
        db.commit()

        # Reload items for the response.
        saved_order = db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order.id)
        ).one()

        return saved_order

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise



@router.get("/{user_id}", response_model=list[OrderRead])
def get_user_orders(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's orders",
        )

    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == current_user.id)
        .order_by(Order.id.desc())
    ).all()

    return orders


@router.get("/{user_id}/{order_id}", response_model=OrderRead)
def get_order_details(
    user_id: int,
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's orders",
        )

    order = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
    ).first()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return order


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    allowed_transitions = {
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"preparing", "cancelled"},
        "preparing": {"out_for_delivery", "cancelled"},
        "out_for_delivery": {"delivered"},
        "delivered": set(),
        "cancelled": set(),
    }

    try:
        order = db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
            .with_for_update()
        ).first()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        current_status = order.status
        new_status = payload.status

        if new_status == current_status:
            raise HTTPException(
                status_code=409,
                detail=f"Order is already {current_status}",
            )

        if new_status not in allowed_transitions.get(current_status, set()):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot change order status from "
                    f"{current_status} to {new_status}"
                ),
            )

        
        # Do not cancel paid orders until a refund workflow exists.
        if new_status == "cancelled" and str(order.payment_status).lower() == "paid":
            raise HTTPException(
                status_code=409,
                detail=(
                    "This order has already been paid. "
                    "A refund workflow is required before cancellation."
                ),
            )

        # Restore inventory when cancelling an eligible order.
        if new_status == "cancelled":
            for item in order.items:

                if item.product_id is None:
                    continue

                inventory = db.scalars(
                    select(Inventory)
                    .where(Inventory.product_id == item.product_id)
                    .with_for_update()
                ).first()

                if inventory is None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Inventory missing for product "
                            f"{item.product_id}"
                        ),
                    )

                inventory.available_weight_kg += item.quantity_kg

        order.status = new_status

        # Create notification for the new order status
        create_order_notification(
            db=db,
            user_id=order.user_id,
            order_id=order.id,
            order_status=order.status,
        )

        db.flush()
        db.commit()

        updated_order = db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        ).one()

        return updated_order

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.patch("/{user_id}/{order_id}/cancel", response_model=OrderRead)
def cancel_order(
    user_id: int,
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Customers can only cancel their own orders.
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot cancel another user's order",
        )

    try:
        # 2. Lock the order to prevent duplicate cancellation.
        order = db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
        ).first()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # 3. Only allow cancellation before preparation starts.
        if order.status not in {"pending", "confirmed"}:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Order cannot be cancelled when its status is "
                    f"'{order.status}'"
                ),
            )

        # 4. Do not cancel paid orders until a refund workflow exists.
        if str(order.payment_status).lower() == "paid":
            raise HTTPException(
                status_code=409,
                detail=(
                    "This order has already been paid. "
                    "A refund workflow is required before cancellation."
                ),
            )

        # 5. Restore the inventory deducted during order creation.
        for item in order.items:
            if item.product_id is None:
                continue

            inventory = db.scalars(
                select(Inventory)
                .where(Inventory.product_id == item.product_id)
                .with_for_update()
            ).first()

            if inventory is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Inventory missing for product "
                        f"{item.product_id}"
                    ),
                )

            inventory.available_weight_kg += item.quantity_kg

        # 6. Update status and notify the customer in one transaction.
        order.status = "cancelled"

        create_order_notification(
            db=db,
            user_id=order.user_id,
            order_id=order.id,
            order_status=order.status,
        )

        db.flush()
        db.commit()

        # 7. Reload the order for the API response.
        cancelled_order = db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
        ).one()

        return cancelled_order

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


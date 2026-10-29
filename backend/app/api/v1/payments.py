from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import (
    PaymentInitiate,
    PaymentRead,
    PaymentVerify,
    RazorpayOrderResponse,
)
from app.services.notification_service import create_order_notification

try:
    import razorpay
except ImportError:
    razorpay = None

router = APIRouter()


@router.post(
    "/{user_id}/{order_id}/create-gateway-order",
    response_model=RazorpayOrderResponse,
)
def create_gateway_order(
    user_id: int,
    order_id: int,
    payload: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot initiate payment for another user",
        )

    try:
        order = db.scalar(
            select(Order)
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
        )

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status == "cancelled":
            raise HTTPException(
                status_code=400, detail="Cannot pay for a cancelled order"
            )

        if order.payment_status == "paid":
            raise HTTPException(
                status_code=409, detail="Order has already been paid"
            )

        amount_in_paise = int(order.total_amount * 100)
        is_simulation = True
        razorpay_order_id = f"order_sim_{uuid4().hex[:14]}"
        key_id = settings.razorpay_key_id or "rzp_test_simulated_key"

        # If live/test Razorpay keys are provided in .env, create real gateway order
        if (
            razorpay is not None
            and settings.razorpay_key_id
            and settings.razorpay_key_secret
            and payload.provider == "razorpay"
        ):
            try:
                client = razorpay.Client(
                    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
                )
                rzp_order = client.order.create(
                    {
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "receipt": f"order_{order.id}",
                        "notes": {
                            "user_id": str(user_id),
                            "order_id": str(order_id),
                        },
                    }
                )
                razorpay_order_id = rzp_order["id"]
                key_id = settings.razorpay_key_id
                is_simulation = False
            except Exception as exc:
                print(f"Razorpay API order creation fallback: {exc}")
                is_simulation = True

        payment = db.scalar(
            select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.status == "pending",
            )
            .order_by(Payment.id.desc())
        )

        if payment is None:
            payment = Payment(
                order_id=order.id,
                provider="razorpay" if not is_simulation else "sandbox",
                provider_reference=razorpay_order_id,
                amount=order.total_amount,
                status="pending",
                payment_method=payload.payment_method or "upi_gpay",
            )
            db.add(payment)
        else:
            payment.provider_reference = razorpay_order_id
            payment.payment_method = payload.payment_method or payment.payment_method

        db.commit()
        db.refresh(payment)

        return RazorpayOrderResponse(
            order_id=order.id,
            razorpay_order_id=razorpay_order_id,
            amount=amount_in_paise,
            currency="INR",
            key_id=key_id,
            payment_id=payment.id,
            is_simulation=is_simulation,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{user_id}/{order_id}/verify-gateway-payment",
    response_model=PaymentRead,
)
def verify_gateway_payment(
    user_id: int,
    order_id: int,
    payload: PaymentVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot verify payment for another user",
        )

    try:
        order = db.scalar(
            select(Order)
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
        )

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot pay for a cancelled order")

        payment = db.scalar(
            select(Payment)
            .where(
                Payment.order_id == order.id,
                Payment.provider_reference == payload.razorpay_order_id,
            )
            .with_for_update()
        )

        if payment is None:
            payment = db.scalar(
                select(Payment)
                .where(Payment.order_id == order.id)
                .order_by(Payment.id.desc())
                .with_for_update()
            )

        if payment is None:
            raise HTTPException(status_code=404, detail="Payment record not found")

        # Idempotency check: if payment and order are already marked paid, return immediately
        if payment.status == "paid" and order.payment_status == "paid":
            db.commit()
            return payment

        # Cryptographic verification if using real Razorpay
        if (
            razorpay is not None
            and settings.razorpay_key_id
            and settings.razorpay_key_secret
            and not payload.razorpay_order_id.startswith("order_sim_")
        ):
            client = razorpay.Client(
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
            )
            try:
                client.utility.verify_payment_signature(
                    {
                        "razorpay_order_id": payload.razorpay_order_id,
                        "razorpay_payment_id": payload.razorpay_payment_id,
                        "razorpay_signature": payload.razorpay_signature,
                    }
                )
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid payment cryptographic signature verification",
                )

        payment.status = "paid"
        payment.payment_method = payload.payment_method or "upi_gpay"
        payment.provider_reference = payload.razorpay_payment_id

        order.payment_status = "paid"
        if order.status == "pending":
            order.status = "confirmed"

        create_order_notification(
            db=db,
            user_id=order.user_id,
            order_id=order.id,
            order_status="confirmed",
        )

        db.commit()
        db.refresh(payment)
        return payment

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{user_id}/{order_id}/confirm-cod",
    response_model=PaymentRead,
)
def confirm_cod_order(
    user_id: int,
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot confirm COD for another user",
        )

    try:
        order = db.scalar(
            select(Order)
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
        )

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot confirm COD for a cancelled order")

        if order.payment_status == "paid":
            raise HTTPException(status_code=409, detail="Order has already been paid")

        if order.status not in ("pending", "confirmed"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot confirm COD for an order in '{order.status}' status",
            )

        payment = db.scalar(
            select(Payment)
            .where(Payment.order_id == order.id)
            .order_by(Payment.id.desc())
            .with_for_update()
        )

        # Idempotency check: if COD was already confirmed, return existing payment
        if order.payment_status == "cod_pending" and payment is not None:
            db.commit()
            return payment

        order.payment_status = "cod_pending"
        if order.status == "pending":
            order.status = "confirmed"

        if payment is None:
            payment = Payment(
                order_id=order.id,
                provider="cod",
                provider_reference=f"COD-{order.id}",
                amount=order.total_amount,
                status="pending",
                payment_method="cod",
            )
            db.add(payment)
        else:
            payment.provider = "cod"
            payment.payment_method = "cod"

        create_order_notification(
            db=db,
            user_id=order.user_id,
            order_id=order.id,
            order_status="confirmed",
        )

        db.commit()
        db.refresh(payment)
        return payment

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


# Backward-compatible sandbox initiate & confirm
@router.post(
    "/{user_id}/{order_id}/initiate",
    response_model=PaymentRead,
)
def initiate_payment(
    user_id: int,
    order_id: int,
    payload: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot initiate payment for another user",
        )

    if payload.provider != "sandbox":
        raise HTTPException(
            status_code=400,
            detail="Only sandbox payments are supported currently",
        )

    try:
        order = db.scalar(
            select(Order)
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
        )

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot pay for a cancelled order")

        if order.payment_status == "paid":
            raise HTTPException(status_code=409, detail="Order has already been paid")

        existing_payment = db.scalar(
            select(Payment)
            .where(
                Payment.order_id == order_id,
                Payment.status == "pending",
            )
            .order_by(Payment.id.desc())
        )

        if existing_payment is not None:
            db.commit()
            return existing_payment

        payment = Payment(
            order_id=order.id,
            provider="sandbox",
            provider_reference=f"SBX-{uuid4().hex[:12].upper()}",
            amount=order.total_amount,
            status="pending",
            payment_method=payload.payment_method or "card",
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

        return payment

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{user_id}/{order_id}/confirm/{payment_id}",
    response_model=PaymentRead,
)
def confirm_payment(
    user_id: int,
    order_id: int,
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot confirm payment for another user",
        )

    try:
        order = db.scalar(
            select(Order)
            .where(
                Order.id == order_id,
                Order.user_id == current_user.id,
            )
            .with_for_update()
        )

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot pay for a cancelled order")

        payment = db.scalar(
            select(Payment)
            .where(
                Payment.id == payment_id,
                Payment.order_id == order.id,
            )
            .with_for_update()
        )

        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")

        if payment.provider != "sandbox":
            raise HTTPException(
                status_code=400, detail="Only sandbox payments can be confirmed here"
            )

        if payment.amount != order.total_amount:
            raise HTTPException(
                status_code=409, detail="Payment amount does not match order total"
            )

        if payment.status == "paid":
            if order.payment_status != "paid":
                raise HTTPException(
                    status_code=409, detail="Payment and order statuses are inconsistent"
                )
            db.commit()
            return payment

        if payment.status != "pending":
            raise HTTPException(
                status_code=409, detail="Payment cannot be confirmed in its current state"
            )

        if order.payment_status == "paid":
            raise HTTPException(status_code=409, detail="Order is already marked as paid")

        payment.status = "paid"
        order.payment_status = "paid"

        db.commit()
        db.refresh(payment)

        return payment

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get(
    "/{user_id}",
    response_model=list[PaymentRead],
)
def list_user_payments(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403, detail="You cannot access another user's payments"
        )

    statement = (
        select(Payment)
        .join(Order, Payment.order_id == Order.id)
        .where(Order.user_id == current_user.id)
        .order_by(Payment.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return db.scalars(statement).all()


@router.get(
    "/{user_id}/{payment_id}",
    response_model=PaymentRead,
)
def get_user_payment(
    user_id: int,
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403, detail="You cannot access another user's payments"
        )

    statement = (
        select(Payment)
        .join(Order, Payment.order_id == Order.id)
        .where(
            Order.user_id == current_user.id,
            Payment.id == payment_id,
        )
    )

    payment = db.scalar(statement)

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found for this user")

    return payment

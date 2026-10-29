
from sqlalchemy.orm import Session

from app.models.notification import Notification


ORDER_STATUS_MESSAGES = {
    "pending": (
        "Order placed",
        "Your order #{order_id} has been placed successfully.",
    ),
    "confirmed": (
        "Order confirmed",
        "Your order #{order_id} has been confirmed.",
    ),
    "preparing": (
        "Order being prepared",
        "Your order #{order_id} is being prepared.",
    ),
    "out_for_delivery": (
        "Order out for delivery",
        "Your order #{order_id} is on its way.",
    ),
    "delivered": (
        "Order delivered",
        "Your order #{order_id} has been delivered. Thank you for shopping with MeenMart!",
    ),
    "cancelled": (
        "Order cancelled",
        "Your order #{order_id} has been cancelled.",
    ),
}


def create_order_notification(
    db: Session,
    user_id: int,
    order_id: int,
    order_status: str,
) -> Notification:
    status_key = str(order_status).lower()

    title, message_template = ORDER_STATUS_MESSAGES.get(
        status_key,
        (
            "Order update",
            "Your order #{order_id} status is now {status}.",
        ),
    )

    message = message_template.format(
        order_id=order_id,
        status=status_key.replace("_", " "),
    )

    notification = Notification(
        user_id=user_id,
        order_id=order_id,
        title=title,
        message=message,
        notification_type="order_update",
        is_read=False,
    )

    db.add(notification)
    return notification

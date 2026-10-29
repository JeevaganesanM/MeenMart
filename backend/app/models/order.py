
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )

    address_id: Mapped[int] = mapped_column(
        ForeignKey("addresses.id"), nullable=False
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )

    payment_status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )

    delivery_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )

    product_name: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    quantity_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False
    )

    unit_price_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    order: Mapped["Order"] = relationship(
        back_populates="items"
    )

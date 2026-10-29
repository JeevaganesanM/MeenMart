from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), index=True, nullable=False
    )

    provider: Mapped[str] = mapped_column(
        String(50), default="sandbox", nullable=False
    )

    provider_reference: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )

    payment_method: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )

    provider_signature: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )


from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            name="uq_delivery_assignments_order_id",
        ),
        CheckConstraint(
            "status IN ('assigned', 'picked_up', 'delivered', 'failed')",
            name="ck_delivery_assignments_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    delivery_person_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_persons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="assigned",
        server_default="assigned",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

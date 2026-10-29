
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, ForeignKey, Numeric
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Inventory(Base):
    __tablename__ = "inventory"

    __table_args__ = (
        CheckConstraint(
            "available_weight_kg >= 0",
            name="ck_inventory_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    available_weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=0, nullable=False
    )

    product: Mapped["Product"] = relationship(
        back_populates="inventory"
    )

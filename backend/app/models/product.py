
from decimal import Decimal

from sqlalchemy import (
    Boolean, ForeignKey, Numeric, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(170), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    price_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    image_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    category: Mapped["Category"] = relationship(
        back_populates="products"
    )

    inventory: Mapped["Inventory | None"] = relationship(
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )

    
    translations: Mapped[list["ProductTranslation"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )



from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProductTranslation(Base):
    __tablename__ = "product_translations"

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "language_code",
            name="uq_product_translation_language",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    language_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    product: Mapped["Product"] = relationship(
        back_populates="translations"
    )

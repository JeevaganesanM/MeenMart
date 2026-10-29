
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    recipient_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )
    phone: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    address_line: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    city: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    postal_code: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    instructions: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    user: Mapped["User"] = relationship(
        back_populates="addresses"
    )

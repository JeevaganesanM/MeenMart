
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

class OrderCreate(BaseModel):
    address_id: int = Field(gt=0)
    delivery_notes: str | None = Field(default=None, max_length=1000)


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        pattern=r"^(confirmed|preparing|out_for_delivery|delivered|cancelled)$"
    )

class OrderItemRead(BaseModel):
    id: int
    product_id: int | None
    product_name: str
    quantity_kg: Decimal
    unit_price_per_kg: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    id: int
    user_id: int
    address_id: int
    total_amount: Decimal
    status: str
    payment_status: str
    delivery_notes: str | None
    items: list[OrderItemRead]

    model_config = ConfigDict(from_attributes=True)

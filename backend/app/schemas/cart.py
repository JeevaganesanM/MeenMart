
from decimal import Decimal

from pydantic import BaseModel,ConfigDict, Field


class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity_kg: Decimal = Field(
        gt=0, max_digits=10, decimal_places=3
    )


class CartItemUpdate(BaseModel):
    quantity_kg: Decimal = Field(
        gt=0, max_digits=10, decimal_places=3
    )

class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity_kg: Decimal = Field(
        gt=0, max_digits=10, decimal_places=3
    )


class CartItemUpdate(BaseModel):
    quantity_kg: Decimal = Field(
        gt=0, max_digits=10, decimal_places=3
    )

class CartItemRead(BaseModel):
    id: int
    product_id: int
    quantity_kg: Decimal

    model_config = ConfigDict(from_attributes=True)


class CartRead(BaseModel):
    id: int
    user_id: int
    items: list[CartItemRead]

    model_config = ConfigDict(from_attributes=True)
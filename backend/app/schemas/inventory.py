
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InventoryCreate(BaseModel):
    product_id: int = Field(gt=0)
    available_weight_kg: Decimal = Field(ge=0, max_digits=10, decimal_places=3)


class InventoryUpdate(BaseModel):
    available_weight_kg: Decimal = Field(ge=0, max_digits=10, decimal_places=3)


class InventoryRead(BaseModel):
    id: int
    product_id: int
    available_weight_kg: Decimal

    model_config = ConfigDict(from_attributes=True)

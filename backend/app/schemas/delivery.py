
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliveryPersonCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=30)


class DeliveryPersonRead(BaseModel):
    id: int
    name: str
    phone: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DeliveryAssignmentCreate(BaseModel):
    order_id: int = Field(gt=0)
    delivery_person_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)


class DeliveryAssignmentStatusUpdate(BaseModel):
    status: str = Field(
        pattern=r"^(picked_up|delivered|failed)$"
    )
    notes: str | None = Field(default=None, max_length=500)


class DeliveryAssignmentRead(BaseModel):
    id: int
    order_id: int
    delivery_person_id: int
    status: str
    notes: str | None
    assigned_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

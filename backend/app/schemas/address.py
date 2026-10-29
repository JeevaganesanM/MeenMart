
from pydantic import BaseModel, Field, ConfigDict

class AddressCreate(BaseModel):
    recipient_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    address_line: str = Field(min_length=5, max_length=1000)
    city: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(min_length=4, max_length=20)
    instructions: str | None = Field(default=None, max_length=1000)


class AddressUpdate(BaseModel):
    recipient_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    address_line: str | None = Field(default=None, min_length=5, max_length=1000)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    postal_code: str | None = Field(default=None, min_length=4, max_length=20)
    instructions: str | None = Field(default=None, max_length=1000)


class AddressRead(AddressCreate):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)

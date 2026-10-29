
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SupportedLanguage = Literal["en", "ta", "ml", "hi"]


class ProductCreate(BaseModel):
    category_id: int = Field(gt=0)

    name: str = Field(min_length=2, max_length=150)

    slug: str = Field(
        min_length=2,
        max_length=170,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    description: str | None = None

    price_per_kg: Decimal = Field(
        gt=0, max_digits=10, decimal_places=2
    )

    image_url: HttpUrl | None = None

    is_active: bool = True


class ProductUpdate(BaseModel):
    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=170,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = None
    price_per_kg: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    image_url: HttpUrl | None = None
    is_active: bool | None = None


class ProductRead(BaseModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    price_per_kg: Decimal
    image_url: str | None
    is_active: bool
    available_weight_kg: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)

class ProductTranslationCreate(BaseModel):
    language_code: SupportedLanguage
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class ProductTranslationRead(BaseModel):
    id: int
    product_id: int
    language_code: SupportedLanguage
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)

class ProductLocalizedRead(BaseModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    price_per_kg: Decimal
    image_url: str | None
    is_active: bool
    available_weight_kg: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)

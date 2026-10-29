
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin

from app.db.session import get_db
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
)

from app.models.product_translation import ProductTranslation
from app.schemas.product import (
    ProductTranslationCreate,
    ProductTranslationRead,
    ProductLocalizedRead,
)

router = APIRouter()



@router.get("/", response_model=list[ProductLocalizedRead])
def list_products(
    category_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    language_code: str = Query(default="en", pattern="^(en|ta|ml|hi)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = (
        select(Product, ProductTranslation, Inventory.available_weight_kg)
        .outerjoin(
            ProductTranslation,
            (ProductTranslation.product_id == Product.id)
            & (ProductTranslation.language_code == language_code),
        )
        .outerjoin(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active.is_(True))
    )

    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)

    if search:
        statement = statement.where(
            ProductTranslation.name.ilike(f"%{search}%")
            if language_code != "en"
            else Product.name.ilike(f"%{search}%")
        )

    statement = (
        statement.order_by(Product.name)
        .offset(skip)
        .limit(limit)
    )

    rows = db.execute(statement).all()

    result = []

    for product, translation, available_weight_kg in rows:
        result.append(
            ProductLocalizedRead(
                id=product.id,
                category_id=product.category_id,
                name=translation.name if translation else product.name,
                slug=product.slug,
                description=(
                    translation.description
                    if translation and translation.description is not None
                    else product.description
                ),
                price_per_kg=product.price_per_kg,
                image_url=product.image_url,
                is_active=product.is_active,
                available_weight_kg=available_weight_kg,
            )
        )

    return result


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    category = db.get(Category, payload.category_id)

    if category is None:
        raise HTTPException(
            status_code=400,
            detail="Category does not exist",
        )

    values = payload.model_dump()

    if values.get("image_url") is not None:
        values["image_url"] = str(values["image_url"])

    product = Product(**values)
    db.add(product)

    try:
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Product slug already exists or data conflicts",
        )

    return product



@router.get("/{product_id}", response_model=ProductLocalizedRead)
def get_product(
    product_id: int,
    language_code: str = Query(
        default="en",
        pattern="^(en|ta|ml|hi)$",
    ),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)

    if product is None or not product.is_active:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    statement = select(ProductTranslation).where(
        ProductTranslation.product_id == product_id,
        ProductTranslation.language_code == language_code,
    )

    translation = db.scalars(statement).first()

    return ProductLocalizedRead(
        id=product.id,
        category_id=product.category_id,
        name=translation.name if translation else product.name,
        slug=product.slug,
        description=(
            translation.description
            if translation and translation.description is not None
            else product.description
        ),
        price_per_kg=product.price_per_kg,
        image_url=product.image_url,
        is_active=product.is_active,
        available_weight_kg=(
            product.inventory.available_weight_kg
            if product.inventory is not None
            else None
        ),
    )


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    values = payload.model_dump(exclude_unset=True)

    if "category_id" in values:
        category = db.get(Category, values["category_id"])

        if category is None:
            raise HTTPException(
                status_code=400,
                detail="Category does not exist",
            )

    if values.get("image_url") is not None:
        values["image_url"] = str(values["image_url"])

    for key, value in values.items():
        setattr(product, key, value)

    try:
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Product slug already exists or data conflicts",
        )

    return product


@router.get(
    "/{product_id}/translations",
    response_model=list[ProductTranslationRead],
)
def get_product_translations(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    statement = select(ProductTranslation).where(
        ProductTranslation.product_id == product_id
    )

    return db.scalars(statement).all()


@router.put(
    "/{product_id}/translations/{language_code}",
    response_model=ProductTranslationRead,
)
def upsert_product_translation(
    product_id: int,
    language_code: str,
    translation_data: ProductTranslationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    supported_languages = {"en", "ta", "ml", "hi"}

    if language_code not in supported_languages:
        raise HTTPException(
            status_code=422,
            detail="Supported languages are en, ta, ml, and hi",
        )

    if translation_data.language_code != language_code:
        raise HTTPException(
            status_code=422,
            detail="Path language_code must match the request body",
        )

    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    statement = select(ProductTranslation).where(
        ProductTranslation.product_id == product_id,
        ProductTranslation.language_code == language_code,
    )

    translation = db.scalars(statement).first()

    if translation is None:
        translation = ProductTranslation(
            product_id=product_id,
            language_code=language_code,
            name=translation_data.name,
            description=translation_data.description,
        )
        db.add(translation)
    else:
        translation.name = translation_data.name
        translation.description = translation_data.description

    db.commit()
    db.refresh(translation)

    return translation

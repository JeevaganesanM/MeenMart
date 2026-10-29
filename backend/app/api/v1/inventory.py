
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin

from app.db.session import get_db
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryUpdate

router = APIRouter()


@router.post(
    "/",
    response_model=InventoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory(
    payload: InventoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    product = db.get(Product, payload.product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = db.scalars(
        select(Inventory).where(
            Inventory.product_id == payload.product_id
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Inventory already exists for this product",
        )

    inventory = Inventory(**payload.model_dump())
    db.add(inventory)

    try:
        db.commit()
        db.refresh(inventory)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Inventory record conflicts with existing data",
        )

    return inventory


@router.get("/{product_id}", response_model=InventoryRead)
def get_inventory(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    inventory = db.scalars(
        select(Inventory).where(Inventory.product_id == product_id)
    ).first()

    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory not found")

    return inventory


@router.patch("/{product_id}", response_model=InventoryRead)
def update_inventory(
    product_id: int,
    payload: InventoryUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    inventory = db.scalars(
        select(Inventory).where(Inventory.product_id == product_id)
    ).first()

    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory not found")

    inventory.available_weight_kg = payload.available_weight_kg

    db.commit()
    db.refresh(inventory)

    return inventory

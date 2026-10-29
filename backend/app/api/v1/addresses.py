from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.address import Address
from app.models.order import Order
from app.models.user import User
from app.schemas.address import AddressCreate, AddressRead, AddressUpdate

router = APIRouter()


def get_owned_address(
    address_id: int,
    user_id: int,
    db: Session,
) -> Address:
    address = db.scalar(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == user_id,
        )
    )

    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    return address


@router.get("/", response_model=list[AddressRead])
def list_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Address)
        .where(Address.user_id == current_user.id)
        .order_by(Address.id.desc())
    ).all()


@router.post(
    "/",
    response_model=AddressRead,
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    payload: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = Address(
        user_id=current_user.id,
        **payload.model_dump(),
    )

    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.patch("/{address_id}", response_model=AddressRead)
def update_address(
    address_id: int,
    payload: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = get_owned_address(address_id, current_user.id, db)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(address, field, value)

    db.commit()
    db.refresh(address)
    return address


@router.delete("/{address_id}")
def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address = get_owned_address(address_id, current_user.id, db)

    # Check if address is referenced by existing orders
    order_exists = db.scalar(
        select(Order.id).where(Order.address_id == address_id)
    )
    if order_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an address that is linked to existing orders.",
        )

    try:
        db.delete(address)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete address because it is referenced by other records.",
        )

    return {"detail": "Address deleted successfully"}

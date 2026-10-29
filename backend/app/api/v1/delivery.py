
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.models.user import User

from app.db.session import get_db
from app.models.delivery_assignment import DeliveryAssignment
from app.models.delivery_person import DeliveryPerson
from app.models.notification import Notification
from app.models.order import Order
from app.schemas.delivery import (
    DeliveryAssignmentCreate,
    DeliveryAssignmentRead,
    DeliveryAssignmentStatusUpdate,
    DeliveryPersonCreate,
    DeliveryPersonRead,
)
from app.services.notification_service import create_order_notification

router = APIRouter()


@router.post(
    "/persons",
    response_model=DeliveryPersonRead,
    status_code=201,
)
def create_delivery_person(
    payload: DeliveryPersonCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(DeliveryPerson).where(
            DeliveryPerson.phone == payload.phone.strip()
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A delivery person with this phone already exists",
        )

    person = DeliveryPerson(
        name=payload.name.strip(),
        phone=payload.phone.strip(),
    )

    try:
        db.add(person)
        db.commit()
        db.refresh(person)
        return person
    except Exception:
        db.rollback()
        raise


@router.get(
    "/persons",
    response_model=list[DeliveryPersonRead],
)
def list_delivery_persons(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return db.scalars(
        select(DeliveryPerson).order_by(DeliveryPerson.id.desc())
    ).all()


@router.patch(
    "/persons/{person_id}/active",
    response_model=DeliveryPersonRead,
)
def set_delivery_person_active(
    person_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    person = db.get(DeliveryPerson, person_id)

    if person is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery person not found",
        )

    person.is_active = is_active
    db.commit()
    db.refresh(person)
    return person


@router.post(
    "/assignments",
    response_model=DeliveryAssignmentRead,
    status_code=201,
)
def create_delivery_assignment(
    payload: DeliveryAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        order = db.scalar(
            select(Order)
            .where(Order.id == payload.order_id)
            .with_for_update()
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        if order.status != "preparing":
            raise HTTPException(
                status_code=409,
                detail="Only orders in preparing status can be assigned",
            )

        existing_assignment = db.scalar(
            select(DeliveryAssignment).where(
                DeliveryAssignment.order_id == order.id
            )
        )

        if existing_assignment is not None:
            raise HTTPException(
                status_code=409,
                detail="This order already has a delivery assignment",
            )

        person = db.scalar(
            select(DeliveryPerson)
            .where(
                DeliveryPerson.id == payload.delivery_person_id,
                DeliveryPerson.is_active.is_(True),
            )
            .with_for_update()
        )

        if person is None:
            raise HTTPException(
                status_code=404,
                detail="Active delivery person not found",
            )

        assignment = DeliveryAssignment(
            order_id=order.id,
            delivery_person_id=person.id,
            status="assigned",
            notes=payload.notes,
        )

        db.add(assignment)

        db.add(
            Notification(
                user_id=order.user_id,
                order_id=order.id,
                title="Delivery assigned",
                message=(
                    f"A delivery person has been assigned to order "
                    f"#{order.id}."
                ),
                notification_type="order_update",
                is_read=False,
            )
        )

        db.commit()
        db.refresh(assignment)
        return assignment

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get(
    "/assignments",
    response_model=list[DeliveryAssignmentRead],
)
def list_delivery_assignments(
    status: str | None = None,
    delivery_person_id: int | None = None,
    order_id: int | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(DeliveryAssignment)

    if status is not None:
        allowed = {"assigned", "picked_up", "delivered", "failed"}
        if status not in allowed:
            raise HTTPException(
                status_code=422,
                detail="Invalid assignment status",
            )
        query = query.where(DeliveryAssignment.status == status)

    if delivery_person_id is not None:
        query = query.where(
            DeliveryAssignment.delivery_person_id == delivery_person_id
        )

    if order_id is not None:
        query = query.where(DeliveryAssignment.order_id == order_id)

    return db.scalars(
        query.order_by(DeliveryAssignment.id.desc())
    ).all()


@router.patch(
    "/assignments/{assignment_id}/status",
    response_model=DeliveryAssignmentRead,
)
def update_delivery_assignment_status(
    assignment_id: int,
    payload: DeliveryAssignmentStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        assignment = db.scalar(
            select(DeliveryAssignment)
            .where(DeliveryAssignment.id == assignment_id)
            .with_for_update()
        )

        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail="Delivery assignment not found",
            )

        order = db.scalar(
            select(Order)
            .where(Order.id == assignment.order_id)
            .with_for_update()
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        current = assignment.status
        new = payload.status

        allowed_transitions = {
            "assigned": {"picked_up", "failed"},
            "picked_up": {"delivered", "failed"},
            "delivered": set(),
            "failed": set(),
        }

        if new not in allowed_transitions.get(current, set()):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot change assignment from {current} to {new}",
            )

        if new == "picked_up" and order.status != "preparing":
            raise HTTPException(
                status_code=409,
                detail="Order must be preparing before pickup",
            )

        if new == "delivered" and order.status != "out_for_delivery":
            raise HTTPException(
                status_code=409,
                detail="Order must be out_for_delivery before delivery",
            )

        assignment.status = new

        if payload.notes is not None:
            assignment.notes = payload.notes

        if new == "picked_up":
            order.status = "out_for_delivery"
            create_order_notification(
                db=db,
                user_id=order.user_id,
                order_id=order.id,
                order_status=order.status,
            )

        elif new == "delivered":
            order.status = "delivered"
            create_order_notification(
                db=db,
                user_id=order.user_id,
                order_id=order.id,
                order_status=order.status,
            )

        elif new == "failed":
            db.add(
                Notification(
                    user_id=order.user_id,
                    order_id=order.id,
                    title="Delivery attempt unsuccessful",
                    message=(
                        f"The delivery attempt for order #{order.id} "
                        "was unsuccessful. Please contact MeenMart for assistance."
                    ),
                    notification_type="order_update",
                    is_read=False,
                )
            )

        db.commit()
        db.refresh(assignment)
        return assignment

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

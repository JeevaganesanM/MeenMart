
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    NotificationRead,
    UnreadCountResponse,
)

router = APIRouter()


def check_user_exists(user_id: int, db: Session) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/{user_id}", response_model=list[NotificationRead])
def list_notifications(
    user_id: int,
    unread_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's notifications",
        )

    check_user_exists(user_id, db)

    query = select(Notification).where(
        Notification.user_id == user_id
    )

    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    query = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return db.scalars(query).all()



@router.get(
    "/{user_id}/unread-count",
    response_model=UnreadCountResponse,
)
def get_unread_count(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's notifications",
        )

    check_user_exists(user_id, db)

    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )

    return UnreadCountResponse(unread_count=count or 0)



@router.patch(
    "/{user_id}/{notification_id}/read",
    response_model=NotificationRead,
)
def mark_notification_as_read(
    user_id: int,
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's notifications",
        )

    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found for this user",
        )

    notification.is_read = True
    db.commit()
    db.refresh(notification)

    return notification



@router.patch("/{user_id}/read-all")
def mark_all_notifications_as_read(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot access another user's notifications",
        )

    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )

    db.commit()

    return {
        "message": "All notifications marked as read",
        "updated_count": result.rowcount or 0,
    }

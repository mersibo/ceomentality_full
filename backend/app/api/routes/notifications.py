from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update

from app.api.deps import CurrentUserDep, SessionDep
from app.models import AdminNotification
from app.schemas import MessageOut, NotificationListOut, NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def notification_out(item: AdminNotification) -> NotificationOut:
    return NotificationOut(
        id=item.id,
        type=item.type,
        detail=item.detail,
        entityType=item.entity_type,
        entityId=item.entity_id,
        isRead=item.is_read,
        createdAt=item.created_at,
    )


@router.get("", response_model=NotificationListOut)
async def list_notifications(session: SessionDep, user: CurrentUserDep, limit: int = 50):
    scope = AdminNotification.user_id == user.id
    items = (
        await session.scalars(
            select(AdminNotification)
            .where(scope)
            .order_by(AdminNotification.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
    ).all()
    unread = await session.scalar(
        select(func.count()).select_from(AdminNotification).where(scope, AdminNotification.is_read.is_(False))
    ) or 0
    return NotificationListOut(items=[notification_out(item) for item in items], unread=unread)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def read_notification(notification_id: UUID, session: SessionDep, user: CurrentUserDep):
    item = await session.get(AdminNotification, notification_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    item.is_read = True
    await session.commit()
    return notification_out(item)


@router.post("/read-all", response_model=MessageOut)
async def read_all_notifications(session: SessionDep, user: CurrentUserDep):
    await session.execute(
        update(AdminNotification)
        .where(AdminNotification.user_id == user.id)
        .values(is_read=True)
    )
    await session.commit()
    return MessageOut(message="Notifications marked as read")

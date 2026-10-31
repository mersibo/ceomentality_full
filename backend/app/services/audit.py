from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActivityEvent, AdminNotification, User


async def record_activity(
    session: AsyncSession,
    *,
    type_: str,
    detail: str,
    actor_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    data: dict | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        type=type_,
        detail=detail,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        data=data or {},
    )
    session.add(event)
    notify_managers = type_ == "notification.manager" or type_.startswith(
        ("candidate.status_", "code.", "codes.", "drop.", "purchase.", "membership.")
    )
    if notify_managers:
        user_ids = (await session.scalars(select(User.id).where(User.is_active.is_(True)))).all()
        for user_id in user_ids:
            session.add(
                AdminNotification(
                    user_id=user_id,
                    type=type_,
                    detail=detail,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )
    return event

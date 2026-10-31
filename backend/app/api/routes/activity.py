from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.models import ActivityEvent
from app.schemas import ActivityOut
from app.services.formatting import activity_out

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("", response_model=list[ActivityOut])
async def list_activity(session: SessionDep, _: CurrentUserDep):
    events = (await session.scalars(select(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(200))).all()
    return [activity_out(item) for item in events]

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUserDep, SessionDep
from app.models import AccessCode, Candidate, Drop
from app.schemas import WorkspaceSearchOut
from app.services.formatting import candidate_out, drop_out

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=WorkspaceSearchOut)
async def search_workspace(session: SessionDep, _: CurrentUserDep, q: str = Query(default="")):
    needle = q.strip().lower()
    if not needle:
        return WorkspaceSearchOut(candidates=[], drops=[], codes=[])
    like = f"%{needle}%"
    candidates = (
        await session.scalars(
            select(Candidate)
            .options(selectinload(Candidate.notes))
            .where(func.lower(func.concat(Candidate.name, " ", Candidate.company, " ", Candidate.telegram)).like(like))
            .limit(20)
        )
    ).all()
    drops = (
        await session.scalars(
            select(Drop)
            .where(func.lower(func.concat(Drop.name, " ", Drop.description, " ", Drop.code)).like(like))
            .limit(20)
        )
    ).all()
    codes = (await session.scalars(select(AccessCode.value).where(func.lower(AccessCode.value).like(like)).limit(20))).all()
    return WorkspaceSearchOut(
        candidates=[candidate_out(item) for item in candidates],
        drops=[drop_out(item) for item in drops],
        codes=list(codes),
    )

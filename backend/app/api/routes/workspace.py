from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas import WorkspaceState
from app.services.audit import record_activity
from app.services.workspace import get_workspace, replace_workspace

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


@router.get("", response_model=WorkspaceState)
async def load_workspace(session: SessionDep, _: CurrentUserDep):
    return await get_workspace(session)


@router.put("", response_model=WorkspaceState)
async def save_workspace(payload: WorkspaceState, session: SessionDep, user: CurrentUserDep):
    state = await replace_workspace(session, payload)
    await record_activity(
        session,
        type_="workspace.replaced",
        detail="Workspace state replaced from frontend adapter",
        actor_id=user.id,
    )
    await session.commit()
    return state


@router.post("/reset", response_model=WorkspaceState)
async def reset_workspace(session: SessionDep, user: CurrentUserDep):
    from app.seed import seed_database

    await seed_database(session, force=True)
    await record_activity(session, type_="workspace.reset", detail="Workspace reset", actor_id=user.id)
    await session.commit()
    return await get_workspace(session)

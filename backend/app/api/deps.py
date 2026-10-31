from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import parse_session_token
from app.db.session import get_session
from app.models import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = parse_session_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user = await session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_optional_current_user(
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    user_id = parse_session_token(token)
    if user_id is None:
        return None
    return await session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))


OptionalCurrentUserDep = Annotated[User | None, Depends(get_optional_current_user)]


async def require_integration_secret(settings: SettingsDep, request: Request) -> None:
    configured = settings.telegram_integration_secret
    provided = request.headers.get("x-integration-secret") or request.headers.get(
        "x-crm-integration-secret"
    )
    if not configured or not provided:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Integration secret required")

    import secrets

    if not secrets.compare_digest(configured, provided):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid integration secret")


IntegrationSecretDep = Annotated[None, Depends(require_integration_secret)]

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, OptionalCurrentUserDep, SessionDep, SettingsDep
from app.core.security import create_session_token, hash_password, verify_password
from app.schemas import LoginIn, LoginOut, PasswordChangeIn, SessionOut, UserOut, UserPatchIn
from app.services.audit import record_activity

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn, response: Response, session: SessionDep, settings: SettingsDep):
    from app.models import User

    user = await session.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_session_token(user.id)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_minutes * 60,
    )
    await record_activity(session, type_="auth.login", detail=f"{user.email} signed in", actor_id=user.id)
    await session.commit()
    return LoginOut(user=UserOut(id=user.id, name=user.name, email=user.email, role=user.role))


@router.get("/me", response_model=LoginOut)
async def me(user: CurrentUserDep):
    return LoginOut(user=UserOut(id=user.id, name=user.name, email=user.email, role=user.role))


@router.get("/session", response_model=SessionOut)
async def session_state(user: OptionalCurrentUserDep):
    if user is None:
        return SessionOut(user=None)
    return SessionOut(user=UserOut(id=user.id, name=user.name, email=user.email, role=user.role))


@router.patch("/me", response_model=LoginOut)
async def update_me(payload: UserPatchIn, user: CurrentUserDep, session: SessionDep):
    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = str(payload.email)
    await record_activity(session, type_="auth.profile_updated", detail=f"{user.email} updated profile", actor_id=user.id)
    await session.commit()
    return LoginOut(user=UserOut(id=user.id, name=user.name, email=user.email, role=user.role))


@router.post("/me/password")
async def change_password(payload: PasswordChangeIn, user: CurrentUserDep, session: SessionDep):
    if not verify_password(payload.currentPassword, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.newPassword)
    await record_activity(session, type_="auth.password_changed", detail=f"{user.email} changed password", actor_id=user.id)
    await session.commit()
    return {"message": "Password changed"}


@router.post("/logout")
async def logout(response: Response, settings: SettingsDep, user: CurrentUserDep, session: SessionDep):
    response.delete_cookie(settings.session_cookie_name, httponly=True, samesite="lax")
    await record_activity(session, type_="auth.logout", detail=f"{user.email} signed out", actor_id=user.id)
    await session.commit()
    return {"message": "Logged out"}

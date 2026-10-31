from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.core.security import hash_password
from app.models import User
from app.schemas import AdminUserCreate, AdminUserOut, AdminUserPatch, MessageOut
from app.services.audit import record_activity

router = APIRouter(prefix="/api/users", tags=["users"])


def require_founder(role: str) -> None:
    if role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can manage users")


def user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        isActive=user.is_active,
        createdAt=user.created_at,
    )


@router.get("", response_model=list[AdminUserOut])
async def list_users(session: SessionDep, user: CurrentUserDep):
    require_founder(user.role)
    items = (await session.scalars(select(User).order_by(User.created_at))).all()
    return [user_out(item) for item in items]


@router.post("", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: AdminUserCreate, session: SessionDep, user: CurrentUserDep):
    require_founder(user.role)
    email = str(payload.email).lower()
    if await session.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    item = User(
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        is_active=True,
    )
    session.add(item)
    await session.flush()
    await record_activity(
        session,
        type_="user.created",
        detail=f"{item.email} created with role {item.role}",
        actor_id=user.id,
        entity_type="user",
        entity_id=str(item.id),
    )
    await session.commit()
    return user_out(item)


@router.patch("/{user_id}", response_model=AdminUserOut)
async def patch_user(user_id: UUID, payload: AdminUserPatch, session: SessionDep, user: CurrentUserDep):
    require_founder(user.role)
    item = await session.get(User, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    values = payload.model_dump(exclude_unset=True)
    if "email" in values:
        email = str(values["email"]).lower()
        duplicate = await session.scalar(select(User.id).where(func.lower(User.email) == email, User.id != item.id))
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
        item.email = email
    if "name" in values:
        item.name = values["name"]
    if "role" in values:
        item.role = values["role"].value
    if "isActive" in values:
        if item.id == user.id and not values["isActive"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate yourself")
        item.is_active = values["isActive"]
    if values.get("password"):
        item.password_hash = hash_password(values["password"])
    await record_activity(
        session,
        type_="user.updated",
        detail=f"{item.email} updated",
        actor_id=user.id,
        entity_type="user",
        entity_id=str(item.id),
    )
    await session.commit()
    return user_out(item)


@router.delete("/{user_id}", response_model=MessageOut)
async def deactivate_user(user_id: UUID, session: SessionDep, user: CurrentUserDep):
    require_founder(user.role)
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate yourself")
    item = await session.get(User, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    item.is_active = False
    await record_activity(
        session,
        type_="user.deactivated",
        detail=f"{item.email} deactivated",
        actor_id=user.id,
        entity_type="user",
        entity_id=str(item.id),
    )
    await session.commit()
    return MessageOut(message="User deactivated")

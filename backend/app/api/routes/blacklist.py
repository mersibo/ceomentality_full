from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUserDep, SessionDep
from app.models import BlacklistEntry
from app.schemas import BlacklistEntryCreate, BlacklistEntryOut, BlacklistEntryPatch, MessageOut
from app.services.audit import record_activity
from app.services.blacklist import (
    normalize_email,
    normalize_phone,
    normalize_telegram_id,
    normalize_telegram_username,
)

router = APIRouter(prefix="/api/blacklist", tags=["blacklist"])


def blacklist_out(entry: BlacklistEntry) -> BlacklistEntryOut:
    return BlacklistEntryOut(
        id=entry.id,
        name=entry.name,
        telegramId=entry.telegram_id,
        telegramUsername=entry.telegram_username,
        email=entry.email,
        phone=entry.phone,
        reason=entry.reason,
        isActive=entry.is_active,
        createdAt=entry.created_at,
        updatedAt=entry.updated_at,
    )


def require_manager(role: str) -> None:
    if role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("", response_model=list[BlacklistEntryOut])
async def list_blacklist(
    session: SessionDep,
    _: CurrentUserDep,
    search: str | None = None,
    active_only: bool = Query(default=True, alias="activeOnly"),
):
    query = select(BlacklistEntry)
    if active_only:
        query = query.where(BlacklistEntry.is_active.is_(True))
    if search:
        needle = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(BlacklistEntry.name).like(needle),
                func.lower(BlacklistEntry.telegram_username).like(needle),
                BlacklistEntry.telegram_id.like(needle),
                func.lower(BlacklistEntry.email).like(needle),
                BlacklistEntry.phone.like(needle),
                func.lower(BlacklistEntry.reason).like(needle),
            )
        )
    entries = (await session.scalars(query.order_by(BlacklistEntry.created_at.desc()))).all()
    return [blacklist_out(entry) for entry in entries]


@router.post("", response_model=BlacklistEntryOut, status_code=status.HTTP_201_CREATED)
async def add_to_blacklist(
    payload: BlacklistEntryCreate,
    session: SessionDep,
    user: CurrentUserDep,
):
    require_manager(user.role)
    telegram_id = normalize_telegram_id(payload.telegramId)
    telegram_username = normalize_telegram_username(payload.telegramUsername)
    email = normalize_email(str(payload.email) if payload.email else None)
    phone = normalize_phone(payload.phone)
    if payload.telegramId and not telegram_id:
        raise HTTPException(status_code=422, detail="telegramId must be numeric")
    if payload.telegramUsername and not telegram_username:
        raise HTTPException(status_code=422, detail="Invalid Telegram username")
    if payload.phone and not phone:
        raise HTTPException(status_code=422, detail="Invalid phone")
    duplicate_filters = []
    if telegram_id:
        duplicate_filters.append(BlacklistEntry.telegram_id == telegram_id)
    if telegram_username:
        duplicate_filters.append(BlacklistEntry.telegram_username == telegram_username)
    if email:
        duplicate_filters.append(BlacklistEntry.email == email)
    if phone:
        duplicate_filters.append(BlacklistEntry.phone == phone)
    if not duplicate_filters:
        raise HTTPException(status_code=422, detail="At least one valid identifier is required")
    duplicate = await session.scalar(
        select(BlacklistEntry).where(BlacklistEntry.is_active.is_(True), or_(*duplicate_filters))
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already blacklisted")
    entry = BlacklistEntry(
        name=payload.name.strip(),
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        email=email,
        phone=phone,
        reason=payload.reason.strip(),
        created_by_id=user.id,
    )
    session.add(entry)
    await session.flush()
    await record_activity(
        session,
        type_="blacklist.added",
        detail=f"{entry.name or entry.telegram_username or entry.telegram_id} added to blacklist",
        actor_id=user.id,
        entity_type="blacklist",
        entity_id=str(entry.id),
        data={"reason": entry.reason},
    )
    await session.commit()
    await session.refresh(entry)
    return blacklist_out(entry)


@router.patch("/{entry_id}", response_model=BlacklistEntryOut)
async def update_blacklist_entry(
    entry_id: UUID,
    payload: BlacklistEntryPatch,
    session: SessionDep,
    user: CurrentUserDep,
):
    require_manager(user.role)
    entry = await session.get(BlacklistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blacklist entry not found")
    values = payload.model_dump(exclude_unset=True)
    if "telegramId" in values:
        entry.telegram_id = normalize_telegram_id(values["telegramId"])
        if values["telegramId"] and not entry.telegram_id:
            raise HTTPException(status_code=422, detail="telegramId must be numeric")
    if "telegramUsername" in values:
        entry.telegram_username = normalize_telegram_username(values["telegramUsername"])
        if values["telegramUsername"] and not entry.telegram_username:
            raise HTTPException(status_code=422, detail="Invalid Telegram username")
    if "email" in values:
        entry.email = normalize_email(str(values["email"]) if values["email"] else None)
    if "phone" in values:
        entry.phone = normalize_phone(values["phone"])
        if values["phone"] and not entry.phone:
            raise HTTPException(status_code=422, detail="Invalid phone")
    if "name" in values:
        entry.name = values["name"].strip()
    if "reason" in values:
        entry.reason = values["reason"].strip()
    if "isActive" in values:
        entry.is_active = values["isActive"]
    if not any((entry.telegram_id, entry.telegram_username, entry.email, entry.phone)):
        raise HTTPException(status_code=422, detail="At least one identifier is required")
    await record_activity(
        session,
        type_="blacklist.updated",
        detail=f"Blacklist entry {entry.id} updated",
        actor_id=user.id,
        entity_type="blacklist",
        entity_id=str(entry.id),
    )
    await session.commit()
    await session.refresh(entry)
    return blacklist_out(entry)


@router.delete("/{entry_id}", response_model=MessageOut)
async def remove_from_blacklist(
    entry_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
):
    require_manager(user.role)
    entry = await session.get(BlacklistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blacklist entry not found")
    entry.is_active = False
    await record_activity(
        session,
        type_="blacklist.removed",
        detail=f"{entry.name or entry.telegram_username or entry.telegram_id} removed from blacklist",
        actor_id=user.id,
        entity_type="blacklist",
        entity_id=str(entry.id),
    )
    await session.commit()
    return MessageOut(message="Removed from blacklist")

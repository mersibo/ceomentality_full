from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BlacklistEntry


def normalize_email(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized or None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    prefix = "+" if value.strip().startswith("+") else ""
    digits = "".join(character for character in value if character.isdigit())
    return f"{prefix}{digits}" if 8 <= len(digits) <= 15 else None


def normalize_telegram_username(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
            break
    normalized = normalized.lstrip("@").split("?", 1)[0].strip("/")
    if not normalized or normalized.startswith("tg:") or normalized.lstrip("-").isdigit():
        return None
    return normalized


def normalize_telegram_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized.startswith("tg:"):
        normalized = normalized.removeprefix("tg:")
    return normalized if normalized.lstrip("-").isdigit() else None


async def find_blacklist_match(
    session: AsyncSession,
    *,
    telegram_id: str | int | None = None,
    telegram: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> BlacklistEntry | None:
    normalized_id = normalize_telegram_id(telegram_id) or normalize_telegram_id(telegram)
    normalized_username = normalize_telegram_username(telegram)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    matches = []
    if normalized_id:
        matches.append(BlacklistEntry.telegram_id == normalized_id)
    if normalized_username:
        matches.append(BlacklistEntry.telegram_username == normalized_username)
    if normalized_email:
        matches.append(BlacklistEntry.email == normalized_email)
    if normalized_phone:
        matches.append(BlacklistEntry.phone == normalized_phone)
    if not matches:
        return None
    return await session.scalar(
        select(BlacklistEntry)
        .where(BlacklistEntry.is_active.is_(True), or_(*matches))
        .order_by(BlacklistEntry.created_at.desc())
    )


async def ensure_not_blacklisted(
    session: AsyncSession,
    *,
    telegram_id: str | int | None = None,
    telegram: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> None:
    entry = await find_blacklist_match(
        session, telegram_id=telegram_id, telegram=telegram, email=email, phone=phone
    )
    if entry is None:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "blacklisted",
            "message": f"Вы находитесь в чёрном списке. Причина: {entry.reason}",
            "reason": entry.reason,
        },
    )

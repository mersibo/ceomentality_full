import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramOutboxMessage


def parse_telegram_chat_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.removeprefix("tg:")
    return normalized if normalized.lstrip("-").isdigit() else None


def parse_telegram_username(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    normalized = normalized.removeprefix("https://t.me/").removeprefix("http://t.me/")
    normalized = normalized.removeprefix("t.me/").removeprefix("@").split("?", 1)[0].strip("/")
    return normalized if re.fullmatch(r"[a-z][a-z0-9_]{4,31}", normalized) else None


async def enqueue_telegram_message(
    session: AsyncSession,
    *,
    chat_id: str | None,
    telegram_username: str | None = None,
    text: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> TelegramOutboxMessage | None:
    parsed_chat_id = parse_telegram_chat_id(chat_id)
    parsed_username = parse_telegram_username(telegram_username)
    if parsed_chat_id is None and parsed_username is None:
        return None
    message = TelegramOutboxMessage(
        chat_id=parsed_chat_id,
        telegram_username=parsed_username,
        text=text,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(message)
    return message

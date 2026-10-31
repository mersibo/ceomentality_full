from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import IntegrationSecretDep, SessionDep
from app.models import Candidate, TelegramOutboxMessage, TelegramUser
from app.schemas import (
    CandidateOut,
    MessageOut,
    TelegramApplicationIn,
    TelegramBlacklistCheckIn,
    TelegramBlacklistCheckOut,
    TelegramOutboxAckIn,
    TelegramOutboxMessageOut,
    TelegramUserOut,
    TelegramUserUpsertIn,
)
from app.services.audit import record_activity
from app.services.blacklist import ensure_not_blacklisted, find_blacklist_match
from app.services.candidates import person_key, unique_candidate_id
from app.services.formatting import candidate_out, initials
from app.services.telegram_outbox import parse_telegram_username

router = APIRouter(prefix="/api/integrations/telegram", tags=["telegram-integration"])


def outbox_message_out(message: TelegramOutboxMessage) -> TelegramOutboxMessageOut:
    return TelegramOutboxMessageOut(
        id=message.id,
        chatId=message.chat_id,
        text=message.text,
        entityType=message.entity_type,
        entityId=message.entity_id,
        attempts=message.attempts,
        createdAt=message.created_at,
    )


def telegram_handle(username: str | None, telegram_id: int) -> str:
    return f"@{username}" if username else f"tg:{telegram_id}"


async def upsert_telegram_user(session: SessionDep, payload: TelegramUserUpsertIn) -> TelegramUser:
    user = await session.scalar(select(TelegramUser).where(TelegramUser.telegram_id == payload.telegramId))
    now = datetime.now(UTC)
    if user is None:
        user = TelegramUser(telegram_id=payload.telegramId)
        session.add(user)
    user.username = payload.username
    user.first_name = payload.firstName
    user.last_name = payload.lastName
    user.language_code = payload.languageCode
    user.is_bot = payload.isBot
    user.last_seen_at = now
    return user


async def link_telegram_username(session: SessionDep, payload: TelegramUserUpsertIn) -> None:
    username = parse_telegram_username(payload.username)
    if not username:
        return

    candidates = (
        await session.scalars(
            select(Candidate).where(or_(Candidate.telegram_id.is_(None), Candidate.telegram_id == ""))
        )
    ).all()
    for candidate in candidates:
        if parse_telegram_username(candidate.telegram) == username:
            candidate.telegram_id = str(payload.telegramId)

    pending_messages = (
        await session.scalars(
            select(TelegramOutboxMessage).where(
                TelegramOutboxMessage.chat_id.is_(None),
                func.lower(TelegramOutboxMessage.telegram_username) == username,
                TelegramOutboxMessage.status.in_(["pending", "failed"]),
            )
        )
    ).all()
    for message in pending_messages:
        message.chat_id = str(payload.telegramId)
        message.status = "pending"
        message.attempts = 0
        message.last_error = None


@router.post("/users", response_model=TelegramUserOut, status_code=status.HTTP_200_OK)
async def remember_telegram_user(
    payload: TelegramUserUpsertIn,
    session: SessionDep,
    _: IntegrationSecretDep,
):
    user = await upsert_telegram_user(session, payload)
    await link_telegram_username(session, payload)
    await session.commit()
    return TelegramUserOut(
        telegramId=user.telegram_id,
        username=user.username,
        firstName=user.first_name,
        lastName=user.last_name,
    )


@router.get("/users", response_model=list[TelegramUserOut])
async def list_telegram_users(session: SessionDep, _: IntegrationSecretDep, limit: int = 5000):
    users = (
        await session.scalars(
            select(TelegramUser).order_by(TelegramUser.created_at).limit(max(1, min(limit, 10000)))
        )
    ).all()
    return [
        TelegramUserOut(
            telegramId=user.telegram_id,
            username=user.username,
            firstName=user.first_name,
            lastName=user.last_name,
        )
        for user in users
    ]


@router.post("/applications", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
async def submit_telegram_application(
    payload: TelegramApplicationIn,
    session: SessionDep,
    _: IntegrationSecretDep,
):
    if payload.applicationType.value != "purchase":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Club membership applications are created outside the Telegram bot",
        )
    existing = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.external_id == payload.submissionId)
    )
    if existing is not None:
        return candidate_out(existing)
    await ensure_not_blacklisted(
        session,
        telegram_id=payload.telegramId,
        telegram=payload.username,
    )
    await upsert_telegram_user(
        session,
        TelegramUserUpsertIn(
            telegramId=payload.telegramId,
            username=payload.username,
            firstName=payload.firstName,
            lastName=payload.lastName,
        ),
    )
    display_name = str(payload.raw.get("name") or "").strip()
    if not display_name:
        display_name = " ".join(filter(None, [payload.firstName, payload.lastName])).strip()
    if not display_name:
        display_name = payload.username or f"Telegram {payload.telegramId}"
    candidate_id = await unique_candidate_id(session, display_name)
    candidate = Candidate(
        id=candidate_id,
        name=display_name,
        initials=initials(display_name),
        role=str(payload.raw.get("position") or "")[:160],
        company=str(payload.raw.get("position") or "")[:200],
        status="Under review",
        wave="",
        code=None,
        summary=payload.text,
        expertise=str(payload.raw.get("activity") or "")[:120],
        country=str(payload.raw.get("country") or "")[:120],
        telegram=telegram_handle(payload.username, payload.telegramId),
        telegram_id=str(payload.telegramId),
        person_key=person_key(
            telegram_id=payload.telegramId,
            telegram=telegram_handle(payload.username, payload.telegramId),
            fallback=candidate_id,
        ),
        external_id=payload.submissionId,
        questionnaire_answers={"telegramApplication": payload.text, **payload.raw},
        social_links={"links": payload.raw.get("socials", "")},
        projects=[{"description": payload.raw.get("projects", "")}]
        if payload.raw.get("projects")
        else [],
        achievements=[str(payload.raw.get("achievements"))]
        if payload.raw.get("achievements")
        else [],
        manager_comments=[],
        decision={},
        member_profile=None,
        source=payload.source.value,
        stage=payload.applicationType.value,
        applied_at=datetime.now(UTC),
    )
    session.add(candidate)
    await record_activity(
        session,
        type_="integration.telegram.application_created",
        detail=f"Telegram application received from {candidate.telegram}",
        entity_type="candidate",
        entity_id=candidate.id,
        data={"telegramId": payload.telegramId, "applicationType": payload.applicationType.value},
    )
    await record_activity(
        session,
        type_="notification.manager",
        detail=f"New {payload.applicationType.value} application: {candidate.name}",
        entity_type="candidate",
        entity_id=candidate.id,
        data={"channel": "admin", "source": "telegram"},
    )
    await session.commit()
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate.id)
    )
    return candidate_out(candidate)


@router.post("/blacklist/check", response_model=TelegramBlacklistCheckOut)
async def check_telegram_blacklist(
    payload: TelegramBlacklistCheckIn,
    session: SessionDep,
    _: IntegrationSecretDep,
):
    entry = await find_blacklist_match(
        session,
        telegram_id=payload.telegramId,
        telegram=payload.username,
    )
    if entry is None:
        return TelegramBlacklistCheckOut(blocked=False)
    return TelegramBlacklistCheckOut(
        blocked=True,
        reason=entry.reason,
        message=f"Вы находитесь в чёрном списке. Причина: {entry.reason}",
    )


@router.get("/outbox", response_model=list[TelegramOutboxMessageOut])
async def get_telegram_outbox(
    session: SessionDep,
    _: IntegrationSecretDep,
    limit: int = 50,
):
    limit = max(1, min(limit, 100))
    messages = (
        await session.scalars(
            select(TelegramOutboxMessage)
            .where(
                TelegramOutboxMessage.chat_id.is_not(None),
                TelegramOutboxMessage.attempts < 10,
                or_(
                    TelegramOutboxMessage.status == "pending",
                    (
                        (TelegramOutboxMessage.status == "processing")
                        & (TelegramOutboxMessage.last_attempt_at < datetime.now(UTC) - timedelta(minutes=5))
                    ),
                ),
            )
            .order_by(TelegramOutboxMessage.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for message in messages:
        message.attempts += 1
        message.status = "processing"
        message.last_attempt_at = datetime.now(UTC)
    await session.commit()
    return [outbox_message_out(message) for message in messages]


@router.post("/outbox/{message_id}/ack", response_model=MessageOut)
async def acknowledge_telegram_message(
    message_id: UUID,
    payload: TelegramOutboxAckIn,
    session: SessionDep,
    _: IntegrationSecretDep,
):
    message = await session.get(TelegramOutboxMessage, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outbox message not found")
    if payload.status == "sent":
        message.status = "sent"
        message.processed_at = datetime.now(UTC)
        message.last_error = None
    else:
        message.status = "failed" if message.attempts >= 10 else "pending"
        message.last_error = payload.error or "Telegram delivery failed"
    await session.commit()
    return MessageOut(message=message.status)

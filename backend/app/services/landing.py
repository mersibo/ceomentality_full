import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.models import IdempotencyRecord, PublicSession


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def payload_digest(value: object) -> str:
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))


def public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12).replace('-', '').replace('_', '')}"


class LandingApiError(Exception):
    def __init__(
        self, status_code: int, code: str, fields: dict[str, str] | None = None,
        reason: str | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.fields = fields or {}
        self.reason = reason


async def find_public_session(
    request: Request, session: AsyncSession, settings
) -> PublicSession | None:
    token = request.cookies.get(settings.public_session_cookie_name)
    if not token:
        return None
    item = await session.scalar(select(PublicSession).where(PublicSession.token_hash == digest(token)))
    if item is None or item.expires_at <= datetime.now(UTC):
        return None
    item.last_seen_at = datetime.now(UTC)
    return item


async def require_public_session(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> PublicSession:
    item = await find_public_session(request, session, settings)
    if item is None:
        raise LandingApiError(401, "UNAUTHORIZED")
    if request.method != "GET":
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not secrets.compare_digest(item.csrf_hash, digest(csrf)):
            raise LandingApiError(403, "FORBIDDEN")
    return item


PublicSessionDep = Annotated[PublicSession, Depends(require_public_session)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=120)]


async def replay_idempotent(
    session: AsyncSession,
    public_session: PublicSession,
    operation: str,
    key: str,
    payload: object,
) -> dict | None:
    request_hash = payload_digest(payload)
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.session_id == public_session.id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )
    if record is None:
        return None
    if not secrets.compare_digest(record.request_hash, request_hash):
        raise LandingApiError(409, "VALIDATION_ERROR")
    return record.response_body


def remember_idempotent(
    session: AsyncSession,
    public_session: PublicSession,
    operation: str,
    key: str,
    payload: object,
    body: dict,
    status_code: int,
) -> None:
    session.add(
        IdempotencyRecord(
            session_id=public_session.id,
            operation=operation,
            key=key,
            request_hash=payload_digest(payload),
            response_body=body,
            response_status=status_code,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessCode, Candidate, Drop

ALPHABET = string.ascii_uppercase + string.digits


def generate_code(prefix: str, groups: int = 2) -> str:
    normalized = "".join(char for char in prefix.upper() if char in ALPHABET)[:24] or "CM"
    suffix = ["".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(groups)]
    return f"{normalized}-{'-'.join(suffix)}"


async def get_or_create_candidate_code(
    session: AsyncSession, candidate: Candidate, drop: Drop
) -> tuple[AccessCode, bool]:
    existing = await session.scalar(
        select(AccessCode).where(
            AccessCode.drop_id == drop.id,
            AccessCode.candidate_id == candidate.id,
            AccessCode.status.in_(["Active", "Redeemed"]),
        )
    )
    if existing is not None:
        candidate.code = existing.value
        candidate.wave = drop.name
        return existing, False

    prefix = drop.code.split("-", 1)[0] or "CM"
    while True:
        value = generate_code(prefix)
        if not await session.scalar(select(AccessCode.id).where(AccessCode.value == value)):
            break

    code = AccessCode(
        drop_id=drop.id,
        candidate_id=candidate.id,
        value=value,
        status="Active",
        valid_from=drop.valid_from,
        valid_until=drop.valid_until,
    )
    session.add(code)
    candidate.code = value
    candidate.wave = drop.name
    candidate.status = "Code assigned"
    drop.issued += 1
    return code, True

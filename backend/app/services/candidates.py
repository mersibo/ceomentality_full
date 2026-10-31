from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Candidate, CandidateNote
from app.schemas import CandidateCreate, ClubApplicationCreate, PurchaseApplicationCreate
from app.services.audit import record_activity
from app.services.blacklist import ensure_not_blacklisted
from app.services.formatting import initials, slugify


def person_key(*, telegram_id: str | int | None, telegram: str, fallback: str) -> str:
    if telegram_id is not None and str(telegram_id).strip():
        return f"tg:{str(telegram_id).strip()}"
    handle = telegram.strip().lower().removeprefix("@").removeprefix("https://t.me/").removeprefix("t.me/")
    if handle and not handle.startswith("tg:"):
        return f"handle:{handle.split('?', 1)[0]}"
    return f"candidate:{fallback}"


STATUS_TRANSITIONS = {
    "purchase": {
        "Under review": {"Approved", "Rejected", "Waitlisted", "Archived"},
        "Waitlisted": {"Under review", "Approved", "Rejected", "Archived"},
        "Approved": {"Code assigned", "Rejected", "Archived"},
        "Code assigned": {"Code used", "Archived"},
        "Code used": {"Archived"},
        "Rejected": {"Under review", "Archived"},
        "Archived": set(),
    },
    "club": {
        "Under review": {"Approved", "Rejected", "Waitlisted", "Archived"},
        "Waitlisted": {"Under review", "Approved", "Rejected", "Archived"},
        "Approved": {"Accepted", "Rejected", "Archived"},
        "Rejected": {"Under review", "Archived"},
        "Accepted": {"Archived"},
        "Archived": set(),
    },
}


def transition_allowed(stage: str, current: str, target: str) -> bool:
    return current == target or target in STATUS_TRANSITIONS.get(stage, {}).get(current, set())


async def unique_candidate_id(session: AsyncSession, name: str) -> str:
    base_id = slugify(name)
    candidate_id = base_id
    suffix = 2
    while await session.get(Candidate, candidate_id):
        candidate_id = f"{base_id}-{suffix}"
        suffix += 1
    return candidate_id


async def create_candidate_from_admin(
    session: AsyncSession,
    payload: CandidateCreate,
    *,
    actor_id=None,
) -> Candidate:
    candidate_id = await unique_candidate_id(session, payload.name)
    candidate = Candidate(
        id=candidate_id,
        name=payload.name,
        initials=initials(payload.name),
        role=payload.role,
        company=payload.company,
        status="Under review",
        wave=payload.wave,
        code=None,
        summary=payload.summary,
        expertise=payload.expertise,
        country=payload.country,
        telegram=payload.telegram,
        delivery_channel=payload.deliveryChannel,
        person_key=person_key(telegram_id=None, telegram=payload.telegram, fallback=candidate_id),
        questionnaire_answers=payload.questionnaireAnswers,
        social_links=payload.socialLinks,
        projects=payload.projects,
        achievements=payload.achievements,
        manager_comments=payload.managerComments,
        decision=payload.decision,
        member_profile=payload.memberProfile,
        source=payload.source.value,
        stage=payload.stage.value,
    )
    session.add(candidate)
    await record_activity(
        session,
        type_="candidate.created",
        detail=f"{candidate.name} created",
        actor_id=actor_id,
        entity_type="candidate",
        entity_id=candidate.id,
        data={"stage": candidate.stage, "source": candidate.source},
    )
    return candidate


async def create_purchase_application(
    session: AsyncSession,
    payload: PurchaseApplicationCreate,
    *,
    source_label: str = "site",
) -> Candidate:
    await ensure_not_blacklisted(
        session,
        telegram_id=payload.telegramId,
        telegram=payload.telegram,
    )
    candidate_id = await unique_candidate_id(session, payload.name)
    candidate = Candidate(
        id=candidate_id,
        name=payload.name,
        initials=initials(payload.name),
        role=payload.role,
        company=payload.company,
        status="Under review",
        wave="",
        code=None,
        summary=payload.summary,
        expertise=payload.expertise,
        country=payload.country,
        telegram=payload.telegram,
        telegram_id=payload.telegramId,
        delivery_channel=payload.deliveryChannel,
        person_key=person_key(telegram_id=payload.telegramId, telegram=payload.telegram, fallback=candidate_id),
        questionnaire_answers={},
        social_links=payload.socialLinks,
        projects=payload.projects,
        achievements=payload.achievements,
        manager_comments=[],
        decision={},
        member_profile=None,
        source=payload.source.value,
        stage="purchase",
        applied_at=datetime.now(UTC),
    )
    session.add(candidate)
    await record_activity(
        session,
        type_="application.purchase.created",
        detail=f"Purchase application received from {candidate.name}",
        entity_type="candidate",
        entity_id=candidate.id,
        data={"source": source_label},
    )
    await record_activity(
        session,
        type_="notification.manager",
        detail=f"New purchase application: {candidate.name}",
        entity_type="candidate",
        entity_id=candidate.id,
        data={"channel": "admin"},
    )
    return candidate


async def create_club_application(
    session: AsyncSession,
    payload: ClubApplicationCreate,
    *,
    source_label: str = "telegram",
) -> Candidate:
    await ensure_not_blacklisted(
        session,
        telegram_id=payload.telegramId,
        telegram=payload.telegram,
    )
    answers = {
        **payload.questionnaireAnswers,
        "businessInfo": payload.businessInfo,
        "additionalInfo": payload.additionalInfo,
    }
    candidate_id = await unique_candidate_id(session, payload.name)
    candidate = Candidate(
        id=candidate_id,
        name=payload.name,
        initials=initials(payload.name),
        role=payload.role,
        company=payload.company,
        status="Under review",
        wave="",
        code=None,
        summary=payload.additionalInfo or payload.businessInfo,
        expertise=payload.activity,
        country=payload.country,
        telegram=payload.telegram,
        telegram_id=payload.telegramId,
        person_key=person_key(telegram_id=payload.telegramId, telegram=payload.telegram, fallback=candidate_id),
        questionnaire_answers=answers,
        social_links=payload.socialLinks,
        projects=payload.projects,
        achievements=payload.achievements,
        manager_comments=[],
        decision={},
        member_profile=None,
        source=payload.source.value,
        stage="club",
        applied_at=datetime.now(UTC),
    )
    session.add(candidate)
    await record_activity(
        session,
        type_="application.club.created",
        detail=f"Club application received from {candidate.name}",
        entity_type="candidate",
        entity_id=candidate.id,
        data={"source": source_label},
    )
    await record_activity(
        session,
        type_="notification.manager",
        detail=f"New club candidate: {candidate.name}",
        entity_type="candidate",
        entity_id=candidate.id,
        data={"channel": "admin"},
    )
    return candidate


def append_manager_comment(candidate: Candidate, text: str) -> None:
    comments = list(candidate.manager_comments or [])
    comments.append(text)
    candidate.manager_comments = comments
    candidate.notes.append(CandidateNote(text=text))

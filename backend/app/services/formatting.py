import re
from datetime import UTC, date, datetime

from app.models import Candidate, Drop
from app.schemas import ActivityOut, CandidateOut, DropOut


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def initials(name: str) -> str:
    return "".join(part[:1] for part in name.split()).upper()[:2] or "CM"


def parse_frontend_date(value: str) -> datetime:
    try:
        if len(value) == 10:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(UTC)


def frontend_date(value: datetime) -> str:
    return value.date().isoformat()


def candidate_out(candidate: Candidate) -> CandidateOut:
    return CandidateOut(
        id=candidate.id,
        name=candidate.name,
        initials=candidate.initials,
        role=candidate.role,
        company=candidate.company,
        status=candidate.status,
        wave=candidate.wave,
        code=candidate.code,
        notes=[note.text for note in sorted(candidate.notes, key=lambda item: item.created_at)],
        summary=candidate.summary,
        expertise=candidate.expertise,
        country=candidate.country,
        telegram=candidate.telegram,
        telegramId=getattr(candidate, "telegram_id", None),
        deliveryChannel=getattr(candidate, "delivery_channel", "telegram") or "telegram",
        personKey=candidate.person_key,
        source=candidate.source,
        stage=candidate.stage,
        appliedAt=frontend_date(candidate.applied_at),
        questionnaireAnswers=getattr(candidate, "questionnaire_answers", {}) or {},
        socialLinks=getattr(candidate, "social_links", {}) or {},
        projects=getattr(candidate, "projects", []) or [],
        achievements=getattr(candidate, "achievements", []) or [],
        managerComments=getattr(candidate, "manager_comments", []) or [],
        decision=getattr(candidate, "decision", {}) or {},
        memberProfile=getattr(candidate, "member_profile", None),
        purchaseConfirmed=candidate.purchase_confirmed,
        purchasedAt=candidate.purchased_at,
        product=candidate.product,
        addedToGroupsAt=candidate.added_to_groups_at,
    )


def drop_out(drop: Drop) -> DropOut:
    return DropOut(
        id=drop.id,
        name=drop.name,
        description=drop.description,
        issued=drop.issued,
        redeemed=drop.redeemed,
        status=drop.status,
        validity=drop.validity,
        code=drop.code,
        codeType=drop.code_type,
        source=drop.source,
    )


def activity_out(event) -> ActivityOut:
    at = event.created_at.isoformat().replace("+00:00", "Z")
    return ActivityOut(id=str(event.id), type=event.type, detail=event.detail, at=at)

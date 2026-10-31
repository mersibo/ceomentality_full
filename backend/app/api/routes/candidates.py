from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUserDep, SessionDep
from app.models import ActivityEvent, Candidate, CandidateNote
from app.schemas import (
    ActivityOut,
    CandidateCreate,
    CandidateDecisionIn,
    CandidateNoteCreate,
    CandidateOut,
    CandidatePatch,
    CandidateProfileOut,
    MembershipUpdateIn,
    PaginatedCandidates,
    PurchaseUpdateIn,
)
from app.services.audit import record_activity
from app.services.candidates import (
    append_manager_comment,
    create_candidate_from_admin,
    person_key,
    transition_allowed,
)
from app.services.formatting import activity_out, candidate_out, initials
from app.services.telegram_outbox import enqueue_telegram_message

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("", response_model=PaginatedCandidates)
async def list_candidates(
    session: SessionDep,
    _: CurrentUserDep,
    status_: str | None = Query(default=None, alias="status"),
    wave: str | None = None,
    source: str | None = None,
    expertise: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = select(Candidate).options(selectinload(Candidate.notes))
    count_query = select(func.count()).select_from(Candidate)
    filters = []
    if status_:
        filters.append(Candidate.status == status_)
    if wave:
        filters.append(Candidate.wave == wave)
    if source:
        filters.append(Candidate.source == source)
    if expertise:
        filters.append(Candidate.expertise == expertise)
    if search:
        needle = f"%{search.lower()}%"
        filters.append(func.lower(func.concat(Candidate.name, " ", Candidate.company, " ", Candidate.telegram)).like(needle))
    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = await session.scalar(count_query) or 0
    items = (
        await session.scalars(
            query.order_by(Candidate.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
    ).all()
    return {
        "items": [candidate_out(item) for item in items],
        "pagination": {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit},
    }


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: str, session: SessionDep, _: CurrentUserDep):
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate_out(candidate)


@router.get("/{candidate_id}/profile", response_model=CandidateProfileOut)
async def get_unified_profile(candidate_id: str, session: SessionDep, _: CurrentUserDep):
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    applications = (
        await session.scalars(
            select(Candidate)
            .options(selectinload(Candidate.notes))
            .where(Candidate.person_key == candidate.person_key)
            .order_by(Candidate.applied_at.desc())
        )
    ).all()
    application_ids = [item.id for item in applications]
    events = (
        await session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.entity_type == "candidate", ActivityEvent.entity_id.in_(application_ids))
            .order_by(ActivityEvent.created_at.desc())
        )
    ).all()
    return CandidateProfileOut(
        personKey=candidate.person_key,
        applications=[candidate_out(item) for item in applications],
        history=[activity_out(event) for event in events],
    )


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
async def create_candidate(payload: CandidateCreate, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await create_candidate_from_admin(session, payload, actor_id=user.id)
    await session.commit()
    await session.refresh(candidate, ["notes"])
    return candidate_out(candidate)


@router.patch("/{candidate_id}", response_model=CandidateOut)
async def patch_candidate(
    candidate_id: str, payload: CandidatePatch, session: SessionDep, user: CurrentUserDep
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    before_status = candidate.status
    values = payload.model_dump(exclude_unset=True)
    if payload.status and not transition_allowed(candidate.stage, before_status, payload.status.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition: {before_status} -> {payload.status.value}",
        )
    field_map = {
        "questionnaireAnswers": "questionnaire_answers",
        "socialLinks": "social_links",
        "managerComments": "manager_comments",
        "memberProfile": "member_profile",
        "purchaseConfirmed": "purchase_confirmed",
        "purchasedAt": "purchased_at",
        "addedToGroupsAt": "added_to_groups_at",
    }
    for field, value in values.items():
        db_field = field_map.get(field, field)
        setattr(candidate, db_field, value.value if hasattr(value, "value") else value)
    if payload.name:
        candidate.initials = initials(payload.name)
    if payload.telegram is not None:
        candidate.person_key = person_key(
            telegram_id=candidate.telegram_id,
            telegram=candidate.telegram,
            fallback=candidate.id,
        )
    if payload.status and payload.status.value != before_status:
        await record_activity(
            session,
            type_="candidate.status_changed",
            detail=f"{candidate.name}: {before_status} -> {payload.status.value}",
            actor_id=user.id,
            entity_type="candidate",
            entity_id=candidate.id,
            data={"previousStatus": before_status, "nextStatus": payload.status.value},
        )
    else:
        await record_activity(
            session,
            type_="candidate.updated",
            detail=f"{candidate.name} updated",
            actor_id=user.id,
            entity_type="candidate",
            entity_id=candidate.id,
        )
    await session.commit()
    await session.refresh(candidate, ["notes"])
    return candidate_out(candidate)


@router.post("/{candidate_id}/decision", response_model=CandidateOut)
async def decide_candidate(
    candidate_id: str, payload: CandidateDecisionIn, session: SessionDep, user: CurrentUserDep
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    before_status = candidate.status
    if not transition_allowed(candidate.stage, before_status, payload.status.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition: {before_status} -> {payload.status.value}",
        )
    candidate.status = payload.status.value
    candidate.decision = {
        **(candidate.decision or {}),
        "status": payload.status.value,
        "reason": payload.reason,
        "decidedBy": str(user.id),
    }
    if payload.status.value == "Accepted":
        candidate.member_profile = {
            **(candidate.member_profile or {}),
            "acceptedAt": datetime.now(UTC).isoformat(),
            "status": "member",
        }
    if payload.comment:
        append_manager_comment(candidate, payload.comment)

    await record_activity(
        session,
        type_="candidate.status_changed",
        detail=f"{candidate.name}: {before_status} -> {payload.status.value}",
        actor_id=user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        data={"previousStatus": before_status, "nextStatus": payload.status.value, "reason": payload.reason},
    )
    await record_activity(
        session,
        type_="notification.user",
        detail=f"{candidate.name} notified: {payload.status.value}",
        actor_id=user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        data={"telegram": candidate.telegram, "status": payload.status.value},
    )
    notification_text = {
        "Approved": "Ваша заявка одобрена.",
        "Rejected": "К сожалению, заявка отклонена.",
        "Accepted": "Вы приняты в закрытый клуб.",
    }.get(payload.status.value, f"Статус заявки изменён: {payload.status.value}")
    await enqueue_telegram_message(
        session,
        chat_id=candidate.telegram_id,
        text=notification_text,
        entity_type="candidate",
        entity_id=candidate.id,
    )
    await session.commit()
    await session.refresh(candidate, ["notes"])
    return candidate_out(candidate)


@router.post("/{candidate_id}/purchase", response_model=CandidateOut)
async def update_purchase(
    candidate_id: str, payload: PurchaseUpdateIn, session: SessionDep, user: CurrentUserDep
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate_id)
    )
    if candidate is None or candidate.stage != "purchase":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase application not found")
    candidate.purchase_confirmed = payload.confirmed
    candidate.product = payload.product
    candidate.purchased_at = (payload.purchasedAt or datetime.now(UTC)) if payload.confirmed else None
    await record_activity(
        session,
        type_="purchase.confirmed" if payload.confirmed else "purchase.unconfirmed",
        detail=f"Purchase for {candidate.name}: {'confirmed' if payload.confirmed else 'not confirmed'}",
        actor_id=user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        data={"product": payload.product},
    )
    await session.commit()
    await session.refresh(candidate, ["notes"])
    return candidate_out(candidate)


@router.post("/{candidate_id}/membership", response_model=CandidateOut)
async def update_membership(
    candidate_id: str, payload: MembershipUpdateIn, session: SessionDep, user: CurrentUserDep
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate_id)
    )
    if candidate is None or candidate.stage != "club":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club application not found")
    if payload.addedToGroups and candidate.status != "Accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Candidate must be accepted first")
    candidate.added_to_groups_at = (payload.addedAt or datetime.now(UTC)) if payload.addedToGroups else None
    await record_activity(
        session,
        type_="membership.groups_updated",
        detail=f"{candidate.name}: closed groups membership updated",
        actor_id=user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        data={"addedToGroups": payload.addedToGroups},
    )
    await session.commit()
    await session.refresh(candidate, ["notes"])
    return candidate_out(candidate)


@router.get("/{candidate_id}/history", response_model=list[ActivityOut])
async def get_candidate_history(candidate_id: str, session: SessionDep, _: CurrentUserDep):
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    events = (
        await session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.entity_type == "candidate", ActivityEvent.entity_id == candidate.id)
            .order_by(ActivityEvent.created_at.desc())
        )
    ).all()
    return [activity_out(event) for event in events]


@router.post("/{candidate_id}/notes", response_model=CandidateOut)
async def add_note(candidate_id: str, payload: CandidateNoteCreate, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    candidate.notes.append(CandidateNote(text=payload.text, visibility=payload.visibility, author_id=user.id))
    await record_activity(
        session,
        type_="candidate.note_added",
        detail=f"Note added to {candidate.name}",
        actor_id=user.id,
        entity_type="candidate",
        entity_id=candidate.id,
    )
    await session.commit()
    await session.refresh(candidate, ["notes"])
    return candidate_out(candidate)

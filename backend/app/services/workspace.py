from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AccessCode, ActivityEvent, Candidate, CandidateNote, CodeBatch, Drop
from app.schemas import WorkspaceState
from app.services.candidates import person_key
from app.services.formatting import (
    activity_out,
    candidate_out,
    drop_out,
    initials,
    parse_frontend_date,
    slugify,
)


async def get_workspace(session: AsyncSession) -> WorkspaceState:
    candidates = (
        await session.scalars(
            select(Candidate).options(selectinload(Candidate.notes)).order_by(Candidate.created_at.desc())
        )
    ).all()
    drops = (await session.scalars(select(Drop).order_by(Drop.created_at.desc()))).all()
    activity = (
        await session.scalars(select(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(200))
    ).all()

    return WorkspaceState(
        candidates=[candidate_out(item) for item in candidates],
        drops=[drop_out(item) for item in drops],
        activity=[activity_out(item) for item in activity],
    )


async def replace_workspace(session: AsyncSession, state: WorkspaceState) -> WorkspaceState:
    await session.execute(delete(CandidateNote))
    await session.execute(delete(AccessCode))
    await session.execute(delete(CodeBatch))
    await session.execute(delete(Candidate))
    await session.execute(delete(Drop))
    await session.execute(delete(ActivityEvent))

    for item in state.candidates:
        candidate = Candidate(
            id=item.id,
            name=item.name,
            initials=item.initials or initials(item.name),
            role=item.role,
            company=item.company,
            status=item.status.value,
            wave=item.wave,
            code=item.code,
            summary=item.summary,
            expertise=item.expertise,
            country=item.country,
            telegram=item.telegram,
            telegram_id=item.telegramId,
            person_key=person_key(telegram_id=item.telegramId, telegram=item.telegram, fallback=item.id),
            questionnaire_answers=item.questionnaireAnswers,
            social_links=item.socialLinks,
            projects=item.projects,
            achievements=item.achievements,
            manager_comments=item.managerComments,
            decision=item.decision,
            member_profile=item.memberProfile,
            purchase_confirmed=item.purchaseConfirmed,
            purchased_at=item.purchasedAt,
            product=item.product,
            added_to_groups_at=item.addedToGroupsAt,
            source=item.source.value,
            stage=item.stage.value,
            applied_at=parse_frontend_date(item.appliedAt),
        )
        candidate.notes = [CandidateNote(text=note) for note in item.notes]
        session.add(candidate)

    used_drop_ids: set[str] = set()
    for item in state.drops:
        drop_id = item.id or slugify(item.name)
        if drop_id in used_drop_ids:
            drop_id = f"{drop_id}-{len(used_drop_ids) + 1}"
        used_drop_ids.add(drop_id)
        session.add(
            Drop(
                id=drop_id,
                name=item.name,
                description=item.description,
                issued=item.issued,
                redeemed=item.redeemed,
                status=item.status.value,
                validity=item.validity,
                code=item.code,
                code_type=item.codeType.value if item.codeType else None,
                source=item.source.value if item.source else None,
            )
        )

    for item in state.activity:
        session.add(ActivityEvent(type=item.type, detail=item.detail, created_at=parse_frontend_date(item.at)))

    await session.commit()
    return await get_workspace(session)

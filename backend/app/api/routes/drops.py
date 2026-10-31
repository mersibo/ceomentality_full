from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.models import AccessCode, Candidate, Drop, TelegramOutboxMessage, TelegramUser
from app.schemas import (
    DropCodeGenerateIn,
    DropCreate,
    DropIssuePreview,
    DropIssueResult,
    DropOut,
    DropPatch,
)
from app.services.audit import record_activity
from app.services.formatting import drop_out, slugify
from app.services.telegram_outbox import enqueue_telegram_message, parse_telegram_username
from app.services.access_codes import generate_code, get_or_create_candidate_code

router = APIRouter(prefix="/api/drops", tags=["drops"])


async def candidate_chat_id(session: SessionDep, candidate: Candidate) -> str | None:
    if candidate.telegram_id and candidate.telegram_id.lstrip("-").isdigit():
        return candidate.telegram_id
    username = parse_telegram_username(candidate.telegram)
    if not username:
        return None
    telegram_user = await session.scalar(
        select(TelegramUser).where(func.lower(TelegramUser.username) == username)
    )
    if telegram_user is None:
        return None
    candidate.telegram_id = str(telegram_user.telegram_id)
    return candidate.telegram_id


@router.get("", response_model=list[DropOut])
async def list_drops(session: SessionDep, _: CurrentUserDep):
    drops = (await session.scalars(select(Drop).order_by(Drop.created_at.desc()))).all()
    return [drop_out(item) for item in drops]


@router.delete("/{drop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drop(drop_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can delete drops")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    if drop.status == "Active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Close the active drop before deleting it")
    candidates = (await session.scalars(select(Candidate).where(Candidate.wave == drop.name))).all()
    for candidate in candidates:
        candidate.wave = None
        candidate.code = None
    await session.execute(delete(AccessCode).where(AccessCode.drop_id == drop.id))
    await record_activity(session, type_="drop.deleted", detail=f"Drop {drop.name} deleted", actor_id=user.id, entity_type="drop", entity_id=drop.id, data={"dropName": drop.name})
    await session.delete(drop)
    await session.commit()


@router.post("", response_model=DropOut, status_code=status.HTTP_201_CREATED)
async def create_drop(payload: DropCreate, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    base_id = slugify(payload.name)
    drop_id = base_id
    suffix = 2
    while await session.get(Drop, drop_id):
        drop_id = f"{base_id}-{suffix}"
        suffix += 1
    drop = Drop(
        id=drop_id,
        name=payload.name,
        description=payload.description,
        issued=payload.issued,
        redeemed=0,
        status="Draft",
        validity=payload.validity,
        code=(payload.code or generate_code("CM")).upper(),
    )
    session.add(drop)
    await record_activity(
        session,
        type_="drop.created",
        detail=f"{drop.name} created",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
    )
    await session.commit()
    return drop_out(drop)


@router.patch("/{drop_id}", response_model=DropOut)
async def patch_drop(drop_id: str, payload: DropPatch, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        db_field = {"codeType": "code_type"}.get(field, field)
        setattr(drop, db_field, value.value if hasattr(value, "value") else value)
    await record_activity(
        session,
        type_="drop.updated",
        detail=f"{drop.name} updated",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
    )
    await session.commit()
    return drop_out(drop)


@router.post("/{drop_id}/activate", response_model=DropOut)
async def activate_drop(drop_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can activate drops")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    active_drops = (await session.scalars(select(Drop).where(Drop.status == "Active"))).all()
    for item in active_drops:
        if item.id != drop.id:
            item.status = "Paused"
    drop.status = "Active"
    await record_activity(
        session,
        type_="drop.activated",
        detail=f"{drop.name} activated",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
    )
    await record_activity(
        session,
        type_="notification.user",
        detail=f"New drop started: {drop.name}",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
        data={"scope": "approved_purchase_candidates"},
    )
    approved_candidates = (
        await session.scalars(
            select(Candidate).where(
                Candidate.stage == "purchase",
                Candidate.status == "Approved",
                Candidate.telegram_id.is_not(None),
            )
        )
    ).all()
    for candidate in approved_candidates:
        await enqueue_telegram_message(
            session,
            chat_id=candidate.telegram_id,
            text=f"Начался новый дроп: {drop.name}.",
            entity_type="candidate",
            entity_id=candidate.id,
        )
    await session.commit()
    return drop_out(drop)


@router.post("/{drop_id}/generate-code", response_model=DropOut)
async def regenerate_drop_code(drop_id: str, payload: DropCodeGenerateIn, session: SessionDep, user: CurrentUserDep):
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can manage drop codes")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    if drop.status == "Active" or drop.issued > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Close the current drop before replacing an issued code",
        )
    drop.code = generate_code(payload.prefix)
    await record_activity(
        session,
        type_="drop.code_generated",
        detail=f"New access code generated for {drop.name}",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
        data={"code": drop.code},
    )
    await session.commit()
    return drop_out(drop)


@router.post("/{drop_id}/issue-code-to-approved", response_model=DropIssueResult)
async def issue_drop_code_to_approved(drop_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    if drop.status != "Active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Drop must be active")

    candidates = (
        await session.scalars(
            select(Candidate).where(
                Candidate.stage == "purchase",
                Candidate.delivery_channel == "telegram",
                Candidate.wave == drop.name,
                Candidate.status.in_(["Approved", "Code assigned"]),
            ).with_for_update(skip_locked=True)
        )
    ).all()
    notifications = []
    queued_to_telegram = []
    skipped_telegram = []
    for candidate in candidates:
        message_key = f"{drop.id}:{candidate.id}"
        current_code = await session.scalar(
            select(AccessCode.id).where(
                AccessCode.drop_id == drop.id,
                AccessCode.candidate_id == candidate.id,
                AccessCode.status.in_(["Active", "Redeemed"]),
            )
        )
        already_queued = await session.scalar(
            select(TelegramOutboxMessage.id).where(
                TelegramOutboxMessage.status != "failed",
                TelegramOutboxMessage.entity_type == "drop_code",
                TelegramOutboxMessage.entity_id == message_key,
            )
        )
        if current_code and already_queued:
            continue
        username = parse_telegram_username(candidate.telegram)
        chat_id = await candidate_chat_id(session, candidate)
        if not chat_id and not username:
            skipped_telegram.append(candidate.id)
            continue
        code, _ = await get_or_create_candidate_code(session, candidate, drop)
        notifications.append({"candidateId": candidate.id, "telegram": candidate.telegram, "code": code.value})
        await record_activity(
            session,
            type_="code.assigned",
            detail=f"{code.value} issued to {candidate.name}",
            actor_id=user.id,
            entity_type="candidate",
            entity_id=candidate.id,
            data={"dropId": drop.id, "dropName": drop.name, "code": code.value},
        )
        await record_activity(
            session,
            type_="notification.user",
            detail=f"Access code sent to {candidate.name}",
            actor_id=user.id,
            entity_type="candidate",
            entity_id=candidate.id,
            data={"telegram": candidate.telegram, "code": code.value},
        )
        outbox_message = await enqueue_telegram_message(
            session,
            chat_id=chat_id,
            telegram_username=username,
            text=(
                f"Ваша заявка на участие в дропе «{drop.name}» одобрена.\n\n"
                f"Код доступа: {code.value}\n"
                f"Срок действия: {drop.validity or 'уточняется организатором'}"
            ),
            entity_type="drop_code",
            entity_id=message_key,
        )
        if outbox_message:
            queued_to_telegram.append(candidate.id)
    await session.commit()
    return DropIssueResult(
        drop=drop_out(drop),
        issuedTo=[item["candidateId"] for item in notifications],
        queuedToTelegram=queued_to_telegram,
        skippedTelegram=skipped_telegram,
        notifications=notifications,
    )


@router.get("/{drop_id}/issue-preview", response_model=DropIssuePreview)
async def preview_drop_code_recipients(drop_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    candidates = (
        await session.scalars(
            select(Candidate)
            .where(
                Candidate.stage == "purchase",
                Candidate.delivery_channel == "telegram",
                Candidate.wave == drop.name,
                Candidate.status.in_(["Approved", "Code assigned"]),
            )
            .order_by(Candidate.name)
        )
    ).all()
    recipients = []
    for candidate in candidates:
        message_key = f"{drop.id}:{candidate.id}"
        current_code = await session.scalar(
            select(AccessCode.id).where(
                AccessCode.drop_id == drop.id,
                AccessCode.candidate_id == candidate.id,
                AccessCode.status.in_(["Active", "Redeemed"]),
            )
        )
        already_queued = await session.scalar(
            select(TelegramOutboxMessage.id).where(
                TelegramOutboxMessage.status != "failed",
                TelegramOutboxMessage.entity_type == "drop_code",
                TelegramOutboxMessage.entity_id == message_key,
            )
        )
        if current_code and already_queued:
            continue
        recipients.append(
            {
                "candidateId": candidate.id,
                "name": candidate.name,
                "telegram": candidate.telegram,
                "deliverable": bool(
                    await candidate_chat_id(session, candidate)
                    or parse_telegram_username(candidate.telegram)
                ),
            }
        )
    await session.commit()
    deliverable = sum(1 for item in recipients if item["deliverable"])
    return {
        "dropId": drop.id,
        "dropName": drop.name,
        "code": drop.code,
        "recipients": recipients,
        "deliverable": deliverable,
        "missingTelegram": len(recipients) - deliverable,
    }


@router.post("/{drop_id}/close", response_model=DropOut)
async def close_drop(drop_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can close drops")
    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")
    drop.status = "Closed"
    drop.code = generate_code("CM")
    assigned_codes = (
        await session.scalars(select(AccessCode).where(AccessCode.status == "Active"))
    ).all()
    for code in assigned_codes:
        if code.drop_id == drop.id:
            code.status = "Expired"
    await record_activity(
        session,
        type_="drop.closed",
        detail=f"{drop.name} closed and access code invalidated",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
        data={},
    )
    await record_activity(
        session,
        type_="notification.user",
        detail=f"Access period ended for {drop.name}",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
        data={"scope": "issued_code_candidates"},
    )
    candidates = (
        await session.scalars(select(Candidate).where(Candidate.wave == drop.name, Candidate.code.is_not(None)))
    ).all()
    for candidate in candidates:
        await enqueue_telegram_message(
            session,
            chat_id=candidate.telegram_id,
            text=f"Доступ по дропу {drop.name} завершён.",
            entity_type="candidate",
            entity_id=candidate.id,
        )
    await session.commit()
    return drop_out(drop)

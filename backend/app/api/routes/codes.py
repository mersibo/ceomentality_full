from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.models import AccessCode, Candidate, CodeBatch, Drop
from app.schemas import AccessCodeOut, CodeBatchCreate, CodeBatchOut, RedeemCodeIn, RedeemCodeOut
from app.services.audit import record_activity
from app.services.access_codes import generate_code, get_or_create_candidate_code

router = APIRouter(tags=["access-codes"])
def access_code_out(code: AccessCode) -> AccessCodeOut:
    return AccessCodeOut(
        id=code.id,
        candidateId=code.candidate_id,
        value=code.value,
        status=code.status,
        validFrom=code.valid_from,
        validUntil=code.valid_until,
        redeemedAt=code.redeemed_at,
        createdAt=code.created_at,
    )


@router.get("/api/access-codes", response_model=list[AccessCodeOut])
async def list_access_codes(session: SessionDep, _: CurrentUserDep):
    codes = (await session.scalars(select(AccessCode).order_by(AccessCode.created_at.desc()).limit(500))).all()
    return [access_code_out(code) for code in codes]


@router.post("/api/code-batches", response_model=CodeBatchOut, status_code=status.HTTP_201_CREATED)
async def create_code_batch(payload: CodeBatchCreate, session: SessionDep, user: CurrentUserDep):
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can generate code batches")
    drop = await session.get(Drop, payload.dropId)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")

    batch = CodeBatch(
        drop_id=drop.id,
        code_type=payload.codeType.value,
        issued=payload.quantity,
        redeemed=0,
        status="Active",
        prefix=payload.prefix,
        created_by_id=user.id,
    )
    session.add(batch)
    await session.flush()

    created = 0
    while created < payload.quantity:
        value = generate_code(payload.prefix)
        exists = await session.scalar(select(AccessCode.id).where(AccessCode.value == value))
        if exists:
            continue
        session.add(
            AccessCode(
                batch_id=batch.id,
                value=value,
                status="Active",
                valid_from=payload.validFrom,
                valid_until=payload.validUntil,
            )
        )
        created += 1

    drop.issued += payload.quantity
    drop.status = "Active"
    await record_activity(
        session,
        type_="codes.generated",
        detail=f"{payload.quantity} codes generated for {drop.name}",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
        data={"batchId": str(batch.id), "quantity": payload.quantity},
    )
    await session.commit()
    return CodeBatchOut(
        id=batch.id,
        dropId=batch.drop_id,
        codeType=batch.code_type,
        issued=batch.issued,
        redeemed=batch.redeemed,
        status=batch.status,
    )


@router.post("/api/candidates/{candidate_id}/access-code")
async def assign_code(candidate_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    candidate = await session.scalar(select(Candidate).where(Candidate.id == candidate_id).with_for_update())
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    if candidate.stage != "purchase" or candidate.status != "Approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only approved purchase applications can receive a code")
    if candidate.code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Candidate already has an access code")
    drop = await session.scalar(select(Drop).where(Drop.status == "Active").limit(1))
    if drop is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active drop")
    code, _ = await get_or_create_candidate_code(session, candidate, drop)
    await record_activity(
        session,
        type_="code.assigned",
        detail=f"{code.value} assigned to {candidate.name}",
        actor_id=user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        data={"dropId": drop.id, "dropName": drop.name, "code": code.value},
    )
    await session.commit()
    await session.refresh(code)
    return access_code_out(code)


@router.post("/api/access-codes/redeem", response_model=RedeemCodeOut)
async def redeem_code(payload: RedeemCodeIn, session: SessionDep):
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    code_query = select(AccessCode).where(AccessCode.value == payload.code).with_for_update()
    if payload.candidateId:
        code_query = code_query.where(AccessCode.candidate_id == payload.candidateId)
    matching_codes = (await session.scalars(code_query)).all()
    if len(matching_codes) != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    code = matching_codes[0]
    if code.status == "Redeemed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code already redeemed")
    if code.status != "Active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code is not active")
    if code.valid_from and code.valid_from > now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code is not active yet")
    if code.valid_until and code.valid_until < now:
        code.status = "Expired"
        await session.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code has expired")
    code.status = "Redeemed"
    code.redeemed_at = now
    if code.candidate_id:
        candidate = await session.get(Candidate, code.candidate_id)
        if candidate:
            candidate.status = "Code used"
            drop = await session.get(Drop, code.drop_id) if code.drop_id else None
            if drop:
                drop.redeemed += 1
    await record_activity(
        session,
        type_="code.redeemed",
        detail=f"{code.value} redeemed",
        entity_type="access_code",
        entity_id=str(code.id),
    )
    await session.commit()
    return RedeemCodeOut(success=True, code={"status": code.status, "redeemedAt": code.redeemed_at})

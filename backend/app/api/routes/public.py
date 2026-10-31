from fastapi import APIRouter, status
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.api.deps import IntegrationSecretDep, SessionDep
from app.models import Candidate
from app.schemas import CandidateOut, ClubApplicationCreate, PurchaseApplicationCreate
from app.services.candidates import create_club_application, create_purchase_application
from app.services.formatting import candidate_out

router = APIRouter(tags=["public-applications"])


@router.post(
    "/api/public/purchase-applications",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_purchase_application(payload: PurchaseApplicationCreate, session: SessionDep):
    candidate = await create_purchase_application(session, payload, source_label="website")
    await session.commit()
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate.id)
    )
    return candidate_out(candidate)


@router.post(
    "/api/public/club-applications",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_club_application(payload: ClubApplicationCreate, session: SessionDep):
    candidate = await create_club_application(session, payload, source_label="telegram_qr")
    await session.commit()
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate.id)
    )
    return candidate_out(candidate)


@router.post(
    "/api/bot/purchase-applications",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
)
async def bot_purchase_application(
    payload: PurchaseApplicationCreate,
    session: SessionDep,
    _: IntegrationSecretDep,
):
    candidate = await create_purchase_application(session, payload, source_label="telegram_bot")
    await session.commit()
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate.id)
    )
    return candidate_out(candidate)


@router.post(
    "/api/bot/club-applications",
    response_model=CandidateOut,
    status_code=status.HTTP_201_CREATED,
)
async def bot_club_application(
    payload: ClubApplicationCreate,
    session: SessionDep,
    _: IntegrationSecretDep,
):
    candidate = await create_club_application(session, payload, source_label="telegram_bot")
    await session.commit()
    candidate = await session.scalar(
        select(Candidate).options(selectinload(Candidate.notes)).where(Candidate.id == candidate.id)
    )
    return candidate_out(candidate)

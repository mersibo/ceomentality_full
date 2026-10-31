from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep
from app.models import (
    Candidate,
    Drop,
    EmailCampaign,
    EmailOutboxMessage,
    EmailSettings,
)
from app.schemas import (
    EmailCampaignCreate,
    EmailCampaignOut,
    EmailCampaignPreviewIn,
    EmailCampaignPreviewOut,
    EmailSettingsOut,
    EmailSettingsPatch,
)
from app.services.audit import record_activity
from app.services.email_campaigns import candidate_email, render_email
from app.services.access_codes import get_or_create_candidate_code

router = APIRouter(prefix="/api/email", tags=["email"])


async def campaign_candidates(session: SessionDep, drop: Drop) -> list[Candidate]:
    return list(
        (
            await session.scalars(
                select(Candidate)
                .where(
                    Candidate.stage == "purchase",
                    Candidate.delivery_channel == "email",
                    Candidate.wave == drop.name,
                    Candidate.status.in_(["Approved", "Code assigned"]),
                )
                .order_by(Candidate.name)
            )
        ).all()
    )


def campaign_out(campaign: EmailCampaign, drop_name: str) -> EmailCampaignOut:
    return EmailCampaignOut(
        id=campaign.id,
        dropId=campaign.drop_id,
        dropName=drop_name,
        subject=campaign.subject,
        body=campaign.body,
        status=campaign.status,
        recipientCount=campaign.recipient_count,
        sentCount=campaign.sent_count,
        failedCount=campaign.failed_count,
        createdAt=campaign.created_at,
        completedAt=campaign.completed_at,
    )


@router.get("/settings", response_model=EmailSettingsOut)
async def get_email_settings(
    session: SessionDep, settings: SettingsDep, _user: CurrentUserDep
):
    item = await session.get(EmailSettings, 1)
    if item is None:
        item = EmailSettings(
            id=1,
            from_email="ceomentality@internet.ru",
            from_name="CEOMENTALITY",
            sending_key_id=settings.rusender_key_id,
        )
        session.add(item)
        await session.commit()
    return EmailSettingsOut(
        fromEmail=item.from_email,
        fromName=item.from_name,
        sendingKeyId=item.sending_key_id,
        providerConfigured=bool(
            settings.email_provider == "rusender" and settings.rusender_api_token
        ),
    )


@router.patch("/settings", response_model=EmailSettingsOut)
async def patch_email_settings(
    payload: EmailSettingsPatch,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    item = await session.get(EmailSettings, 1)
    if item is None:
        item = EmailSettings(id=1)
        session.add(item)
    item.from_email = str(payload.fromEmail).lower()
    item.from_name = payload.fromName.strip()
    item.sending_key_id = payload.sendingKeyId
    item.updated_by_id = user.id
    await record_activity(
        session,
        type_="email.settings_updated",
        detail=f"Email sender updated to {item.from_name} <{item.from_email}>",
        actor_id=user.id,
        entity_type="email_settings",
        entity_id="1",
    )
    await session.commit()
    return EmailSettingsOut(
        fromEmail=item.from_email,
        fromName=item.from_name,
        sendingKeyId=item.sending_key_id,
        providerConfigured=bool(
            settings.email_provider == "rusender" and settings.rusender_api_token
        ),
    )


@router.post("/campaigns/preview", response_model=EmailCampaignPreviewOut)
async def preview_campaign(
    payload: EmailCampaignPreviewIn, session: SessionDep, _user: CurrentUserDep
):
    drop = await session.get(Drop, payload.dropId)
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop not found")
    candidates = await campaign_candidates(session, drop)
    recipients = []
    for candidate in candidates:
        email = candidate_email(candidate)
        recipients.append(
            {
                "candidateId": candidate.id,
                "name": candidate.name,
                "email": email,
                "deliverable": bool(email),
            }
        )
    deliverable = sum(1 for item in recipients if item["deliverable"])
    return {
        "dropId": drop.id,
        "dropName": drop.name,
        "code": drop.code,
        "recipients": recipients,
        "deliverable": deliverable,
        "missingEmail": len(recipients) - deliverable,
    }


@router.get("/campaigns", response_model=list[EmailCampaignOut])
async def list_campaigns(session: SessionDep, _user: CurrentUserDep):
    campaigns = (
        await session.scalars(
            select(EmailCampaign).order_by(EmailCampaign.created_at.desc()).limit(100)
        )
    ).all()
    drops = (
        {
            item.id: item.name
            for item in (
                await session.scalars(
                    select(Drop).where(
                        Drop.id.in_([campaign.drop_id for campaign in campaigns])
                    )
                )
            ).all()
        }
        if campaigns
        else {}
    )
    return [campaign_out(item, drops.get(item.drop_id, item.drop_id)) for item in campaigns]


@router.post(
    "/campaigns",
    response_model=EmailCampaignOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    payload: EmailCampaignCreate,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if settings.email_provider != "rusender" or not settings.rusender_api_token:
        raise HTTPException(status_code=503, detail="RuSender is not configured")
    drop = await session.get(Drop, payload.dropId)
    if drop is None:
        raise HTTPException(status_code=404, detail="Drop not found")
    if drop.status != "Active":
        raise HTTPException(status_code=409, detail="Drop must be active")
    candidates = await campaign_candidates(session, drop)
    deliverable = [(candidate, candidate_email(candidate)) for candidate in candidates]
    deliverable = [(candidate, email) for candidate, email in deliverable if email]
    if not deliverable:
        raise HTTPException(status_code=409, detail="No recipients with email")
    campaign = EmailCampaign(
        id=uuid4(),
        drop_id=drop.id,
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        status="queued",
        recipient_count=len(deliverable),
        created_by_id=user.id,
    )
    session.add(campaign)
    await session.flush()
    for candidate, email in deliverable:
        code, _ = await get_or_create_candidate_code(session, candidate, drop)
        session.add(
            EmailOutboxMessage(
                campaign_id=campaign.id,
                candidate_id=candidate.id,
                recipient_email=email,
                recipient_name=candidate.name,
                subject=render_email(campaign.subject, candidate, drop, code.value),
                body=render_email(campaign.body, candidate, drop, code.value),
                idempotency_key=f"campaign-{campaign.id}-{candidate.id}"[:150],
            )
        )
    await record_activity(
        session,
        type_="email.campaign_queued",
        detail=f"Email campaign queued for {drop.name}: {len(deliverable)} recipients",
        actor_id=user.id,
        entity_type="drop",
        entity_id=drop.id,
        data={"campaignId": str(campaign.id), "recipients": len(deliverable)},
    )
    await session.commit()
    await session.refresh(campaign)
    return campaign_out(campaign, drop.name)

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import EmailCampaign, EmailOutboxMessage, EmailSettings
from app.services.rusender import RuSenderClient, RuSenderError

logger = logging.getLogger(__name__)


async def claim_message() -> UUID | None:
    retry_before = datetime.now(UTC) - timedelta(seconds=60)
    async with AsyncSessionLocal() as session:
        message = await session.scalar(
            select(EmailOutboxMessage)
            .where(
                EmailOutboxMessage.attempts < 5,
                or_(
                    (EmailOutboxMessage.status == "pending")
                    & or_(
                        EmailOutboxMessage.last_attempt_at.is_(None),
                        EmailOutboxMessage.last_attempt_at <= retry_before,
                    ),
                    (EmailOutboxMessage.status == "sending")
                    & (EmailOutboxMessage.last_attempt_at <= retry_before),
                ),
            )
            .order_by(EmailOutboxMessage.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if message is None:
            return None
        message.status = "sending"
        message.attempts += 1
        message.last_attempt_at = datetime.now(UTC)
        await session.commit()
        return message.id


async def update_campaign(session, campaign_id: UUID) -> None:
    campaign = await session.get(EmailCampaign, campaign_id)
    if campaign is None:
        return
    rows = (
        await session.execute(
            select(EmailOutboxMessage.status, func.count())
            .where(EmailOutboxMessage.campaign_id == campaign_id)
            .group_by(EmailOutboxMessage.status)
        )
    ).all()
    counts = dict(rows)
    campaign.sent_count = counts.get("sent", 0)
    campaign.failed_count = counts.get("failed", 0)
    if not counts.get("pending", 0) and not counts.get("sending", 0):
        campaign.status = "completed" if not campaign.failed_count else "completed_with_errors"
        campaign.completed_at = datetime.now(UTC)
    else:
        campaign.status = "sending"


async def deliver(message_id: UUID, client: RuSenderClient) -> None:
    async with AsyncSessionLocal() as session:
        message = await session.get(EmailOutboxMessage, message_id)
        email_settings = await session.get(EmailSettings, 1)
        if message is None:
            return
        if email_settings is None:
            email_settings = EmailSettings(
                id=1,
                from_email="ceomentality@internet.ru",
                from_name="CEOMENTALITY",
                sending_key_id=client.key_id,
            )
            session.add(email_settings)
            await session.flush()
        try:
            # A value saved in CRM overrides the server default. An empty CRM field
            # must not discard RUSENDER_KEY_ID from the environment.
            client.key_id = email_settings.sending_key_id or client.key_id
            provider_id = await client.send(
                to_email=message.recipient_email,
                to_name=message.recipient_name,
                from_email=email_settings.from_email,
                from_name=email_settings.from_name,
                subject=message.subject,
                text=message.body,
                idempotency_key=message.idempotency_key,
            )
            message.status = "sent"
            message.provider_id = provider_id
            message.last_error = None
            message.processed_at = datetime.now(UTC)
            logger.info("Email %s sent to %s via RuSender", message.id, message.recipient_email)
        except RuSenderError as error:
            message.last_error = str(error)[:2000]
            message.status = "failed" if message.attempts >= 5 else "pending"
            logger.warning(
                "Email %s to %s failed on attempt %s: %s",
                message.id,
                message.recipient_email,
                message.attempts,
                error,
            )
        await update_campaign(session, message.campaign_id)
        await session.commit()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    if settings.email_provider != "rusender" or not settings.rusender_api_token:
        raise RuntimeError("RuSender is not configured")
    client = RuSenderClient(
        str(settings.rusender_api_url),
        settings.rusender_api_token,
        settings.rusender_key_id,
    )
    while True:
        message_id = await claim_message()
        if message_id is None:
            await asyncio.sleep(settings.email_outbox_poll_seconds)
            continue
        await deliver(message_id, client)


if __name__ == "__main__":
    asyncio.run(main())

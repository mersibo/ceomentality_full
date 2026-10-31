import asyncio

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import (
    AccessCode,
    ActivityEvent,
    Candidate,
    CandidateNote,
    CheckoutQuote,
    CodeBatch,
    ContactMessage,
    Drop,
    EmailCampaign,
    EmailOutboxMessage,
    EmailSettings,
    IdempotencyRecord,
    MembershipInvitation,
    ProductVariant,
    PublicSession,
    StoreOrder,
    StorePayment,
    User,
)


async def seed_database(session: AsyncSession, *, force: bool = False) -> None:
    # Serializes initialization across multiple workers or backend replicas.
    await session.execute(text("SELECT pg_advisory_xact_lock(734221901)"))
    settings = get_settings()
    existing_user = await session.scalar(select(User).where(User.email == settings.first_superuser_email))
    if existing_user is None:
        session.add(
            User(
                name="Club Manager",
                email=settings.first_superuser_email,
                password_hash=hash_password(settings.first_superuser_password),
                role="founder",
            )
        )

    for variant_id, name in (
        ("ceowallet-white", "CEOWALLET White"),
        ("ceowallet-black", "CEOWALLET Black"),
    ):
        if await session.get(ProductVariant, variant_id) is None:
            session.add(
                ProductVariant(
                    id=variant_id,
                    name=name,
                    unit_price=299000,
                    currency="RUB",
                    available=True,
                    max_quantity=10,
                )
            )

    if force:
        await session.execute(delete(EmailOutboxMessage))
        await session.execute(delete(EmailCampaign))
        await session.execute(delete(EmailSettings))
        await session.execute(delete(IdempotencyRecord))
        await session.execute(delete(StorePayment))
        await session.execute(delete(StoreOrder))
        await session.execute(delete(CheckoutQuote))
        await session.execute(delete(MembershipInvitation))
        await session.execute(delete(ContactMessage))
        await session.execute(delete(PublicSession))
        await session.execute(delete(CandidateNote))
        await session.execute(delete(AccessCode))
        await session.execute(delete(CodeBatch))
        await session.execute(delete(Candidate))
        await session.execute(delete(Drop))
        await session.execute(delete(ActivityEvent))

    await session.commit()


async def ensure_seeded(session: AsyncSession) -> None:
    await seed_database(session)


async def main() -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await seed_database(session)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import User


async def reset_admin_password() -> str:
    settings = get_settings()
    email = str(settings.first_superuser_email).strip().lower()
    async with AsyncSessionLocal() as session:
        user = await session.scalar(
            select(User).where(func.lower(User.email) == email).with_for_update()
        )
        if user is None:
            raise RuntimeError(f"CRM user {email} was not found")
        user.password_hash = hash_password(settings.first_superuser_password)
        user.is_active = True
        await session.commit()
    return email


async def main() -> None:
    email = await reset_admin_password()
    print(f"CRM password reset for {email}")


if __name__ == "__main__":
    asyncio.run(main())

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
BCRYPT_MAX_PASSWORD_LENGTH = 72


def _normalize_bcrypt_password(password: str) -> str:
    return password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_LENGTH].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_normalize_bcrypt_password(password))


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(_normalize_bcrypt_password(password), password_hash)


def create_session_token(user_id: UUID) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.secret_key, algorithm=ALGORITHM)


def parse_session_token(token: str) -> UUID | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        return UUID(subject) if subject else None
    except (JWTError, ValueError):
        return None

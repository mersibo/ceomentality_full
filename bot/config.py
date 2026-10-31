from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    bot_token: str
    crm_api_url: str
    integration_secret: str
    admin_ids: frozenset[int]
    outbox_poll_seconds: float
    redis_url: str | None
    telegram_proxy_url: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("BOT_TOKEN", "").strip()
        secret = os.environ.get("TELEGRAM_INTEGRATION_SECRET", "").strip()
        api_url = os.environ.get("CRM_API_URL", "http://backend:8000").rstrip("/")
        if not token:
            raise RuntimeError("BOT_TOKEN is required")
        if len(secret) < 24:
            raise RuntimeError("TELEGRAM_INTEGRATION_SECRET must contain at least 24 characters")
        admin_ids = frozenset(
            int(item.strip())
            for item in os.environ.get("BOT_ADMIN_IDS", "").split(",")
            if item.strip()
        )
        return cls(
            bot_token=token,
            crm_api_url=api_url,
            integration_secret=secret,
            admin_ids=admin_ids,
            outbox_poll_seconds=max(1.0, float(os.environ.get("OUTBOX_POLL_SECONDS", "3"))),
            redis_url=os.environ.get("REDIS_URL") or None,
            telegram_proxy_url=os.environ.get("TELEGRAM_PROXY_URL") or None,
        )

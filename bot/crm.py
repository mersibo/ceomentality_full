import asyncio
from typing import Any

import httpx


class CRMError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class CRMClient:
    def __init__(self, base_url: str, integration_secret: str):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Integration-Secret": integration_secret},
            timeout=httpx.Timeout(15.0),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, path: str, **kwargs) -> Any:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.request(method, path, **kwargs)
                if response.status_code < 500:
                    if response.is_error:
                        payload = response.json() if response.content else {}
                        detail = payload.get("detail", f"CRM returned {response.status_code}")
                        raise CRMError(str(detail), response.status_code)
                    return response.json() if response.content else None
                last_error = CRMError(f"CRM returned {response.status_code}", response.status_code)
            except CRMError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                last_error = error
            await asyncio.sleep(0.5 * (2**attempt))
        raise CRMError(f"CRM is unavailable: {last_error}", 503)

    async def remember_user(self, user) -> None:
        await self.request(
            "POST",
            "/api/integrations/telegram/users",
            json={
                "telegramId": user.id,
                "username": user.username,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "languageCode": user.language_code,
                "isBot": user.is_bot,
            },
        )

    async def check_blacklist(self, user) -> dict:
        return await self.request(
            "POST",
            "/api/integrations/telegram/blacklist/check",
            json={"telegramId": user.id, "username": user.username},
        )

    async def submit_application(self, user, *, submission_id: str, flow: str, answers: dict) -> dict:
        summary = "\n".join(f"{key}: {value}" for key, value in answers.items())
        return await self.request(
            "POST",
            "/api/integrations/telegram/applications",
            json={
                "submissionId": submission_id,
                "telegramId": user.id,
                "username": user.username,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "text": summary,
                "applicationType": flow,
                "source": "Telegram bot",
                "raw": answers,
            },
        )

    async def outbox(self) -> list[dict]:
        return await self.request("GET", "/api/integrations/telegram/outbox?limit=50")

    async def acknowledge(self, message_id: str, *, sent: bool, error: str | None = None) -> None:
        await self.request(
            "POST",
            f"/api/integrations/telegram/outbox/{message_id}/ack",
            json={"status": "sent" if sent else "failed", "error": error},
        )

    async def users(self) -> list[dict]:
        return await self.request("GET", "/api/integrations/telegram/users?limit=10000")

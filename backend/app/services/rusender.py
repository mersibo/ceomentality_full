import html
from typing import Any

import httpx


class RuSenderError(RuntimeError):
    pass


class RuSenderClient:
    def __init__(self, api_url: str, token: str, key_id: int | None = None):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.key_id = key_id

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        headers = {
            **kwargs.pop("headers", {}),
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            try:
                response = await client.request(
                    method, f"{self.api_url}{path}", headers=headers, **kwargs
                )
            except httpx.HTTPError as error:
                raise RuSenderError("RuSender API is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise RuSenderError(f"RuSender HTTP {response.status_code}: {detail}")
        try:
            return response.json()
        except ValueError as error:
            raise RuSenderError("RuSender returned invalid JSON") from error

    async def resolve_key_id(self) -> int:
        if self.key_id:
            return self.key_id
        result = await self._request("GET", "/public/external-mails/keys")
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            items = result.get("items") or result.get("data") or result.get("keys") or []
        else:
            items = []
        active = [
            item
            for item in items
            if item.get("id")
            and str(item.get("status", "active")).lower() in {"active", "enabled"}
        ]
        candidates = active or [item for item in items if item.get("id")]
        if not candidates:
            raise RuSenderError(
                "No sending key is available; set RUSENDER_KEY_ID or grant external_mail.read"
            )
        self.key_id = int(candidates[0]["id"])
        return self.key_id

    async def send(
        self,
        *,
        to_email: str,
        to_name: str,
        from_email: str,
        from_name: str,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> str:
        key_id = await self.resolve_key_id()
        result = await self._request(
            "POST",
            f"/external-mails/send/{key_id}",
            json={
                "idempotencyKey": idempotency_key,
                "mail": {
                    "to": {"email": to_email, "name": to_name},
                    "from": {"email": from_email, "name": from_name},
                    "subject": subject,
                    "text": text,
                    "html": "<div style=\"font-family:Arial,sans-serif;white-space:pre-wrap\">"
                    f"{html.escape(text)}</div>",
                },
            },
        )
        provider_id = result.get("uuid") if isinstance(result, dict) else None
        if not provider_id:
            raise RuSenderError("RuSender response has no message uuid")
        return str(provider_id)

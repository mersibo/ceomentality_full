import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx


class CDEKError(RuntimeError):
    pass


@dataclass(frozen=True)
class CDEKQuote:
    price_kopecks: int
    tariff_code: int
    tariff_name: str
    delivery_mode: int
    period_min: int | None
    period_max: int | None


_token_cache: dict[tuple[str, str], tuple[str, datetime]] = {}
_token_lock = asyncio.Lock()


def _kopecks(value: Any) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


class CDEKClient:
    def __init__(self, api_url: str, account: str, secure_password: str, timeout: float = 15.0):
        self.api_url = api_url.rstrip("/")
        self.account = account
        self.secure_password = secure_password
        self.timeout = timeout

    async def _token(self) -> str:
        key = (self.api_url, self.account)
        cached = _token_cache.get(key)
        now = datetime.now(UTC)
        if cached and cached[1] > now + timedelta(seconds=30):
            return cached[0]
        async with _token_lock:
            cached = _token_cache.get(key)
            if cached and cached[1] > now + timedelta(seconds=30):
                return cached[0]
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_url}/oauth/token",
                    params={
                        "grant_type": "client_credentials",
                        "client_id": self.account,
                        "client_secret": self.secure_password,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            if response.status_code >= 400:
                raise CDEKError(f"CDEK authentication failed: HTTP {response.status_code}")
            data = response.json()
            token = data.get("access_token")
            if not token:
                raise CDEKError("CDEK authentication response has no access token")
            expires_in = max(int(data.get("expires_in", 3600)), 60)
            _token_cache[key] = (token, now + timedelta(seconds=expires_in))
            return token

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        token = await self._token()
        headers = {**kwargs.pop("headers", {}), "Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method, f"{self.api_url}{path}", headers=headers, **kwargs
            )
        if response.status_code >= 400:
            raise CDEKError(
                f"CDEK request failed: HTTP {response.status_code}: {response.text[:1000]}"
            )
        try:
            return response.json()
        except ValueError as error:
            raise CDEKError("CDEK returned invalid JSON") from error

    async def pickup_points(self, city: str) -> list[dict[str, Any]]:
        cities = await self._request(
            "GET",
            "/location/suggest/cities",
            params={"country_code": "RU", "name": city},
        )
        matches = [item for item in cities if item.get("code")] if isinstance(cities, list) else []
        if not matches:
            return []
        normalized = city.casefold().replace("ё", "е")
        selected = next(
            (
                item
                for item in matches
                if str(item.get("city") or "").casefold().replace("ё", "е") == normalized
            ),
            matches[0],
        )
        data = await self._request(
            "GET",
            "/deliverypoints",
            params={"city_code": selected["code"], "type": "PVZ", "is_handout": "true"},
        )
        points = []
        for item in data if isinstance(data, list) else []:
            location = item.get("location") or {}
            code = str(item.get("code") or "").strip()
            address = str(location.get("address_full") or location.get("address") or "").strip()
            if not code or not address or not location.get("city_code"):
                continue
            points.append(
                {
                    "code": code,
                    "name": str(item.get("name") or code)[:300],
                    "address": address[:500],
                    "city": str(location.get("city") or city)[:300],
                    "workTime": str(item.get("work_time") or "")[:300],
                }
            )
        return points

    async def pickup_point(self, code: str) -> dict[str, Any]:
        data = await self._request("GET", "/deliverypoints", params={"code": code})
        if not isinstance(data, list) or not data:
            raise CDEKError("CDEK pickup point was not found")
        item = data[0]
        location = item.get("location") or {}
        if not location.get("city_code"):
            raise CDEKError("CDEK pickup point has no city code")
        return {
            "code": str(item.get("code") or code),
            "name": str(item.get("name") or code)[:300],
            "address": str(location.get("address_full") or location.get("address") or "")[:500],
            "city": str(location.get("city") or "")[:300],
            "cityCode": int(location["city_code"]),
        }

    async def calculate(
        self,
        *,
        sender_city_code: int,
        recipient_city_code: int,
        weight: int,
        length: int,
        width: int,
        height: int,
    ) -> CDEKQuote:
        data = await self._request(
            "POST",
            "/calculator/tarifflist",
            json={
                "type": 1,
                "currency": 1,
                "lang": "rus",
                "from_location": {"code": sender_city_code},
                "to_location": {"code": recipient_city_code},
                "packages": [
                    {"weight": weight, "length": length, "width": width, "height": height}
                ],
            },
        )
        tariffs = [
            tariff
            for tariff in (data.get("tariff_codes") or [])
            if tariff.get("delivery_mode") == 4 and tariff.get("delivery_sum") is not None
        ]
        if not tariffs:
            raise CDEKError("CDEK has no pickup-point tariff for this destination")
        tariff = min(tariffs, key=lambda item: Decimal(str(item["delivery_sum"])))
        return CDEKQuote(
            price_kopecks=_kopecks(tariff["delivery_sum"]),
            tariff_code=int(tariff["tariff_code"]),
            tariff_name=str(tariff.get("tariff_name") or tariff["tariff_code"])[:300],
            delivery_mode=int(tariff["delivery_mode"]),
            period_min=int(tariff["period_min"]) if tariff.get("period_min") is not None else None,
            period_max=int(tariff["period_max"]) if tariff.get("period_max") is not None else None,
        )

    async def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/orders", json=payload)
        entity = data.get("entity") or {}
        errors = [
            error
            for request in (data.get("requests") or [])
            for error in (request.get("errors") or [])
        ]
        if errors or not entity.get("uuid"):
            message = "; ".join(str(error.get("message") or error) for error in errors)
            raise CDEKError(message or "CDEK did not create the shipment")
        return data

    async def order(self, uuid: str) -> dict[str, Any]:
        return await self._request("GET", f"/orders/{uuid}")

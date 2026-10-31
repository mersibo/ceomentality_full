import pytest

from app.services import cdek
from app.services.cdek import CDEKClient


@pytest.mark.asyncio
async def test_cdek_token_uses_documented_query_parameters(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"access_token": "token", "expires_in": 3600}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            captured.update(url=url, **kwargs)
            return Response()

    monkeypatch.setattr(cdek.httpx, "AsyncClient", lambda **_kwargs: Client())
    token = await CDEKClient(
        "https://api.cdek.test/v2",
        "test-query-account",
        "test-secret",
    )._token()

    assert token == "token"
    assert captured["params"] == {
        "grant_type": "client_credentials",
        "client_id": "test-query-account",
        "client_secret": "test-secret",
    }
    assert "data" not in captured


@pytest.mark.asyncio
async def test_pickup_points_do_not_expose_internal_city_code(monkeypatch) -> None:
    client = CDEKClient(
        "https://api.cdek.test/v2",
        "test-pickup-account",
        "test-secret",
    )

    async def request(_method, path, **_kwargs):
        if path == "/location/suggest/cities":
            return [{"code": 44, "city": "Москва"}]
        return [
            {
                "code": "MSK1",
                "name": "ПВЗ",
                "work_time": "10:00-20:00",
                "location": {
                    "city_code": 44,
                    "city": "Москва",
                    "address_full": "Москва, ул. Тестовая, 1",
                },
            }
        ]

    monkeypatch.setattr(client, "_request", request)
    points = await client.pickup_points("Москва")

    assert points == [
        {
            "code": "MSK1",
            "name": "ПВЗ",
            "address": "Москва, ул. Тестовая, 1",
            "city": "Москва",
            "workTime": "10:00-20:00",
        }
    ]

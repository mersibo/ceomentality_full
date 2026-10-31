import asyncio

import httpx

from crm import CRMClient, CRMError


def test_client_retries_server_errors() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"detail": "down"})

    async def scenario() -> None:
        client = CRMClient("https://crm.example.com", "x" * 24)
        await client.client.aclose()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://crm.example.com")
        try:
            await client.request("GET", "/health")
        except CRMError as error:
            assert error.status_code == 503
        else:
            raise AssertionError("CRMError was not raised")
        finally:
            await client.close()

    asyncio.run(scenario())
    assert attempts == 3

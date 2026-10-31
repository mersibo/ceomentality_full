import pytest

from app.services.tbank import (
    TBankClient,
    TBankError,
    make_token,
    payment_status,
    receipt_items,
    verify_token,
)


def test_token_uses_scalars_and_lowercase_boolean() -> None:
    payload = {
        "TerminalKey": "TBankTest",
        "Amount": 349000,
        "OrderId": "order_1",
        "Success": True,
        "Receipt": {"must": "be ignored"},
    }
    token = make_token(payload, "secret-password")
    assert len(token) == 64
    assert verify_token({**payload, "Token": token}, "secret-password")
    assert not verify_token({**payload, "Amount": 1, "Token": token}, "secret-password")


def test_receipt_total_matches_order_total() -> None:
    items = receipt_items(
        [{"variantId": "ceowallet-white", "quantity": 1, "unitPrice": 299000}],
        50000,
        tax="vat0",
    )
    assert sum(item["Amount"] for item in items) == 349000
    assert items[0]["Tax"] == "vat0"
    assert items[0]["PaymentMethod"] == "full_prepayment"
    assert items[1]["PaymentObject"] == "service"

    closing_items = receipt_items(
        [{"variantId": "ceowallet-black", "quantity": 1, "unitPrice": 299000}],
        50000,
        tax="vat0",
        payment_method="full_payment",
    )
    assert all(item["PaymentMethod"] == "full_payment" for item in closing_items)


def test_tbank_status_mapping_only_confirms_completed_payment() -> None:
    assert payment_status("CONFIRMED", True) == "paid"
    assert payment_status("AUTHORIZED", True) == "processing"
    assert payment_status("REJECTED", False) == "payment_failed"
    assert payment_status("REFUNDED", True) == "cancelled"
    assert payment_status("CONFIRMED", False) is None


@pytest.mark.asyncio
async def test_tbank_error_includes_provider_details(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "Success": False,
                "ErrorCode": "204",
                "Message": "Invalid parameters",
                "Details": "Invalid token",
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def post(self, *_args, **_kwargs) -> Response:
            return Response()

    monkeypatch.setattr("app.services.tbank.httpx.AsyncClient", lambda **_kwargs: Client())

    with pytest.raises(TBankError, match="Details: Invalid token"):
        await TBankClient(
            api_url="https://securepay.tinkoff.ru/v2",
            terminal_key="terminal",
            password="password",
        ).request("Init", {"Amount": 100, "OrderId": "order"})

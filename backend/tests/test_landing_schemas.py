import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.landing_schemas import PurchaseRequest, QuoteRequest


def test_purchase_request_matches_frontend_contract() -> None:
    request = PurchaseRequest(
        name="Test User",
        email="test@example.com",
        phone="+79001234567",
        telegram="@ceo_test",
        deliveryChannel="telegram",
        variantId="ceowallet-white",
        comment="",
        consents={"privacy": True},
    )
    assert request.variantId == "ceowallet-white"
    assert request.telegram == "@ceo_test"


def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PurchaseRequest(
            name="Test User",
            email="test@example.com",
            phone="+79001234567",
            telegram="https://t.me/ceo_test",
            deliveryChannel="telegram",
            variantId="ceowallet-white",
            comment="",
            consents={"privacy": True},
            trustedPrice=1,
        )


@pytest.mark.parametrize("telegram", ["@ceo_test", "ceo_test", "https://t.me/ceo_test"])
def test_purchase_request_accepts_common_telegram_formats(telegram: str) -> None:
    request = PurchaseRequest(
        name="Test User",
        email="test@example.com",
        phone="+79001234567",
        telegram=telegram,
        deliveryChannel="telegram",
        variantId="ceowallet-white",
        comment="",
        consents={"privacy": True},
    )
    assert request.telegram == telegram


def test_purchase_request_allows_email_delivery_without_telegram() -> None:
    request = PurchaseRequest(
        name="Test User",
        email="test@example.com",
        phone="+79001234567",
        telegram="",
        deliveryChannel="email",
        variantId="ceowallet-white",
        comment="",
        consents={"privacy": True},
    )
    assert request.deliveryChannel == "email"


def test_purchase_request_requires_telegram_for_telegram_delivery() -> None:
    with pytest.raises(ValidationError):
        PurchaseRequest(
            name="Test User",
            email="test@example.com",
            phone="+79001234567",
            telegram="",
            deliveryChannel="telegram",
            variantId="ceowallet-white",
            comment="",
            consents={"privacy": True},
        )


def test_purchase_request_allows_telegram_delivery_without_email() -> None:
    request = PurchaseRequest(
        name="Test User",
        email=None,
        phone="+79001234567",
        telegram="@ceo_test",
        deliveryChannel="telegram",
        variantId="ceowallet-white",
        comment="",
        consents={"privacy": True},
    )
    assert request.email is None


def test_purchase_request_requires_email_for_email_delivery() -> None:
    with pytest.raises(ValidationError):
        PurchaseRequest(
            name="Test User",
            email=None,
            phone="+79001234567",
            telegram="",
            deliveryChannel="email",
            variantId="ceowallet-white",
            comment="",
            consents={"privacy": True},
        )


def test_quote_rejects_more_than_two_items() -> None:
    with pytest.raises(ValidationError):
        QuoteRequest(
            items=[
                {"variantId": "ceowallet-white", "quantity": 1},
                {"variantId": "ceowallet-black", "quantity": 1},
                {"variantId": "ceowallet-white", "quantity": 1},
            ],
            customer={
                "name": "Test User",
                "email": "test@example.com",
                "phone": "+79001234567",
                "city": "Moscow",
                "address": "Street 1",
                "comment": "",
            },
            consents={"privacy": True, "agreement": True, "purchaseTerms": True},
        )


def test_settings_reject_reserved_superuser_email() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+asyncpg://user:password@postgres/database",
            secret_key="a-secure-development-secret",
            first_superuser_email="manager@ceomentality.local",
            first_superuser_password="a-secure-password",
        )

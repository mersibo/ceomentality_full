from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

VariantId = Literal["ceowallet-white", "ceowallet-black"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Item(StrictModel):
    variantId: VariantId
    quantity: int = Field(ge=1, le=10)


class PricedItem(Item):
    unitPrice: int = Field(ge=0)


class Customer(StrictModel):
    name: str = Field(min_length=1, max_length=300)
    email: EmailStr
    phone: str = Field(pattern=r"^\+[0-9]{8,15}$")
    # Fixed delivery does not need a destination at quote time; CDEK validates
    # its pickup point separately in the delivery-provider branch.
    city: str = Field(default="", max_length=300)
    address: str = Field(default="", max_length=500)
    pickupPointCode: str | None = Field(default=None, min_length=1, max_length=30)
    pickupPointName: str | None = Field(default=None, min_length=1, max_length=300)
    comment: str = Field(max_length=2000)


class PrivacyConsent(StrictModel):
    privacy: Literal[True]


class CheckoutConsents(PrivacyConsent):
    agreement: Literal[True]
    purchaseTerms: Literal[True]


class PublicSessionOut(StrictModel):
    csrfToken: str
    accessGranted: bool
    membershipAllowed: bool


class CatalogVariant(StrictModel):
    variantId: VariantId
    unitPrice: int = Field(ge=0)
    available: bool
    maxQuantity: int = Field(ge=0, le=10)


class CatalogOut(StrictModel):
    currency: Literal["RUB"] = "RUB"
    variants: list[CatalogVariant]


class AccessRequest(StrictModel):
    code: str = Field(min_length=1, max_length=64)
    variantId: VariantId


class AcceptedOut(StrictModel):
    accepted: Literal[True] = True


class ClaimRequest(StrictModel):
    token: str = Field(min_length=1, max_length=4096)


class ReceiptOut(StrictModel):
    id: str
    status: Literal["received"] = "received"


class ContactRequest(StrictModel):
    name: str = Field(min_length=1, max_length=300)
    email: EmailStr
    consents: PrivacyConsent
    message: str = Field(min_length=1, max_length=5000)


class PurchaseRequest(StrictModel):
    name: str = Field(min_length=1, max_length=300)
    email: EmailStr | None = None
    consents: PrivacyConsent
    phone: str = Field(pattern=r"^\+[0-9]{8,15}$")
    telegram: str = Field(default="", max_length=300)
    deliveryChannel: Literal["telegram", "email"]
    variantId: VariantId
    comment: str = Field(max_length=2000)

    @model_validator(mode="after")
    def require_selected_delivery_contact(self) -> "PurchaseRequest":
        if self.deliveryChannel == "telegram" and not self.telegram.strip():
            raise ValueError("telegram is required for Telegram delivery")
        if self.deliveryChannel == "email" and self.email is None:
            raise ValueError("email is required for email delivery")
        return self


class MembershipRequest(StrictModel):
    name: str = Field(min_length=1, max_length=300)
    email: EmailStr
    consents: PrivacyConsent
    phone: str = Field(pattern=r"^\+[0-9]{8,15}$")
    telegram: str = Field(min_length=1, max_length=300)
    project: str = Field(min_length=1, max_length=5000)
    invitation: str = Field(max_length=300)


class QuoteRequest(StrictModel):
    items: list[Item] = Field(min_length=1, max_length=2)
    customer: Customer
    consents: CheckoutConsents


class PickupPoint(StrictModel):
    code: str
    name: str
    address: str
    city: str
    workTime: str


class PickupPointsOut(StrictModel):
    items: list[PickupPoint]


class QuoteOut(StrictModel):
    currency: Literal["RUB"] = "RUB"
    items: list[PricedItem]
    subtotal: int
    delivery: int
    total: int
    id: str
    expiresAt: datetime


class CreateOrder(StrictModel):
    quoteId: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    customer: Customer
    consents: CheckoutConsents


class OrderOut(StrictModel):
    currency: Literal["RUB"] = "RUB"
    items: list[PricedItem]
    subtotal: int
    delivery: int
    total: int
    id: str
    status: Literal[
        "awaiting_payment", "processing", "paid", "shipped", "delivered",
        "payment_failed", "cancelled",
    ]
    tracking: dict[str, str] | None = None


class OrderClaimOut(StrictModel):
    orderId: str


class PaymentOut(StrictModel):
    paymentUrl: str
    sbpQr: str | None = None


class MembershipStatusOut(StrictModel):
    status: Literal["not_submitted", "pending", "approved", "rejected"]


class PaymentWebhook(StrictModel):
    providerPaymentId: str = Field(min_length=1, max_length=200)
    orderId: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    status: Literal["processing", "paid", "payment_failed", "cancelled"]
    amount: int = Field(ge=0)
    currency: Literal["RUB"]

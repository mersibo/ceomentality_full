import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app.api.deps import SessionDep, SettingsDep
from app.landing_schemas import (
    AcceptedOut,
    AccessRequest,
    CatalogOut,
    CatalogVariant,
    ClaimRequest,
    ContactRequest,
    CreateOrder,
    MembershipRequest,
    MembershipStatusOut,
    OrderClaimOut,
    OrderOut,
    PaymentOut,
    PaymentWebhook,
    PickupPointsOut,
    PurchaseRequest,
    QuoteOut,
    QuoteRequest,
    ReceiptOut,
)
from app.models import (
    AccessCode,
    Candidate,
    CheckoutQuote,
    ContactMessage,
    Drop,
    MembershipInvitation,
    ProductVariant,
    PublicSession,
    StoreOrder,
    StorePayment,
)
from app.schemas import CandidateCreate, ClubApplicationCreate
from app.services.audit import record_activity
from app.services.blacklist import find_blacklist_match
from app.services.candidates import create_candidate_from_admin, create_club_application
from app.services.cdek import CDEKClient, CDEKError
from app.services.landing import (
    IdempotencyKey,
    LandingApiError,
    PublicSessionDep,
    digest,
    find_public_session,
    payload_digest,
    public_id,
    remember_idempotent,
    replay_idempotent,
)
from app.services.tbank import (
    TBankClient,
    TBankError,
    payment_status,
    receipt_items,
    verify_token,
)
from app.services.telegram_outbox import enqueue_telegram_message

router = APIRouter(prefix="/api/v1", tags=["landing"])
logger = logging.getLogger(__name__)


def cdek_client(settings: SettingsDep) -> CDEKClient:
    if not settings.cdek_account or not settings.cdek_secure_password:
        raise LandingApiError(503, "DELIVERY_UNAVAILABLE")
    return CDEKClient(
        str(settings.cdek_api_url), settings.cdek_account, settings.cdek_secure_password
    )


def as_order(order: StoreOrder) -> dict:
    return OrderOut(
        currency="RUB", items=order.items, subtotal=order.subtotal, delivery=order.delivery,
        total=order.total, id=order.id, status=order.status, tracking=order.tracking,
    ).model_dump(mode="json")


async def match_purchase_candidate(session: SessionDep, customer: dict) -> Candidate | None:
    email = customer.get("email", "").strip().lower()
    phone = customer.get("phone", "").strip()
    candidates = (
        await session.scalars(
            select(Candidate).where(Candidate.stage == "purchase").order_by(Candidate.updated_at.desc()).limit(500)
        )
    ).all()
    matches = [
        candidate for candidate in candidates
        if (
            (candidate.questionnaire_answers or {}).get("email", "").strip().lower() == email
            and (candidate.questionnaire_answers or {}).get("phone", "").strip() == phone
        )
    ]
    return matches[0] if len(matches) == 1 else None


async def ensure_landing_allowed(session: SessionDep, **identifiers) -> None:
    entry = await find_blacklist_match(session, **identifiers)
    if entry:
        raise LandingApiError(403, "BLACKLISTED", reason=entry.reason)


@router.get("/session")
async def public_session(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep
):
    item = await find_public_session(request, session, settings)
    token = None
    if item is None:
        token = secrets.token_urlsafe(32)
        item = PublicSession(
            token_hash=digest(token),
            csrf_hash="",
            expires_at=datetime.now(UTC) + timedelta(days=settings.public_session_days),
        )
        session.add(item)
    csrf = secrets.token_urlsafe(32)
    item.csrf_hash = digest(csrf)
    item.expires_at = datetime.now(UTC) + timedelta(days=settings.public_session_days)
    await session.commit()
    if token:
        response.set_cookie(
            settings.public_session_cookie_name,
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.public_session_days * 86400,
            path="/",
        )
    membership_allowed = False
    if item.membership_invitation_id:
        invitation = await session.get(MembershipInvitation, item.membership_invitation_id)
        membership_allowed = bool(
            invitation and not invitation.revoked and not invitation.used_at
            and invitation.expires_at > datetime.now(UTC)
            and invitation.claimed_session_id == item.id
        )
    return {
        "csrfToken": csrf,
        "accessGranted": item.access_granted,
        "membershipAllowed": membership_allowed,
    }


@router.get("/catalog", response_model=CatalogOut)
async def catalog(session: SessionDep):
    variants = (await session.scalars(select(ProductVariant).order_by(ProductVariant.id))).all()
    return CatalogOut(
        variants=[
            CatalogVariant(
                variantId=item.id,
                unitPrice=item.unit_price,
                available=item.available and (item.stock_quantity is None or item.stock_quantity > 0),
                maxQuantity=min(item.max_quantity, item.stock_quantity or item.max_quantity),
            )
            for item in variants
        ]
    )


@router.get("/delivery/pickup-points", response_model=PickupPointsOut)
async def pickup_points(
    city: str, settings: SettingsDep, _public: PublicSessionDep
):
    city = city.strip()
    if len(city) < 2 or len(city) > 300:
        raise LandingApiError(422, "VALIDATION_ERROR", {"city": "INVALID"})
    if settings.delivery_provider != "cdek":
        raise LandingApiError(503, "DELIVERY_UNAVAILABLE")
    try:
        points = await cdek_client(settings).pickup_points(city)
    except CDEKError as error:
        raise LandingApiError(502, "DELIVERY_UNAVAILABLE") from error
    return {"items": points[:200]}


@router.post("/access/check", response_model=AcceptedOut)
async def check_access(
    payload: AccessRequest, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "access.check", key, data):
        return replay
    variant = await session.get(ProductVariant, payload.variantId)
    if variant is None or not variant.available:
        raise LandingApiError(409, "OUT_OF_STOCK")
    now = datetime.now(UTC)
    normalized_code = payload.code.strip().upper()
    matching_codes = (
        await session.scalars(
            select(AccessCode)
            .where(AccessCode.value == normalized_code)
            .with_for_update()
        )
    ).all()
    if len(matching_codes) != 1:
        raise LandingApiError(403, "INVALID_CODE", {"code": "INVALID"})
    access_code = matching_codes[0]
    drop = await session.get(Drop, access_code.drop_id) if access_code.drop_id else None
    if (
        drop is None
        or drop.status != "Active"
        or (access_code.status == "Redeemed" and public.access_code_id != access_code.id)
        or access_code.status not in {"Active", "Redeemed"}
        or (access_code.valid_from and access_code.valid_from > now)
        or (access_code.valid_until and access_code.valid_until < now)
        or (drop.valid_from and drop.valid_from > now)
        or (drop.valid_until and drop.valid_until < now)
    ):
        raise LandingApiError(403, "INVALID_CODE", {"code": "INVALID"})
    if access_code.status == "Active":
        access_code.status = "Redeemed"
        access_code.redeemed_at = now
        drop.redeemed += 1
        if access_code.candidate_id:
            candidate = await session.get(Candidate, access_code.candidate_id)
            if candidate and candidate.status == "Code assigned":
                candidate.status = "Code used"
        await record_activity(
            session,
            type_="code.redeemed",
            detail=f"{access_code.value} redeemed on landing",
            entity_type="access_code",
            entity_id=str(access_code.id),
        )
    public.access_granted = True
    public.access_drop_id = drop.id
    public.access_code_id = access_code.id
    body = {"accepted": True}
    remember_idempotent(session, public, "access.check", key, data, body, 200)
    await session.commit()
    return body


@router.post("/purchase-applications", response_model=ReceiptOut, status_code=status.HTTP_201_CREATED)
async def purchase_application(
    payload: PurchaseRequest, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "purchase.application", key, data):
        return replay
    await ensure_landing_allowed(
        session,
        telegram=payload.telegram,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
    )
    candidate = await create_candidate_from_admin(
        session,
        CandidateCreate(
            name=payload.name,
            telegram=payload.telegram,
            deliveryChannel=payload.deliveryChannel,
            stage="purchase",
            source="Website",
            summary=payload.comment,
            questionnaireAnswers={
                "email": str(payload.email) if payload.email else "", "phone": payload.phone,
                "telegram": payload.telegram, "deliveryChannel": payload.deliveryChannel,
                "variantId": payload.variantId, "privacy": True,
            },
        ),
    )
    candidate.product = payload.variantId
    body = {"id": candidate.id, "status": "received"}
    remember_idempotent(session, public, "purchase.application", key, data, body, 201)
    await session.commit()
    return body


@router.post("/contact-messages", response_model=ReceiptOut, status_code=status.HTTP_201_CREATED)
async def contact_message(
    payload: ContactRequest, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "contact.message", key, data):
        return replay
    message = ContactMessage(
        name=payload.name, email=str(payload.email), message=payload.message,
        consent=payload.consents.model_dump(),
    )
    session.add(message)
    await session.flush()
    await record_activity(
        session, type_="notification.manager", detail=f"New website message from {payload.name}",
        entity_type="contact_message", entity_id=str(message.id), data={"source": "landing"},
    )
    body = {"id": str(message.id), "status": "received"}
    remember_idempotent(session, public, "contact.message", key, data, body, 201)
    await session.commit()
    return body


@router.post("/membership/invitations/claim", response_model=AcceptedOut)
async def claim_invitation(
    payload: ClaimRequest, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "membership.claim", key, data):
        return replay
    invitation = await session.scalar(
        select(MembershipInvitation).where(MembershipInvitation.token_hash == digest(payload.token)).with_for_update()
    )
    now = datetime.now(UTC)
    if (
        invitation is None or invitation.revoked or invitation.used_at
        or invitation.expires_at <= now
        or (invitation.claimed_session_id and invitation.claimed_session_id != public.id)
    ):
        raise LandingApiError(403, "INVALID_INVITATION")
    invitation.claimed_at = now
    invitation.claimed_session_id = public.id
    public.membership_invitation_id = invitation.id
    body = {"accepted": True}
    remember_idempotent(session, public, "membership.claim", key, data, body, 200)
    await session.commit()
    return body


@router.post("/membership-applications", response_model=ReceiptOut, status_code=status.HTTP_201_CREATED)
async def membership_application(
    payload: MembershipRequest, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "membership.application", key, data):
        return replay
    await ensure_landing_allowed(
        session, telegram=payload.telegram, email=str(payload.email), phone=payload.phone
    )
    if public.membership_invitation_id is None:
        raise LandingApiError(403, "FORBIDDEN")
    invitation = await session.scalar(
        select(MembershipInvitation).where(
            MembershipInvitation.id == public.membership_invitation_id
        ).with_for_update()
    )
    now = datetime.now(UTC)
    if (
        invitation is None or invitation.revoked or invitation.used_at
        or invitation.expires_at <= now or invitation.claimed_session_id != public.id
    ):
        raise LandingApiError(403, "INVALID_INVITATION")
    candidate = await create_club_application(
        session,
        ClubApplicationCreate(
            name=payload.name, telegram=payload.telegram, activity="",
            projects=[{"name": payload.project}], additionalInfo=payload.project,
            questionnaireAnswers={
                "email": str(payload.email), "phone": payload.phone,
                "referral": payload.invitation, "privacy": True,
            }, source="Website",
        ),
        source_label="landing_qr",
    )
    invitation.used_at = now
    public.membership_candidate_id = candidate.id
    body = {"id": candidate.id, "status": "received"}
    remember_idempotent(session, public, "membership.application", key, data, body, 201)
    await session.commit()
    return body


@router.get("/membership/status", response_model=MembershipStatusOut)
async def membership_status(session: SessionDep, public: PublicSessionDep):
    if public.membership_candidate_id is None:
        return {"status": "not_submitted"}
    candidate = await session.get(Candidate, public.membership_candidate_id)
    if candidate is None:
        return {"status": "not_submitted"}
    mapped = {
        "Approved": "approved", "Accepted": "approved", "Rejected": "rejected",
        "Under review": "pending", "Waitlisted": "pending",
    }
    return {"status": mapped.get(candidate.status, "pending")}


@router.post("/checkout/quotes", response_model=QuoteOut)
async def create_quote(
    payload: QuoteRequest, session: SessionDep, settings: SettingsDep,
    public: PublicSessionDep, key: IdempotencyKey,
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "checkout.quote", key, data):
        return replay
    if not public.access_granted:
        raise LandingApiError(403, "FORBIDDEN")
    if len({item.variantId for item in payload.items}) != len(payload.items):
        raise LandingApiError(422, "VALIDATION_ERROR")
    priced = []
    subtotal = 0
    for item in payload.items:
        variant = await session.get(ProductVariant, item.variantId)
        available = variant and variant.available and item.quantity <= variant.max_quantity
        if available and variant.stock_quantity is not None:
            available = item.quantity <= variant.stock_quantity
        if not available:
            raise LandingApiError(409, "OUT_OF_STOCK")
        line = {"variantId": variant.id, "quantity": item.quantity, "unitPrice": variant.unit_price}
        priced.append(line)
        subtotal += item.quantity * variant.unit_price
    customer = payload.customer.model_dump(mode="json")
    delivery = settings.delivery_price_kopecks
    if settings.delivery_provider == "cdek":
        if not payload.customer.pickupPointCode or not payload.customer.pickupPointName:
            raise LandingApiError(422, "VALIDATION_ERROR", {"pickupPointCode": "REQUIRED"})
        try:
            client = cdek_client(settings)
            point = await client.pickup_point(payload.customer.pickupPointCode)
            if (
                point["address"] != payload.customer.address
                or point["name"] != payload.customer.pickupPointName
            ):
                raise LandingApiError(422, "VALIDATION_ERROR", {"pickupPointCode": "INVALID"})
            quote_result = await client.calculate(
                sender_city_code=settings.cdek_sender_city_code,
                recipient_city_code=point["cityCode"],
                weight=settings.cdek_package_weight_grams
                * sum(item.quantity for item in payload.items),
                length=settings.cdek_package_length_cm,
                width=settings.cdek_package_width_cm,
                height=settings.cdek_package_height_cm,
            )
            delivery = quote_result.price_kopecks
            customer["delivery"] = {
                "provider": "cdek",
                "pickupPointCode": point["code"],
                "pickupPointName": point["name"],
                "pickupPointAddress": point["address"],
                "tariffCode": quote_result.tariff_code,
                "tariffName": quote_result.tariff_name,
                "periodMin": quote_result.period_min,
                "periodMax": quote_result.period_max,
                "returnPayer": settings.cdek_return_payer,
            }
        except LandingApiError:
            raise
        except CDEKError as error:
            raise LandingApiError(502, "DELIVERY_UNAVAILABLE") from error
    expires = datetime.now(UTC) + timedelta(minutes=settings.quote_ttl_minutes)
    quote = CheckoutQuote(
        id=public_id("quote"), session_id=public.id, items=priced,
        customer=customer, consents=payload.consents.model_dump(),
        subtotal=subtotal, delivery=delivery,
        total=subtotal + delivery, payload_hash=payload_digest(data),
        expires_at=expires,
    )
    session.add(quote)
    body = {
        "currency": "RUB", "items": priced, "subtotal": quote.subtotal,
        "delivery": quote.delivery, "total": quote.total, "id": quote.id,
        "expiresAt": expires.isoformat(),
    }
    remember_idempotent(session, public, "checkout.quote", key, data, body, 200)
    await session.commit()
    return body


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrder, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "order.create", key, data):
        return replay
    if not public.access_granted:
        raise LandingApiError(403, "FORBIDDEN")
    quote = await session.scalar(
        select(CheckoutQuote).where(CheckoutQuote.id == payload.quoteId).with_for_update()
    )
    if quote is None or quote.session_id != public.id:
        raise LandingApiError(404, "NOT_FOUND")
    existing = await session.scalar(select(StoreOrder).where(StoreOrder.quote_id == quote.id))
    if existing:
        body = as_order(existing)
        remember_idempotent(session, public, "order.create", key, data, body, 200)
        await session.commit()
        return body
    if quote.expires_at <= datetime.now(UTC):
        raise LandingApiError(409, "QUOTE_EXPIRED")
    customer = payload.customer.model_dump(mode="json")
    quote_customer = dict(quote.customer)
    quote_customer.pop("delivery", None)
    if customer != quote_customer or payload.consents.model_dump() != quote.consents:
        raise LandingApiError(422, "VALIDATION_ERROR")
    claim_token = secrets.token_urlsafe(32)
    order = StoreOrder(
        id=public_id("order"), session_id=public.id, quote_id=quote.id,
        items=quote.items, customer=quote.customer, consents=quote.consents,
        subtotal=quote.subtotal, delivery=quote.delivery, total=quote.total,
        claim_token_hash=digest(claim_token),
    )
    candidate = await match_purchase_candidate(session, customer)
    if candidate:
        order.candidate_id = candidate.id
    session.add(order)
    quote.used_at = datetime.now(UTC)
    public.order_ids = [*public.order_ids, order.id]
    # Materialize SQLAlchemy defaults before serializing the new order.
    await session.flush()
    body = as_order(order)
    remember_idempotent(session, public, "order.create", key, data, body, 201)
    await record_activity(
        session, type_="order.created", detail=f"Website order {order.id} created",
        entity_type="order", entity_id=order.id, data={"total": order.total, "currency": "RUB"},
    )
    await session.commit()
    return body


@router.post("/payments/webhook", include_in_schema=False)
async def payment_webhook(
    payload: PaymentWebhook,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    signature: str = Header(default="", alias="X-Payment-Signature"),
):
    if settings.payment_provider == "disabled" or not settings.payment_webhook_secret:
        raise LandingApiError(503, "PAYMENT_UNAVAILABLE")
    expected = hmac.new(
        settings.payment_webhook_secret.encode("utf-8"),
        await request.body(),
        hashlib.sha256,
    ).hexdigest()
    if not signature or not secrets.compare_digest(signature, expected):
        raise LandingApiError(403, "FORBIDDEN")
    payment = await session.scalar(
        select(StorePayment).where(
            StorePayment.provider_payment_id == payload.providerPaymentId,
            StorePayment.order_id == payload.orderId,
        ).with_for_update()
    )
    order = await session.get(StoreOrder, payload.orderId)
    if (
        payment is None or order is None or payload.amount != order.total
        or payload.currency != order.currency
    ):
        raise LandingApiError(422, "VALIDATION_ERROR")
    await apply_payment_status(session, payment, order, payload.status, settings)
    await session.commit()
    return {"accepted": True}


async def apply_payment_status(
    session: SessionDep,
    payment: StorePayment,
    order: StoreOrder,
    new_status: str,
    settings,
) -> None:
    was_paid = payment.status == "paid"
    payment.status = new_status
    order.status = new_status
    if new_status == "paid" and not was_paid:
        candidate = await session.get(Candidate, order.candidate_id) if order.candidate_id else None
        if candidate:
            candidate.purchase_confirmed = True
            candidate.purchased_at = datetime.now(UTC)
            candidate.product = ", ".join(item["variantId"] for item in order.items)
            if candidate.status == "Code assigned":
                candidate.status = "Code used"
        invitation_token = secrets.token_urlsafe(32)
        invitation = MembershipInvitation(
            token_hash=digest(invitation_token), candidate_id=order.candidate_id,
            order_id=order.id, expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(invitation)
        await session.flush()
        if candidate and candidate.telegram_id and settings.public_site_url:
            invitation_url = (
                f"{str(settings.public_site_url).rstrip('/')}/app.html?screen=application"
                f"#invitation={quote(invitation_token)}"
            )
            await enqueue_telegram_message(
                session, chat_id=candidate.telegram_id,
                text=f"Покупка подтверждена. Анкета для вступления в клуб: {invitation_url}",
                entity_type="membership_invitation", entity_id=str(invitation.id),
            )
        await record_activity(
            session, type_="purchase.confirmed", detail=f"Website order {order.id} paid",
            entity_type="order", entity_id=order.id,
            data={"candidateId": order.candidate_id, "total": order.total},
        )


@router.post("/payments/tbank/webhook", include_in_schema=False)
async def tbank_payment_webhook(
    request: Request, session: SessionDep, settings: SettingsDep
):
    if (
        settings.payment_provider != "tbank"
        or not settings.tbank_terminal_key
        or not settings.tbank_password
    ):
        raise LandingApiError(503, "PAYMENT_UNAVAILABLE")
    try:
        payload = await request.json()
    except ValueError as error:
        raise LandingApiError(422, "VALIDATION_ERROR") from error
    if not isinstance(payload, dict):
        raise LandingApiError(422, "VALIDATION_ERROR")
    if payload.get("TerminalKey") != settings.tbank_terminal_key or not verify_token(
        payload, settings.tbank_password
    ):
        raise LandingApiError(403, "FORBIDDEN")
    order_id = str(payload.get("OrderId", ""))
    provider_payment_id = str(payload.get("PaymentId", ""))
    payment = await session.scalar(
        select(StorePayment).where(
            StorePayment.provider == "tbank",
            StorePayment.provider_payment_id == provider_payment_id,
            StorePayment.order_id == order_id,
        ).with_for_update()
    )
    order = await session.get(StoreOrder, order_id)
    try:
        amount = int(payload.get("Amount", -1))
    except (TypeError, ValueError) as error:
        raise LandingApiError(422, "VALIDATION_ERROR") from error
    if payment is None or order is None or amount != order.total:
        raise LandingApiError(422, "VALIDATION_ERROR")
    success_value = payload.get("Success")
    success = success_value is True or str(success_value).lower() == "true"
    mapped_status = payment_status(str(payload.get("Status", "")), success)
    if mapped_status:
        await apply_payment_status(session, payment, order, mapped_status, settings)
        await session.commit()
    return PlainTextResponse("OK")


@router.post("/orders/claim", response_model=OrderClaimOut)
async def claim_order(
    payload: ClaimRequest, session: SessionDep, public: PublicSessionDep, key: IdempotencyKey
):
    data = payload.model_dump(mode="json")
    if replay := await replay_idempotent(session, public, "order.claim", key, data):
        return replay
    order = await session.scalar(select(StoreOrder).where(StoreOrder.claim_token_hash == digest(payload.token)))
    if order is None:
        raise LandingApiError(404, "NOT_FOUND")
    if order.id not in public.order_ids:
        public.order_ids = [*public.order_ids, order.id]
    body = {"orderId": order.id}
    remember_idempotent(session, public, "order.claim", key, data, body, 200)
    await session.commit()
    return body


async def authorized_order(order_id: str, session: SessionDep, public: PublicSessionDep) -> StoreOrder:
    order = await session.get(StoreOrder, order_id)
    if order is None or order.id not in public.order_ids:
        raise LandingApiError(404, "NOT_FOUND")
    return order


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, session: SessionDep, public: PublicSessionDep):
    return as_order(await authorized_order(order_id, session, public))


@router.post("/orders/{order_id}/payment", response_model=PaymentOut)
async def create_payment(
    order_id: str, session: SessionDep, settings: SettingsDep,
    public: PublicSessionDep, key: IdempotencyKey,
):
    data = {"orderId": order_id}
    if replay := await replay_idempotent(session, public, "payment.create", key, data):
        return replay
    order = await authorized_order(order_id, session, public)
    if order.status not in {"awaiting_payment", "payment_failed", "processing"}:
        raise LandingApiError(409, "PAYMENT_UNAVAILABLE")
    if settings.payment_provider == "disabled":
        raise LandingApiError(503, "PAYMENT_UNAVAILABLE")
    existing = await session.scalar(
        select(StorePayment).where(StorePayment.order_id == order.id, StorePayment.status.in_(["pending", "processing"]))
        .order_by(StorePayment.created_at.desc()).limit(1)
    )
    if existing:
        body = {"paymentUrl": existing.payment_url}
        if existing.provider == "tbank" and order.total >= 1000:
            try:
                body["sbpQr"] = await TBankClient(
                    api_url=str(settings.tbank_api_url),
                    terminal_key=settings.tbank_terminal_key,
                    password=settings.tbank_password,
                ).get_sbp_qr(existing.provider_payment_id)
            except TBankError:
                logger.warning("SBP QR unavailable for existing order %s", order.id)
    elif order.status == "processing":
        raise LandingApiError(409, "PAYMENT_UNAVAILABLE")
    elif settings.payment_provider == "tbank":
        if (
            not settings.tbank_terminal_key
            or not settings.tbank_password
            or settings.public_site_url is None
        ):
            raise LandingApiError(503, "PAYMENT_UNAVAILABLE")
        site_url = str(settings.public_site_url).rstrip("/")
        return_query = urlencode({"screen": "processing", "orderId": order.id})
        fail_query = urlencode({"screen": "payment-failed", "orderId": order.id})
        customer = order.customer or {}
        request_body = {
            "Amount": order.total,
            "OrderId": order.id,
            "Description": "Картхолдер CEOMENTALITY",
            # SBP is supported by the universal form and works only as a one-stage payment.
            "PayType": "O",
            "NotificationURL": f"{site_url}/api/v1/payments/tbank/webhook",
            "SuccessURL": f"{site_url}/app.html?{return_query}",
            "FailURL": f"{site_url}/app.html?{fail_query}",
            "DATA": {
                "Email": customer.get("email"),
                "Phone": customer.get("phone"),
                "OperationInitiatorType": "0",
            },
            "Receipt": {
                "Email": customer.get("email"),
                "Phone": customer.get("phone"),
                "Taxation": settings.tbank_taxation,
                "Items": receipt_items(order.items, order.delivery, tax=settings.tbank_tax),
            },
        }
        try:
            result = await TBankClient(
                api_url=str(settings.tbank_api_url),
                terminal_key=settings.tbank_terminal_key,
                password=settings.tbank_password,
            ).request("Init", request_body)
        except TBankError as error:
            logger.warning("T-Bank Init rejected order %s: %s", order.id, error)
            raise LandingApiError(502, "PAYMENT_UNAVAILABLE") from error
        payment_id = str(result.get("PaymentId", ""))
        payment_url = str(result.get("PaymentURL", ""))
        payment_origin = urlparse(payment_url)
        allowed_payment_hosts = {
            "securepay.tinkoff.ru",
            "securepayments.tinkoff.ru",
            "pay.tbank-online.com",
        }
        if (
            not payment_id
            or payment_origin.scheme != "https"
            or payment_origin.hostname not in allowed_payment_hosts
            or not payment_origin.path
        ):
            logger.warning(
                "T-Bank Init returned an invalid payment target for order %s (host=%s)",
                order.id,
                payment_origin.hostname,
            )
            raise LandingApiError(502, "PAYMENT_UNAVAILABLE")
        session.add(StorePayment(
            order_id=order.id, provider="tbank", provider_payment_id=payment_id,
            payment_url=payment_url, amount=order.total, currency=order.currency,
        ))
        order.status = "processing"
        sbp_qr = None
        try:
            sbp_qr = await TBankClient(
                api_url=str(settings.tbank_api_url),
                terminal_key=settings.tbank_terminal_key,
                password=settings.tbank_password,
            ).get_sbp_qr(payment_id)
        except TBankError as error:
            logger.warning("Could not generate SBP QR for order %s: %s", order.id, error)
        body = {"paymentUrl": payment_url, "sbpQr": sbp_qr}
    else:
        if settings.payment_checkout_base_url is None:
            raise LandingApiError(503, "PAYMENT_UNAVAILABLE")
        payment_id = public_id("pay")
        base = str(settings.payment_checkout_base_url).rstrip("/")
        payment_url = f"{base}?{urlencode({'paymentId': payment_id, 'orderId': order.id})}"
        session.add(StorePayment(
            order_id=order.id, provider=settings.payment_provider,
            provider_payment_id=payment_id, payment_url=payment_url,
            amount=order.total, currency=order.currency,
        ))
        order.status = "processing"
        body = {"paymentUrl": payment_url}
    remember_idempotent(session, public, "payment.create", key, data, body, 200)
    await session.commit()
    return body

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep
from app.models import StoreOrder, StorePayment
from app.schemas import StoreOrderAdminOut, StorePaymentAdminOut
from app.services.audit import record_activity
from app.services.cdek import CDEKClient, CDEKError
from app.services.tbank import TBankClient, TBankError, receipt_items

router = APIRouter(prefix="/api/orders", tags=["orders"])


def order_out(order: StoreOrder, payment: StorePayment | None) -> StoreOrderAdminOut:
    payment_out = None
    if payment:
        payment_out = StorePaymentAdminOut(
            provider=payment.provider,
            providerPaymentId=payment.provider_payment_id,
            status=payment.status,
            amount=payment.amount,
        )
    return StoreOrderAdminOut(
        id=order.id,
        status=order.status,
        items=order.items,
        customer=order.customer,
        subtotal=order.subtotal,
        delivery=order.delivery,
        total=order.total,
        currency=order.currency,
        candidateId=order.candidate_id,
        createdAt=order.created_at,
        payment=payment_out,
        tracking=order.tracking,
    )


async def latest_payment(session: SessionDep, order_id: str) -> StorePayment | None:
    return await session.scalar(
        select(StorePayment)
        .where(StorePayment.order_id == order_id)
        .order_by(StorePayment.created_at.desc())
        .limit(1)
    )


def tbank_client(settings: SettingsDep) -> TBankClient:
    if not settings.tbank_terminal_key or not settings.tbank_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="T-Bank integration unavailable",
        )
    return TBankClient(
        api_url=str(settings.tbank_api_url),
        terminal_key=settings.tbank_terminal_key,
        password=settings.tbank_password,
    )


def cdek_client(settings: SettingsDep) -> CDEKClient:
    if (
        settings.delivery_provider != "cdek"
        or not settings.cdek_account
        or not settings.cdek_secure_password
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CDEK integration unavailable",
        )
    return CDEKClient(
        str(settings.cdek_api_url), settings.cdek_account, settings.cdek_secure_password
    )


def cdek_order_payload(order: StoreOrder, settings: SettingsDep) -> dict:
    customer = order.customer or {}
    delivery = customer.get("delivery") or {}
    point = delivery.get("pickupPointCode")
    tariff = delivery.get("tariffCode")
    if not point or not tariff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order has no confirmed CDEK pickup point and tariff",
        )
    package_items = []
    total_quantity = 0
    for item in order.items:
        quantity = int(item["quantity"])
        total_quantity += quantity
        unit_price = int(item["unitPrice"])
        package_items.append(
            {
                "name": "Картхолдер CEOMENTALITY",
                "ware_key": item["variantId"],
                "payment": {"value": 0},
                "cost": unit_price / 100,
                "weight": settings.cdek_package_weight_grams,
                "amount": quantity,
                "weight_gross": settings.cdek_package_weight_grams * quantity,
            }
        )
    return {
        "type": 1,
        "number": order.id,
        "order_count": 1,
        "tariff_code": int(tariff),
        "shipment_point": settings.cdek_shipment_point,
        "delivery_point": point,
        "recipient": {
            "name": customer.get("name"),
            "email": customer.get("email"),
            "phones": [{"number": customer.get("phone")}],
        },
        "sender": {
            "name": settings.cdek_sender_name,
            "phones": [{"number": settings.cdek_sender_phone}],
        },
        "delivery_recipient_cost": {"value": 0},
        "packages": [
            {
                "number": f"{order.id}-1",
                "weight": settings.cdek_package_weight_grams * total_quantity,
                "length": settings.cdek_package_length_cm,
                "width": settings.cdek_package_width_cm,
                "height": settings.cdek_package_height_cm,
                "items": package_items,
            }
        ],
    }


@router.get("", response_model=list[StoreOrderAdminOut])
async def list_orders(session: SessionDep, _user: CurrentUserDep):
    orders = (
        await session.scalars(select(StoreOrder).order_by(StoreOrder.created_at.desc()).limit(500))
    ).all()
    if not orders:
        return []
    payments = (
        await session.scalars(
            select(StorePayment)
            .where(StorePayment.order_id.in_([order.id for order in orders]))
            .order_by(StorePayment.created_at.desc())
        )
    ).all()
    latest_by_order: dict[str, StorePayment] = {}
    for payment in payments:
        latest_by_order.setdefault(payment.order_id, payment)
    return [order_out(order, latest_by_order.get(order.id)) for order in orders]


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only founder can delete orders")
    order = await session.get(StoreOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status in {"paid", "shipped", "delivered"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paid or shipped orders cannot be deleted; issue a refund first")
    await session.execute(delete(StorePayment).where(StorePayment.order_id == order_id))
    await session.delete(order)
    await session.commit()


@router.post("/{order_id}/refund", response_model=StoreOrderAdminOut)
async def refund_order(
    order_id: str,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Refund is not allowed")
    order = await session.scalar(
        select(StoreOrder).where(StoreOrder.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    payment = await latest_payment(session, order_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if order.status not in {"paid", "shipped", "delivered"} or payment.status != "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only paid orders can be refunded")
    if payment.provider != "tbank":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Refund unavailable")
    try:
        await tbank_client(settings).request("Cancel", {"PaymentId": payment.provider_payment_id})
    except TBankError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="T-Bank rejected refund"
        ) from error
    payment.status = "cancelled"
    order.status = "cancelled"
    await record_activity(
        session,
        type_="payment.refunded",
        detail=f"Full refund for website order {order.id}",
        actor_id=user.id,
        entity_type="order",
        entity_id=order.id,
        data={"providerPaymentId": payment.provider_payment_id, "amount": payment.amount},
    )
    await session.commit()
    return order_out(order, payment)


@router.post("/{order_id}/complete", response_model=StoreOrderAdminOut)
async def complete_order(
    order_id: str,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action is not allowed")
    order = await session.scalar(
        select(StoreOrder).where(StoreOrder.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    payment = await latest_payment(session, order_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if order.status not in {"paid", "shipped"} or payment.status != "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is not ready")
    if payment.provider != "tbank":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Closing receipt unavailable",
        )
    customer = order.customer or {}
    receipt = {
        "Email": customer.get("email"),
        "Phone": customer.get("phone"),
        "Taxation": settings.tbank_taxation,
        "Items": receipt_items(
            order.items,
            order.delivery,
            tax=settings.tbank_tax,
            payment_method="full_payment",
        ),
        "Payments": {
            "Electronic": 0,
            "AdvancePayment": order.total,
            "Credit": 0,
            "Cash": 0,
            "Provision": 0,
        },
    }
    try:
        await tbank_client(settings).send_closing_receipt(
            {"PaymentId": payment.provider_payment_id, "Receipt": receipt}
        )
    except TBankError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="T-Bank rejected closing receipt",
        ) from error
    order.status = "delivered"
    await record_activity(
        session,
        type_="order.delivered",
        detail=f"Website order {order.id} delivered; closing receipt sent",
        actor_id=user.id,
        entity_type="order",
        entity_id=order.id,
        data={"providerPaymentId": payment.provider_payment_id, "amount": payment.amount},
    )
    await session.commit()
    return order_out(order, payment)


@router.post("/{order_id}/shipment", response_model=StoreOrderAdminOut)
async def create_shipment(
    order_id: str,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action is not allowed")
    order = await session.scalar(
        select(StoreOrder).where(StoreOrder.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    payment = await latest_payment(session, order_id)
    if order.status not in {"paid", "shipped"} or payment is None or payment.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a paid order can be sent to CDEK",
        )
    if order.tracking and order.tracking.get("uuid"):
        return order_out(order, payment)
    try:
        result = await cdek_client(settings).create_order(cdek_order_payload(order, settings))
    except CDEKError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="CDEK rejected shipment creation",
        ) from error
    entity = result["entity"]
    order.tracking = {
        "carrier": "CDEK",
        "number": str(entity.get("cdek_number") or ""),
        "uuid": str(entity["uuid"]),
        "status": "created",
        "pickupPointCode": str((order.customer.get("delivery") or {}).get("pickupPointCode", "")),
        "returnPayer": settings.cdek_return_payer,
    }
    order.status = "shipped"
    await record_activity(
        session,
        type_="shipment.created",
        detail=f"CDEK shipment created for website order {order.id}",
        actor_id=user.id,
        entity_type="order",
        entity_id=order.id,
        data={"provider": "cdek", "uuid": entity["uuid"]},
    )
    await session.commit()
    return order_out(order, payment)


@router.post("/{order_id}/shipment/refresh", response_model=StoreOrderAdminOut)
async def refresh_shipment(
    order_id: str,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action is not allowed")
    order = await session.scalar(
        select(StoreOrder).where(StoreOrder.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    tracking = order.tracking or {}
    if not tracking.get("uuid"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="CDEK shipment has not been created"
        )
    try:
        result = await cdek_client(settings).order(str(tracking["uuid"]))
    except CDEKError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not refresh CDEK shipment",
        ) from error
    entity = result.get("entity") or result
    statuses = entity.get("statuses") or []
    latest_status = statuses[-1].get("code") if statuses else tracking.get("status", "created")
    order.tracking = {
        **tracking,
        "number": str(entity.get("cdek_number") or tracking.get("number") or ""),
        "status": str(latest_status or "created"),
    }
    await session.commit()
    return order_out(order, await latest_payment(session, order_id))

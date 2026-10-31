import hashlib
import hmac
import base64
import binascii
from xml.etree import ElementTree
import ssl
from pathlib import Path
from typing import Any

import httpx


class TBankError(RuntimeError):
    pass


_CERT_DIR = Path(__file__).resolve().parents[2] / "certs"


def _ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    for certificate in (
        "russian_trusted_root_ca.crt",
        "russian_trusted_sub_ca.crt",
    ):
        context.load_verify_locations(cafile=_CERT_DIR / certificate)
    return context


def _token_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def make_token(payload: dict[str, Any], password: str) -> str:
    values = {
        key: value
        for key, value in payload.items()
        if key != "Token" and value is not None and not isinstance(value, (dict, list))
    }
    values["Password"] = password
    source = "".join(_token_value(values[key]) for key in sorted(values))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def verify_token(payload: dict[str, Any], password: str) -> bool:
    supplied = str(payload.get("Token", ""))
    expected = make_token(payload, password)
    return bool(supplied) and hmac.compare_digest(supplied, expected)


class TBankClient:
    def __init__(self, *, api_url: str, terminal_key: str, password: str):
        self.api_url = api_url.rstrip("/")
        self.terminal_key = terminal_key
        self.password = password

    async def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_url(f"{self.api_url}/{method}", payload)

    async def request_url(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"TerminalKey": self.terminal_key, **payload}
        body["Token"] = make_token(body, self.password)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                verify=_ssl_context(),
            ) as client:
                response = await client.post(url, json=body)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TBankError("T-Bank API is unavailable") from error
        if not isinstance(result, dict) or not result.get("Success"):
            code = result.get("ErrorCode", "unknown") if isinstance(result, dict) else "invalid"
            message = result.get("Message", "T-Bank rejected request") if isinstance(result, dict) else ""
            details = result.get("Details", "") if isinstance(result, dict) else ""
            suffix = f" Details: {details}" if details else ""
            raise TBankError(f"T-Bank error {code}: {message}{suffix}")
        return result

    async def send_closing_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        base_url = self.api_url.removesuffix("/v2")
        return await self.request_url(f"{base_url}/cashbox/SendClosingReceipt", payload)

    async def get_sbp_qr(self, payment_id: str) -> str:
        result = await self.request("GetQr", {
            "PaymentId": payment_id,
            "DataType": "IMAGE",
            "PaymentMethod": "SBP",
        })
        data = result.get("Data")
        if not isinstance(data, str) or not data or len(data) > 2_000_000:
            raise TBankError("T-Bank returned an empty SBP QR")
        try:
            raw = data.encode("utf-8") if data.lstrip().startswith("<") else base64.b64decode(data, validate=True)
            root = ElementTree.fromstring(raw)
            if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
                raise ValueError("Not SVG")
        except (ValueError, binascii.Error, ElementTree.ParseError) as error:
            raise TBankError("T-Bank returned an invalid SVG QR") from error
        # Loaded only as an image, never inserted as active HTML.
        return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


def receipt_items(
    order_items: list[dict],
    delivery: int,
    *,
    tax: str,
    payment_method: str = "full_prepayment",
) -> list[dict]:
    items = []
    for item in order_items:
        colour = "белый" if item["variantId"].endswith("white") else "чёрный"
        items.append(
            {
                "Name": f"Картхолдер, {colour}",
                "Price": item["unitPrice"],
                "Quantity": item["quantity"],
                "Amount": item["unitPrice"] * item["quantity"],
                "Tax": tax,
                "PaymentMethod": payment_method,
                "PaymentObject": "commodity",
                "MeasurementUnit": "шт",
            }
        )
    if delivery:
        items.append(
            {
                "Name": "Доставка",
                "Price": delivery,
                "Quantity": 1,
                "Amount": delivery,
                "Tax": tax,
                "PaymentMethod": payment_method,
                "PaymentObject": "service",
                "MeasurementUnit": "усл. ед",
            }
        )
    return items


def payment_status(status: str, success: bool) -> str | None:
    if status == "CONFIRMED" and success:
        return "paid"
    if status in {"NEW", "FORM_SHOWED", "AUTHORIZED", "CONFIRMING"}:
        return "processing"
    if status in {"REJECTED", "AUTH_FAIL", "DEADLINE_EXPIRED"}:
        return "payment_failed"
    if status in {"CANCELED", "REVERSED", "REFUNDED"}:
        return "cancelled"
    return None

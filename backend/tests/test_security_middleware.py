from starlette.requests import Request

from app.core.security_middleware import SecurityMiddleware


def request_with_headers(*, host: str, proto: str = "http") -> Request:
    headers = [(b"host", host.encode()), (b"x-forwarded-proto", proto.encode())]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers})


def test_accepts_configured_origin() -> None:
    middleware = SecurityMiddleware(None, frontend_origin="http://crm.example", session_cookie_name="session")
    request = request_with_headers(host="internal")
    assert middleware.valid_origin(request, "http://crm.example")


def test_accepts_same_origin_with_port() -> None:
    middleware = SecurityMiddleware(None, frontend_origin="http://203.0.113.10", session_cookie_name="session")
    request = request_with_headers(host="203.0.113.10:8080")
    assert middleware.valid_origin(request, "http://203.0.113.10:8080")


def test_rejects_foreign_origin() -> None:
    middleware = SecurityMiddleware(None, frontend_origin="https://crm.example", session_cookie_name="session")
    request = request_with_headers(host="crm.example", proto="https")
    assert not middleware.valid_origin(request, "https://attacker.example")


def test_tbank_webhook_has_dedicated_rate_limit() -> None:
    assert SecurityMiddleware.limit_for("/api/v1/payments/tbank/webhook") == (600, 60)

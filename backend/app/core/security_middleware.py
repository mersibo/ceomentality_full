import asyncio
from collections import defaultdict, deque
from time import monotonic

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app, *, frontend_origin: str, session_cookie_name: str,
        public_session_cookie_name: str = "ceo_public_session",
    ):
        super().__init__(app)
        self.frontend_origin = frontend_origin.rstrip("/")
        self.session_cookie_name = session_cookie_name
        self.public_session_cookie_name = public_session_cookie_name
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    @staticmethod
    def client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        return forwarded or (request.client.host if request.client else "unknown")

    @staticmethod
    def limit_for(path: str) -> tuple[int, int] | None:
        if path == "/api/auth/login":
            return 10, 300
        if path == "/api/v1/payments/tbank/webhook":
            return 600, 60
        if path.startswith("/api/public/") or path == "/api/access-codes/redeem":
            return 30, 60
        if path.startswith("/api/v1/"):
            return (10, 60) if path == "/api/v1/access/check" else (60, 60)
        if path.startswith(("/api/integrations/telegram/", "/api/bot/")):
            return 120, 60
        return None

    def valid_origin(self, request: Request, origin: str) -> bool:
        normalized_origin = origin.rstrip("/").lower()
        if normalized_origin == self.frontend_origin.lower():
            return True

        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        scheme = forwarded_proto or request.url.scheme
        forwarded_host = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
        host = forwarded_host or request.headers.get("host", "").strip()
        return bool(host) and normalized_origin == f"{scheme}://{host}".lower()

    async def dispatch(self, request: Request, call_next):
        has_session = request.cookies.get(self.session_cookie_name) or request.cookies.get(
            self.public_session_cookie_name
        )
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and has_session:
            origin = request.headers.get("origin")
            if origin and not self.valid_origin(request, origin):
                body = (
                    {"error": {"code": "FORBIDDEN"}}
                    if request.url.path.startswith("/api/v1/")
                    else {"detail": "Invalid request origin"}
                )
                return JSONResponse(body, status_code=403)

        limit = self.limit_for(request.url.path)
        if limit:
            maximum, window = limit
            key = f"{self.client_ip(request)}:{request.url.path}"
            now = monotonic()
            async with self.lock:
                bucket = self.requests[key]
                while bucket and bucket[0] <= now - window:
                    bucket.popleft()
                if len(bucket) >= maximum:
                    body = (
                        {"error": {"code": "RATE_LIMITED"}}
                        if request.url.path.startswith("/api/v1/")
                        else {"detail": "Too many requests. Try again later."}
                    )
                    return JSONResponse(
                        body,
                        status_code=429,
                        headers={"Retry-After": str(window)},
                    )
                bucket.append(now)
        return await call_next(request)

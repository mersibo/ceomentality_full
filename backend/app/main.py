from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    activity,
    analytics,
    auth,
    blacklist,
    candidates,
    codes,
    drops,
    email_campaigns,
    health,
    integrations,
    landing,
    notifications,
    orders,
    products,
    public,
    search,
    users,
    workspace,
)
from app.core.config import get_settings
from app.core.security_middleware import SecurityMiddleware
from app.services.landing import LandingApiError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        SecurityMiddleware,
        frontend_origin=str(settings.frontend_origin),
        session_cookie_name=settings.session_cookie_name,
        public_session_cookie_name=settings.public_session_cookie_name,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.frontend_origin).rstrip("/")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type", "Authorization", "X-Integration-Secret", "X-CRM-Integration-Secret",
            "X-CSRF-Token", "Idempotency-Key",
        ],
    )
    app.add_exception_handler(
        LandingApiError,
        lambda _request, exc: JSONResponse(
            {"error": {
                "code": exc.code,
                **({"fields": exc.fields} if exc.fields else {}),
                **({"reason": exc.reason} if exc.reason else {}),
            }},
            status_code=exc.status_code,
            headers={"Cache-Control": "no-store"},
        ),
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if not request.url.path.startswith("/api/v1/"):
            return JSONResponse({"detail": exc.errors()}, status_code=422)
        fields = {}
        for error in exc.errors():
            name = str(error.get("loc", ["body"])[-1])
            fields[name] = "REQUIRED" if error.get("type") == "missing" else "INVALID"
        return JSONResponse(
            {"error": {"code": "VALIDATION_ERROR", "fields": fields}},
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(workspace.router)
    app.include_router(candidates.router)
    app.include_router(blacklist.router)
    app.include_router(drops.router)
    app.include_router(email_campaigns.router)
    app.include_router(codes.router)
    app.include_router(integrations.router)
    app.include_router(notifications.router)
    app.include_router(orders.router)
    app.include_router(products.router)
    app.include_router(public.router)
    app.include_router(landing.router)
    app.include_router(search.router)
    app.include_router(activity.router)
    app.include_router(analytics.router)
    app.include_router(users.router)
    return app


app = create_app()

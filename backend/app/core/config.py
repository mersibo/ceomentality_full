from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CEOMENTALITY API"
    environment: str = "development"
    database_url: str
    secret_key: str = Field(min_length=24)
    session_cookie_name: str = "ceomentality_session"
    cookie_secure: bool = False
    allow_insecure_http: bool = False
    frontend_origin: AnyHttpUrl = "http://127.0.0.1:5173"
    first_superuser_email: EmailStr = "manager@ceomentality.club"
    first_superuser_password: str = Field(min_length=8)
    access_token_minutes: int = 60 * 12
    telegram_integration_secret: str | None = Field(default=None, min_length=24)
    public_session_cookie_name: str = "ceo_public_session"
    public_session_days: int = Field(default=7, ge=1, le=30)
    quote_ttl_minutes: int = Field(default=30, ge=5, le=180)
    delivery_price_kopecks: int = Field(default=50000, ge=0)
    delivery_provider: Literal["fixed", "cdek"] = "fixed"
    cdek_api_url: AnyHttpUrl = "https://api.cdek.ru/v2"
    cdek_account: str | None = None
    cdek_secure_password: str | None = None
    cdek_shipment_point: str = "MSK147"
    cdek_sender_city_code: int = Field(default=44, ge=1)
    cdek_sender_name: str = "CEOMENTALITY"
    cdek_sender_phone: str = "+79966553590"
    cdek_package_weight_grams: int = Field(default=500, ge=1)
    cdek_package_length_cm: int = Field(default=13, ge=1)
    cdek_package_width_cm: int = Field(default=9, ge=1)
    cdek_package_height_cm: int = Field(default=4, ge=1)
    cdek_return_payer: Literal["customer", "store"] = "customer"
    email_provider: Literal["disabled", "rusender"] = "disabled"
    rusender_api_url: AnyHttpUrl = "https://api.rusender.ru/api/v1"
    rusender_api_token: str | None = None
    rusender_key_id: int | None = Field(default=None, ge=1)
    email_outbox_poll_seconds: int = Field(default=5, ge=1, le=300)
    payment_provider: Literal["disabled", "mock", "tbank"] = "disabled"
    payment_checkout_base_url: AnyHttpUrl | None = None
    payment_webhook_secret: str | None = Field(default=None, min_length=24)
    public_site_url: AnyHttpUrl | None = None
    tbank_api_url: AnyHttpUrl = "https://securepay.tinkoff.ru/v2"
    tbank_terminal_key: str | None = None
    tbank_password: str | None = Field(default=None, min_length=8)
    tbank_taxation: Literal["usn_income"] = "usn_income"
    tbank_tax: Literal["none", "vat0"] = "vat0"

    @field_validator(
        "payment_checkout_base_url", "payment_webhook_secret", "public_site_url",
        "tbank_terminal_key", "tbank_password", "cdek_account", "cdek_secure_password",
        "rusender_api_token", "rusender_key_id",
        mode="before"
    )
    @classmethod
    def blank_optional_values_are_none(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production":
            weak_values = {
                "change-this-to-a-long-random-secret",
                "change-this-to-a-long-random-secret-before-production",
                "change-me-now",
                "change-me-now-01",
            }
            if self.secret_key in weak_values or self.secret_key.startswith("replace-with-"):
                raise ValueError("SECRET_KEY must be changed for production")
            if self.first_superuser_password in weak_values or self.first_superuser_password.startswith(
                "replace-with-"
            ):
                raise ValueError("FIRST_SUPERUSER_PASSWORD must be changed for production")
            if self.frontend_origin.scheme == "http":
                if not self.allow_insecure_http:
                    raise ValueError(
                        "HTTP FRONTEND_ORIGIN requires ALLOW_INSECURE_HTTP=true"
                    )
                if self.cookie_secure:
                    raise ValueError("COOKIE_SECURE must be false for temporary HTTP deployments")
            elif not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true for production HTTPS deployments")
            if not self.telegram_integration_secret or self.telegram_integration_secret.startswith(
                "replace-with-"
            ):
                raise ValueError("TELEGRAM_INTEGRATION_SECRET is required for production")
            if self.payment_provider == "mock" and (
                self.payment_checkout_base_url is None or not self.payment_webhook_secret
            ):
                raise ValueError(
                    "PAYMENT_CHECKOUT_BASE_URL and PAYMENT_WEBHOOK_SECRET are required when payments are enabled"
                )
            if self.payment_provider == "tbank" and (
                not self.tbank_terminal_key
                or self.tbank_terminal_key.startswith("replace-with-")
                or not self.tbank_password
                or self.tbank_password.startswith("replace-with-")
                or self.public_site_url is None
            ):
                raise ValueError(
                    "TBANK_TERMINAL_KEY, TBANK_PASSWORD and PUBLIC_SITE_URL are required for T-Bank"
                )
            if self.delivery_provider == "cdek" and (
                not self.cdek_account
                or self.cdek_account.startswith("replace-with-")
                or not self.cdek_secure_password
                or self.cdek_secure_password.startswith("replace-with-")
            ):
                raise ValueError(
                    "CDEK_ACCOUNT and CDEK_SECURE_PASSWORD are required for CDEK delivery"
                )
            if self.email_provider == "rusender" and (
                not self.rusender_api_token
                or self.rusender_api_token.startswith("replace-with-")
            ):
                raise ValueError("RUSENDER_API_TOKEN is required for RuSender email")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

from app.core.config import Settings


def test_blank_rusender_key_id_is_treated_as_missing() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:password@localhost/database",
        secret_key="a-secure-test-secret-with-enough-length",
        first_superuser_password="secure-test-password",
        rusender_key_id="",
    )

    assert settings.rusender_key_id is None

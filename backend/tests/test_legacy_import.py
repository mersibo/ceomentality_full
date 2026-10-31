import pytest

from app.import_legacy_bot import retarget_insert


def test_retargets_quoted_public_table() -> None:
    source = 'INSERT INTO "public"."users" ("user_id") VALUES (1);'
    assert retarget_insert(source, "users", "legacy_bot_users").startswith(
        'INSERT INTO legacy_bot_users ("user_id")'
    )


def test_rejects_unexpected_statement() -> None:
    with pytest.raises(ValueError):
        retarget_insert("DELETE FROM users", "users", "legacy_bot_users")

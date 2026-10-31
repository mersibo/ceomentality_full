import pytest
from pydantic import ValidationError

from app.schemas import BlacklistEntryCreate
from app.services.blacklist import normalize_telegram_id, normalize_telegram_username


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@SomeUser", "someuser"),
        ("https://t.me/SomeUser", "someuser"),
        ("t.me/someuser?start=club", "someuser"),
        ("tg:12345", None),
        ("12345", None),
        (None, None),
    ],
)
def test_normalize_telegram_username(raw, expected):
    assert normalize_telegram_username(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(12345, "12345"), ("tg:12345", "12345"), ("-1000123", "-1000123"), ("@user", None)],
)
def test_normalize_telegram_id(raw, expected):
    assert normalize_telegram_id(raw) == expected


def test_blacklist_entry_requires_telegram_identifier():
    with pytest.raises(ValidationError):
        BlacklistEntryCreate(name="Blocked user", reason="Abuse")

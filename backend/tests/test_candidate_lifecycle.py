from app.services.candidates import person_key, transition_allowed
from app.services.telegram_outbox import parse_telegram_username


def test_person_key_prefers_telegram_id() -> None:
    assert person_key(telegram_id=12345, telegram="@ignored", fallback="candidate") == "tg:12345"


def test_person_key_normalizes_telegram_link() -> None:
    assert (
        person_key(telegram_id=None, telegram="https://t.me/ExampleUser?start=x", fallback="candidate")
        == "handle:exampleuser"
    )


def test_purchase_status_transitions() -> None:
    assert transition_allowed("purchase", "Under review", "Approved")
    assert transition_allowed("purchase", "Approved", "Code assigned")
    assert not transition_allowed("purchase", "Under review", "Code used")


def test_club_status_transitions() -> None:
    assert transition_allowed("club", "Approved", "Accepted")
    assert not transition_allowed("club", "Accepted", "Under review")


def test_telegram_username_normalization() -> None:
    assert parse_telegram_username("https://t.me/ExampleUser?start=drop") == "exampleuser"
    assert parse_telegram_username("@ExampleUser") == "exampleuser"
    assert parse_telegram_username("not a telegram handle") is None
    assert parse_telegram_username("@abc") is None

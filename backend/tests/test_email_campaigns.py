from app.models import Candidate, Drop
from app.services.email_campaigns import candidate_email, render_email
from app.services.rusender import RuSenderClient


def test_campaign_variables_and_candidate_email():
    candidate = Candidate(
        id="candidate-1",
        name="Иван",
        initials="ИИ",
        person_key="email:test@example.com",
        questionnaire_answers={"email": " Test@Example.com "},
    )
    drop = Drop(
        id="drop-1",
        name="Drop One",
        code="CM-TEST",
        validity="10–20 октября",
    )
    assert candidate_email(candidate) == "test@example.com"
    assert (
        render_email("{{name}} / {{drop_name}} / {{drop_code}} / {{validity}}", candidate, drop)
        == "Иван / Drop One / CM-TEST / 10–20 октября"
    )


async def test_rusender_discovers_key_and_sends_with_idempotency():
    calls = []

    class StubClient(RuSenderClient):
        async def _request(self, method, path, **kwargs):
            calls.append((method, path, kwargs))
            if method == "GET":
                return {"items": [{"id": 42, "status": "ACTIVE"}]}
            return {"uuid": "message-uuid"}

    client = StubClient("https://api.example.test", "token")
    provider_id = await client.send(
        to_email="person@example.com",
        to_name="Иван",
        from_email="ceomentality@internet.ru",
        from_name="CEOMENTALITY",
        subject="Код",
        text="CM-TEST",
        idempotency_key="campaign-1-person-1",
    )
    assert provider_id == "message-uuid"
    assert calls[0][1] == "/public/external-mails/keys"
    assert calls[1][1] == "/external-mails/send/42"
    assert calls[1][2]["json"]["idempotencyKey"] == "campaign-1-person-1"

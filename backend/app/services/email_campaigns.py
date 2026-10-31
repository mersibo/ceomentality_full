from pydantic import EmailStr, TypeAdapter, ValidationError

from app.models import Candidate, Drop

email_adapter = TypeAdapter(EmailStr)


def candidate_email(candidate: Candidate) -> str | None:
    value = str((candidate.questionnaire_answers or {}).get("email") or "").strip().lower()
    if not value:
        return None
    try:
        return str(email_adapter.validate_python(value))
    except ValidationError:
        return None


def render_email(value: str, candidate: Candidate, drop: Drop, access_code: str | None = None) -> str:
    replacements = {
        "{{name}}": candidate.name,
        "{{drop_name}}": drop.name,
        "{{drop_code}}": access_code or candidate.code or drop.code,
        "{{validity}}": drop.validity or "уточняется организатором",
    }
    for key, replacement in replacements.items():
        value = value.replace(key, replacement)
    return value

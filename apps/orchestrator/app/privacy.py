from __future__ import annotations

import re
from dataclasses import dataclass


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE)
API_KEY_RE = re.compile(r"\b(?:sk|pk|rk|key|token)_[A-Za-z0-9._-]{12,}\b", re.IGNORECASE)
PASSWORD_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|пароль|токен|token|secret|секрет|api[_ -]?key|ключ)\s*[:=]\s*([^\s,;]+)"
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redacted: bool
    markers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "redacted": self.redacted,
            "markers": list(self.markers),
        }


def redact_for_llm(text: str) -> RedactionResult:
    result = str(text or "")
    markers: list[str] = []

    result, count = BEARER_RE.subn("Bearer [REDACTED_TOKEN]", result)
    if count:
        markers.append("bearer_token")

    result, count = API_KEY_RE.subn("[REDACTED_API_KEY]", result)
    if count:
        markers.append("api_key")

    result, count = PASSWORD_RE.subn(lambda match: f"{match.group(1)}=[REDACTED_SECRET]", result)
    if count:
        markers.append("secret_assignment")

    result, count = EMAIL_RE.subn("[REDACTED_EMAIL]", result)
    if count:
        markers.append("email")

    result, count = PHONE_RE.subn("[REDACTED_PHONE]", result)
    if count:
        markers.append("phone")

    return RedactionResult(
        text=result,
        redacted=bool(markers),
        markers=tuple(dict.fromkeys(markers)),
    )

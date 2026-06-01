"""Email preprocessing before LLM."""

import re

from models.classifier_models import EmailInput

_ORDER_ID_PATTERN = re.compile(
    r"\b(?:PUKOID|POV|MOC)[A-Z0-9]*\b|\b[A-Z]{2,}\d{6,}\b",
    re.IGNORECASE,
)
_INSTANCE_PATTERN = re.compile(r"<instance\d*>|<instance>", re.IGNORECASE)
_FAIL_KEYWORDS = re.compile(r"\bFAIL\b|\bTimeout\b|\bERROR\b", re.IGNORECASE)


def normalize_email(email: EmailInput) -> str:
    subject = email.subject.strip()
    body = email.body.strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return f"Subject: {subject}\n\nBody:\n{body}"


def extract_signals(email: EmailInput) -> list[str]:
    combined = f"{email.subject}\n{email.body}"
    signals: list[str] = []

    for match in _ORDER_ID_PATTERN.finditer(combined):
        signals.append(f"order_id:{match.group(0)}")

    for match in _INSTANCE_PATTERN.finditer(combined):
        signals.append(f"instance:{match.group(0)}")

    for match in _FAIL_KEYWORDS.finditer(combined):
        signals.append(f"keyword:{match.group(0)}")

    if email.sender:
        signals.append(f"sender:{email.sender}")

    return list(dict.fromkeys(signals))


def build_user_prompt(email: EmailInput) -> str:
    normalized = normalize_email(email)
    signals = extract_signals(email)
    if not signals:
        return normalized
    signals_block = "\n".join(f"- {s}" for s in signals)
    return f"{normalized}\n\nDetected signals:\n{signals_block}"

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_PHONE_STRIP = re.compile(r"[^\d+]")


@dataclass
class Lead:
    email: str
    name: str
    source: str
    phone: Optional[str] = None
    company: Optional[str] = None
    industry_context: Optional[str] = None
    raw_payload: dict = field(default_factory=dict)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = _PHONE_STRIP.sub("", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}" if digits else None


def normalize(raw: dict) -> Lead:
    """Validate and normalize a raw lead dict from any source.

    Args:
        raw: Dict with at minimum email, name, source keys.

    Returns:
        Normalized Lead dataclass.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    email = raw.get("email", "").strip()
    name = raw.get("name", "").strip()
    source = raw.get("source", "").strip()

    if not email:
        raise ValueError("Lead missing required field: email")
    if "@" not in email:
        raise ValueError(f"Invalid email format: {email!r}")
    if not name:
        raise ValueError("Lead missing required field: name")
    if not source:
        raise ValueError("Lead missing required field: source")

    lead = Lead(
        email=_normalize_email(email),
        name=name,
        source=source,
        phone=_normalize_phone(raw.get("phone")),
        company=raw.get("company", "").strip() or None,
        industry_context=raw.get("industry_context", "").strip() or None,
        raw_payload=raw,
    )

    logger.debug("Normalized lead: %s (%s)", lead.email, lead.source)
    return lead

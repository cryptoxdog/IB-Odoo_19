"""One display format for every phone and email stored on a partner.

Pure functions: no Odoo import, so the ERP import, the VanillaSoft import, a
manual edit and the upgrade migration share the same rules and the rules are
tested without an Odoo runtime.

Phones
    A North American (NANP: US, CA and the other ``+1`` countries) number is
    written ``(XXX) XXX-XXXX``, an extension as `` x123``. Any other number is
    written in international form ``+CC ...`` when the ``phonenumbers`` library
    (the library Odoo's own ``phone_validation`` wraps, present on Odoo.sh) can
    parse it; without the library a ``+`` number keeps its digits and its
    spacing collapsed to single spaces. A value that cannot be parsed, a blank
    and the literal ``NULL`` are returned unchanged apart from surrounding
    whitespace, and :func:`format_phone_result` reports them so the caller can
    log once.

Emails
    Split on ``;`` or ``,``, strip, lowercase, keep only ``local@domain.tld``
    shaped entries, de-duplicate keeping the first, join with ``", "``. No
    domain is ever removed here: dropping the brokerage's own mailboxes is an
    import-only rule owned elsewhere.

Both functions are idempotent.
"""

from __future__ import annotations

import re
from typing import NamedTuple

NANP_COUNTRIES = frozenset(
    {
        "US",
        "CA",
        "AG",
        "AI",
        "AS",
        "BB",
        "BM",
        "BS",
        "DM",
        "DO",
        "GD",
        "GU",
        "JM",
        "KN",
        "KY",
        "LC",
        "MP",
        "MS",
        "PR",
        "SX",
        "TC",
        "TT",
        "VC",
        "VG",
        "VI",
    }
)

_EXTENSION = re.compile(r"\s*(?:x|ext\.?|extension|#)\s*(\d{1,6})\s*$", re.IGNORECASE)
_ALLOWED_PHONE_CHARS = re.compile(r"^[\d\s().+\-/]+$")
_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>.]+$")
_ANGLE_ADDRESS = re.compile(r"<\s*([^<>]+?)\s*>")
_NULL_TOKENS = frozenset({"null", "none", "n/a"})


class PhoneResult(NamedTuple):
    value: str
    parsed: bool


class EmailResult(NamedTuple):
    value: str
    dropped: int


def _country(country_code: str | None) -> str:
    return (country_code or "US").strip().upper() or "US"


def _split_extension(text: str) -> tuple[str, str]:
    match = _EXTENSION.search(text)
    if not match:
        return text, ""
    return text[: match.start()], match.group(1)


def _nanp(digits: str, extension: str) -> str | None:
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
        return None
    formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return f"{formatted} x{extension}" if extension else formatted


def _international(text: str, country: str) -> str | None:
    """International ``+CC ...`` form through ``phonenumbers`` when available."""
    try:
        import phonenumbers  # noqa: PLC0415 — optional; Odoo's phone_validation ships it
    except ImportError:
        return None
    try:
        number = phonenumbers.parse(text, None if text.startswith("+") else country)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


def format_phone_result(raw: str | None, country_code: str | None = "US") -> PhoneResult:
    """Format one phone value and say whether it was understood."""
    text = (raw or "").strip()
    if not text or text.lower() in _NULL_TOKENS:
        return PhoneResult(text, False)
    body, extension = _split_extension(text)
    body = body.strip()
    if not body or not _ALLOWED_PHONE_CHARS.match(body):
        return PhoneResult(text, False)
    digits = re.sub(r"\D", "", body)
    country = _country(country_code)
    plus = body.startswith("+")
    if (plus and digits.startswith("1")) or (not plus and country in NANP_COUNTRIES):
        formatted = _nanp(digits, extension)
        return PhoneResult(formatted, True) if formatted else PhoneResult(text, False)
    international = _international(body, country)
    if international:
        return PhoneResult(f"{international} x{extension}" if extension else international, True)
    if plus and len(digits) >= 8:
        collapsed = "+" + " ".join(body[1:].split())
        return PhoneResult(f"{collapsed} x{extension}" if extension else collapsed, True)
    return PhoneResult(text, False)


def format_phone(raw: str | None, country_code: str | None = "US") -> str:
    """Return ``raw`` in the one stored phone format; unparseable values unchanged."""
    return format_phone_result(raw, country_code).value


def format_emails_result(raw: str | None) -> EmailResult:
    """Format an email list and count the entries dropped as malformed."""
    kept: list[str] = []
    dropped = 0
    for entry in re.split(r"[;,]", raw or ""):
        candidate = entry.strip()
        if not candidate:
            continue
        angle = _ANGLE_ADDRESS.search(candidate)
        if angle:
            candidate = angle.group(1)
        candidate = candidate.strip().lower()
        if not _EMAIL.match(candidate):
            dropped += 1
            continue
        if candidate not in kept:
            kept.append(candidate)
    return EmailResult(", ".join(kept), dropped)


def format_emails(raw: str | None) -> str:
    """Return the email list in the one stored format."""
    return format_emails_result(raw).value

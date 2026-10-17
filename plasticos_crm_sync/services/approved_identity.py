"""Operator-approved VanillaSoft ContactID → ERP CT_ID crosswalk.

The CSV is an allowlist of source IDs. It is not an Odoo import file.
Phase 0 binds the contact note to the VanillaSoft custom field ``Notes``.
Call comments are a different payload and are never that note.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path

CROSSWALK_PARAM = "plasticos_crm_sync.approved_contact_crosswalk"
CROSSWALK_HEADER = ("erp_ct_id", "vanillasoft_contact_id")
PINNED_SHA256 = "f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2"
PINNED_VS_COUNT = 763
PINNED_ERP_COUNT = 716
XMLID_MODULE = "plasticos_transaction"
CONTACT_NOTE_KEY = "Notes"
MOBILE_PHONE_NAMES = frozenset({"mobile", "mobile 1", "mobile 2", "cell"})


class CrosswalkError(ValueError):
    """The configured crosswalk is missing or does not match the pinned census."""


class CrosswalkBlocked(Exception):
    """An approved contact note cannot be stored without a new field."""


def xmlid_name(ct_id: str) -> str:
    return f"legacy_erp_contact_{ct_id}"


_PHONE_EXTENSION = re.compile(r"(?:ext\.?|extension|x)[:\s]*\d+\s*$", re.IGNORECASE)


def digits_only(number: str) -> str:
    return "".join(ch for ch in str(number or "") if ch.isdigit())


def phone_match_key(number: str) -> str:
    """Normalize one number before it is compared with any other number.

    Punctuation and a trailing extension are removed first. A leading NANP
    country code is removed only when that leaves a 10-digit number. The
    result is compared for exact equality. A shorter number is not a match
    for a longer one.
    """
    text = _PHONE_EXTENSION.sub("", str(number or "").strip())
    digits = digits_only(text)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def validate_crosswalk(
    text: str,
    *,
    expected_sha256: str = PINNED_SHA256,
    expected_vs: int = PINNED_VS_COUNT,
    expected_erp: int = PINNED_ERP_COUNT,
) -> dict[str, str]:
    """Return ``{vanillasoft_contact_id: erp_ct_id}`` or raise ``CrosswalkError``."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != expected_sha256:
        raise CrosswalkError(f"approved crosswalk SHA256 {digest} != {expected_sha256}")
    reader = csv.reader(io.StringIO(text))
    try:
        header = tuple(next(reader))
    except StopIteration as exc:
        raise CrosswalkError("approved crosswalk is empty") from exc
    if header != CROSSWALK_HEADER:
        raise CrosswalkError(f"approved crosswalk header {header!r} != {CROSSWALK_HEADER!r}")
    mapping: dict[str, str] = {}
    erp_ids: set[str] = set()
    for line_no, row in enumerate(reader, start=2):
        if not row or (len(row) == 1 and row[0] == ""):
            continue
        if len(row) != 2 or not row[0].isdigit() or not row[1].isdigit():
            raise CrosswalkError(f"approved crosswalk row {line_no} is not two numeric source IDs")
        ct_id, vs_id = row
        if vs_id in mapping and mapping[vs_id] != ct_id:
            raise CrosswalkError(f"VanillaSoft {vs_id} maps to more than one ERP CT_ID")
        mapping[vs_id] = ct_id
        erp_ids.add(ct_id)
    if len(mapping) != expected_vs or len(erp_ids) != expected_erp:
        raise CrosswalkError(
            f"approved crosswalk census {len(mapping)} VanillaSoft / {len(erp_ids)} ERP "
            f"!= {expected_vs} / {expected_erp}"
        )
    return mapping


def load_crosswalk_map(env) -> dict[str, str] | None:
    """Load the pinned file, or ``None`` when the parameter is unset.

    A set parameter that is missing or mismatched raises. An environment with
    no ``ir.config_parameter`` model (pure-python fakes) has no crosswalk.
    """
    try:
        model = env["ir.config_parameter"]
    except (KeyError, AttributeError):
        return None
    icp = model.sudo() if hasattr(model, "sudo") else model
    path = (icp.get_param(CROSSWALK_PARAM) or "").strip()
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        raise CrosswalkError(f"approved crosswalk file is missing: {path}")
    return validate_crosswalk(file_path.read_text(encoding="utf-8"))


def contact_note_text(custom_fields: dict[str, str] | None) -> str:
    """The contact note is the custom field ``Notes`` only."""
    if not custom_fields:
        return ""
    return str(custom_fields.get(CONTACT_NOTE_KEY) or "").strip()


def append_note(existing: str | None, note: str) -> str | None:
    """Return the appended description, or ``None`` when nothing should be written."""
    text = (note or "").strip()
    if not text:
        return None
    current = existing or ""
    if current.rstrip().endswith(text):
        return None
    if not current:
        return text
    separator = "" if current.endswith("\n") else "\n"
    return f"{current}{separator}{text}"


def note_held_by_fields(fields: dict | None, note: str) -> bool:
    text = (note or "").strip()
    if not text or not isinstance(fields, dict):
        return False
    stored = str(fields.get(CONTACT_NOTE_KEY) or "").strip()
    return bool(stored) and (stored == text or stored.rstrip().endswith(text))


def fields_with_contact_note(fields: dict | None, note: str) -> dict | None:
    """Place ``Notes`` on an existing provider row. ``None`` means no write."""
    text = (note or "").strip()
    if not text:
        return None
    current = dict(fields or {})
    if note_held_by_fields(current, text):
        return None
    merged = append_note(str(current.get(CONTACT_NOTE_KEY) or ""), text)
    if merged is None:
        return None
    current[CONTACT_NOTE_KEY] = merged
    return current


def phone_kinds(phones: object) -> tuple[tuple[str, str], ...]:
    """``(mobile|other, number)`` for every enabled phone, first occurrence wins."""
    if not isinstance(phones, list):
        return ()
    seen: set[str] = set()
    kept: list[tuple[str, str]] = []
    for item in phones:
        if not isinstance(item, dict):
            continue
        disabled = item.get("disabled", item.get("Disabled"))
        if str(disabled).strip().lower() in {"1", "true", "yes"}:
            continue
        number = str(item.get("number") or "").strip()
        token = phone_match_key(number)
        if not token or token in seen:
            continue
        seen.add(token)
        name = str(item.get("name") or "").strip().lower()
        kind = "mobile" if name in MOBILE_PHONE_NAMES else "other"
        kept.append((kind, number))
    return tuple(kept)

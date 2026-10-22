"""Operator-approved VanillaSoft ContactID → ERP CT_ID crosswalk.

The CSV is an allowlist of source IDs. It is not an Odoo import file.
Phase 0 binds the contact note to the VanillaSoft custom field ``Notes``.
Call comments are a different payload and are never that note.
The note is appended to the ERP person's ``res.partner.comment``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from html import escape
from html.parser import HTMLParser
from pathlib import Path

CROSSWALK_PARAM = "plasticos_crm_sync.approved_contact_crosswalk"
CROSSWALK_HEADER = ("erp_ct_id", "vanillasoft_contact_id")
PINNED_SHA256 = "9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1"
PINNED_VS_COUNT = 759
PINNED_ERP_COUNT = 691
XMLID_MODULE = "plasticos_transaction"
# Second VanillaSoft ids for a person the crosswalk already approves on an
# active ERP contact. The inactive CT_ID is the wrong target. These ids are
# not imported again.
# The inactive contact is the wrong target. The active company is already
# imported, and this person is not one of its active contacts. The VanillaSoft
# contact is placed on that company. It is not a second lead.
ACTIVE_COMPANY_CP_BY_VS = {
    "572647290": "399",  # WESTBURY PAPERSTOCK WAREHOUSE
    "573474286": "1405",  # MIDWEST FIBER INC, including Normal, IL
    "579156006": "1484",  # ASHEBORO RECYCLING
    "700174793": "1257",  # PRATT INDUSTRIES; Jay Wallace is inactive on this active company
    "683417624": "1380",  # Jay Saxton, regional manager on active BALCONES RECYCLING
    "609608749": "2461",  # Wanda McGee, owner; Randy is the plant manager on FOUR SEASONS PRODUCE
    "715993397": "2076",  # Jessica Klein; the Le Mars address belongs to active KAMPS INC
}
OMITTED_DUPLICATE_VS_IDS = frozenset(
    {
        "1045036935",  # inactive CT 127550001; active person is approved as CT 179700001
        "1179868294",  # inactive CT 127200001; active person is approved as CT 126500001
        "584402429",  # inactive CT 64200001; active person is approved as CT 126850001
        "585278462",  # same inactive person as 584402429
    }
)
CONTACT_NOTE_KEY = "Notes"
MOBILE_PHONE_NAMES = frozenset({"mobile", "mobile 1", "mobile 2", "cell"})


class CrosswalkError(ValueError):
    """The configured crosswalk is missing or does not match the pinned census."""


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
        if len(row) != 2 or not row[1].isdigit() or (row[0] and not row[0].isdigit()):
            raise CrosswalkError(f"approved crosswalk row {line_no} is not two numeric source IDs")
        ct_id, vs_id = row
        if vs_id in mapping and mapping[vs_id] != ct_id:
            raise CrosswalkError(f"VanillaSoft {vs_id} maps to more than one ERP CT_ID")
        mapping[vs_id] = ct_id
        if ct_id:
            erp_ids.add(ct_id)
    if len(mapping) != expected_vs or len(erp_ids) != expected_erp:
        raise CrosswalkError(
            f"approved crosswalk census {len(mapping)} VanillaSoft / {len(erp_ids)} ERP "
            f"!= {expected_vs} / {expected_erp}"
        )
    return mapping


def without_duplicate_contacts(mapping: dict[str, str] | None) -> dict[str, str] | None:
    """Drop VanillaSoft ids that repeat a person already approved on an active contact."""
    if mapping is None:
        return None
    return {vs_id: ct_id for vs_id, ct_id in mapping.items() if vs_id not in OMITTED_DUPLICATE_VS_IDS}


def load_crosswalk_map(env) -> dict[str, str] | None:
    """Load the pinned file, or ``None`` when the parameter is unset.

    A set parameter that is missing or mismatched raises. An environment with
    no ``ir.config_parameter`` model (pure-python fakes) has no crosswalk.
    """
    try:
        model = env["ir.config_parameter"]
    except (KeyError, AttributeError, TypeError):
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


_BLOCK_TAGS = frozenset({"p", "div", "li", "blockquote", "pre", "tr", "h1", "h2", "h3", "h4", "h5", "h6"})


class _CommentBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._parts: list[str] = []

    def flush(self) -> None:
        text = _squash("".join(self._parts))
        if text:
            self.blocks.append(text)
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.flush()
        elif tag == "br":
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self.flush()

    def handle_data(self, data):
        self._parts.append(data)


def _squash(text: str) -> str:
    return " ".join(str(text or "").split())


def comment_blocks(comment: str | None) -> tuple[str, ...]:
    """The text of each paragraph in an Html ``comment``, whitespace collapsed."""
    parser = _CommentBlocks()
    parser.feed(str(comment or ""))
    parser.close()
    parser.flush()
    return tuple(parser.blocks)


def comment_holds(comment: str | None, note: str) -> bool:
    """True when one paragraph, or a run of adjacent paragraphs, has the text of ``note``."""
    text = _squash(note)
    if not text:
        return False
    blocks = comment_blocks(comment)
    for start in range(len(blocks)):
        joined = ""
        for block in blocks[start:]:
            joined = f"{joined} {block}" if joined else block
            if joined == text:
                return True
            if len(joined) >= len(text):
                break
    return False


def comment_with_note(comment: str | None, note: str) -> str | None:
    """``comment`` with ``note`` appended as its own paragraph. ``None`` means no write.

    Whole paragraphs are compared, so the ERP notes and any other CRM note on
    the partner are kept as they are.
    """
    text = (note or "").strip()
    if not text or comment_holds(comment, text):
        return None
    return f"{comment or ''}<p>{escape(text, quote=False)}</p>"


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

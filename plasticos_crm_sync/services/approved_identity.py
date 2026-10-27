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
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path

CROSSWALK_PARAM = "plasticos_crm_sync.approved_contact_crosswalk"
CROSSWALK_HEADER = ("erp_ct_id", "vanillasoft_contact_id")
PINNED_SHA256 = "f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2"
PINNED_VS_COUNT = 763
PINNED_ERP_COUNT = 716
XMLID_MODULE = "plasticos_transaction"
CONTACT_NOTE_KEY = "Notes"
MOBILE_PHONE_NAMES = frozenset({"mobile", "mobile 1", "mobile 2", "cell"})
FAX_PHONE_NAMES = frozenset({"fax"})
# Source names that may fill the native primary number, in preference order.
# Mobile 2 fills ``mobile`` only when no primary mobile exists.
PRIMARY_PHONE_NAMES = ("direct", "phone", "work", "office")
PRIMARY_MOBILE_NAMES = ("mobile", "mobile 1", "cell", "mobile 2")


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


def phone_identity_key(number: str) -> str:
    """``phone_match_key`` plus the extension, so ``x101`` and ``x102`` stay two lines.

    Formatting variants of one line, with or without a leading NANP ``1``,
    still share one key. A number with an extension is a different line from
    the same number without one.
    """
    base = phone_match_key(number)
    if not base:
        return ""
    match = _PHONE_EXTENSION.search(str(number or "").strip())
    extension = digits_only(match.group(0)) if match else ""
    return f"{base}x{extension}" if extension else base


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


_IMPORTER_PARAGRAPH = re.compile(r"<p>([^<]*)</p>", re.IGNORECASE)
_LABELLED_SOURCE_PARAGRAPH = re.compile(r"^VanillaSoft (?:ContactID \S+ )?(.+?): (.+)$")


def _excluded_importer_paragraph(text: str) -> bool:
    """True only for a full importer line naming an excluded source column."""
    match = _LABELLED_SOURCE_PARAGRAPH.match(" ".join(str(text or "").split()))
    if match is None:
        return False
    from ..adapters.base import is_excluded_source_field

    return is_excluded_source_field(match.group(1))


def without_excluded_source_paragraphs(html: str | None) -> str:
    """Drop ``<p>VanillaSoft … excluded label: …</p>`` nodes. Every other byte stays.

    The match is the paragraph the importer writes, including the ContactID form.
    A note that merely mentions an excluded word is not a match. Nested or
    attributed markup is not a match, so it is not rewritten.
    """
    source = "" if html is None else str(html)
    if not source:
        return source
    pieces: list[str] = []
    last = 0
    changed = False
    for match in _IMPORTER_PARAGRAPH.finditer(source):
        text = unescape(match.group(1))
        if not _excluded_importer_paragraph(text):
            continue
        pieces.append(source[last : match.start()])
        last = match.end()
        changed = True
    if not changed:
        return source
    pieces.append(source[last:])
    return "".join(pieces)


def comment_with_note(comment: str | None, note: str) -> str | None:
    """``comment`` with ``note`` appended as its own paragraph. ``None`` means no write.

    Whole paragraphs are compared, so the ERP notes and any other CRM note on
    the partner are kept as they are.
    """
    text = (note or "").strip()
    if not text or comment_holds(comment, text):
        return None
    return f"{comment or ''}<p>{escape(text, quote=False)}</p>"


def phone_kind(name: str) -> str:
    """The ``plasticos.partner.phone`` label for a provider phone name."""
    key = str(name or "").strip().lower()
    if key in MOBILE_PHONE_NAMES:
        return "mobile"
    if key in FAX_PHONE_NAMES:
        return "fax"
    return "other"


def read_phones(phones: object, *, contact_ref: str = "") -> tuple[tuple[tuple[str, str], ...], frozenset[str]]:
    """``((source label, number), ...)`` for every enabled entry, and the keys of the disabled ones.

    ``disabled`` is read with the adapter's strict parser. An unrecognised
    spelling raises ``CrmAdapterError`` naming the contact and the entry: it is
    neither an enabled nor a disabled number. The disabled keys let a caller
    refuse the same number arriving through another payload field.
    """
    # Imported here: the adapter package lazily imports this module.
    from ..adapters.vanillasoft.adapter import _first_present, vs_bool

    if not isinstance(phones, list):
        return (), frozenset()
    kept: list[tuple[str, str]] = []
    disabled: set[str] = set()
    for position, item in enumerate(phones):
        if not isinstance(item, dict):
            continue
        field_name = f"contact {contact_ref} phone_numbers[{position}].disabled"
        number = str(item.get("number") or "").strip()
        key = phone_identity_key(number)
        if vs_bool(_first_present(item, "disabled", "Disabled"), field=field_name):
            if key:
                disabled.add(key)
            continue
        if key:
            kept.append((str(item.get("name") or "").strip(), number))
    return tuple(kept), frozenset(disabled)


def enabled_phones(phones: object, *, contact_ref: str = "") -> tuple[tuple[str, str], ...]:
    """``(source label, number)`` for every enabled entry with digits, in source order."""
    return read_phones(phones, contact_ref=contact_ref)[0]


def phone_entries(enabled: tuple[tuple[str, str], ...]):
    """One ``CanonicalPhone`` per distinct classified line; the first occurrence keeps its label.

    Two entries are one line only when the classification and the number,
    extension included, both match: one number given as Direct and as Fax
    stays two entries.
    """
    from ..adapters.base import CanonicalPhone

    seen: set[tuple[str, str]] = set()
    kept = []
    for label, number in enabled:
        kind = phone_kind(label)
        token = (kind, phone_identity_key(number))
        if token in seen:
            continue
        seen.add(token)
        kept.append(CanonicalPhone(label=label, number=number, kind=kind))
    return tuple(kept)


def primary_number(enabled: tuple[tuple[str, str], ...], names: tuple[str, ...]) -> str:
    """The first enabled number whose source name is earliest in ``names``."""
    for wanted in names:
        for label, number in enabled:
            if label.lower() == wanted:
                return number
    return ""


def phone_kinds(phones: object) -> tuple[tuple[str, str], ...]:
    """``(mobile|fax|other, number)`` for every enabled phone, first occurrence wins."""
    return tuple((entry.kind, entry.number) for entry in phone_entries(enabled_phones(phones)))

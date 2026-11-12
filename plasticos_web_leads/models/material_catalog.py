"""Live material-master vocabulary for web-lead triage.

Pure: no Odoo import. The caller supplies the active rows. A value is kept
only when its code or name is one of those rows. Seller text is matched on
word boundaries, longest label first and the earliest phrase on a tie.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_SINGLE_FIELDS = {
    "polymer": "polymer",
    "form": "form",
    "material_grade": "material_grade",
    "quality_tier": "quality_tier",
    "color": "color",
    "source_type": "source_type",
    "filler_type": "filler",
    "packaging_type": "packaging",
    "process_type": "process",
}

_SLOT_FIELDS = tuple(_SINGLE_FIELDS.items())


def _prepare(text: object) -> str:
    """Separators become spaces. reuseable and w/ print are the listed words."""
    raw = str(text or "")
    raw = re.sub(r"reuseable", "reusable", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bw\s*/\s*print\b", "printed", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bwith\s+print\b", "printed", raw, flags=re.IGNORECASE)
    raw = re.sub(r"[-/()]", " ", raw)
    return " ".join(raw.split())


@dataclass(frozen=True)
class CatalogEntry:
    code: str
    name: str
    description: str = ""
    full_name: str = ""


def _labels(entry: CatalogEntry, *, include_description: bool) -> tuple[str, ...]:
    named = (
        (entry.code, False),
        (entry.name, True),
        (entry.description if include_description else "", False),
    )
    labels: list[str] = []
    seen: set[str] = set()
    for value, allow_singular in named:
        text = _prepare(value)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            labels.append(text)
        if allow_singular and key.endswith("s") and not key.endswith("ss") and len(text) > 4:
            singular = text[:-1]
            singular_key = singular.casefold()
            if singular and singular_key not in seen:
                seen.add(singular_key)
                labels.append(singular)
    return tuple(labels)


def accept_value(value: object, entries: Sequence[CatalogEntry]) -> str | None:
    """Return the catalog code when a reply is exactly a code or a name."""
    token = _prepare(value).casefold()
    if not token:
        return None
    for entry in entries:
        if not entry.code:
            continue
        for label in _labels(entry, include_description=False):
            if label.casefold() == token:
                return entry.code
    return None


def _hits(text: str | None, entries: Sequence[CatalogEntry]) -> list[tuple[int, int, str]]:
    haystack = _prepare(text)
    found: list[tuple[int, int, int, str]] = []
    for entry in entries:
        if not entry.code:
            continue
        best: tuple[int, int, int] | None = None
        for label in _labels(entry, include_description=True):
            match = re.search(rf"\b{re.escape(label)}\b", haystack, re.IGNORECASE)
            if not match:
                continue
            span = (match.start(), match.end(), len(label))
            if best is None or (-span[2], span[0]) < (-best[2], best[0]):
                best = span
        if best is not None:
            found.append((best[0], best[1], best[2], entry.code))
    kept: list[tuple[int, int, str]] = []
    for start, end, length, code in found:
        covered = any(
            other_length > length and other_start <= start and other_end >= end
            for other_start, other_end, other_length, _other_code in found
        )
        if not covered:
            kept.append((-length, start, code))
    kept.sort()
    return kept


def match_one(text: str | None, entries: Sequence[CatalogEntry]) -> str | None:
    """One code: the longest word-boundary label, then the earliest phrase."""
    hits = _hits(text, entries)
    return hits[0][2] if hits else None


def match_codes(text: str | None, entries: Sequence[CatalogEntry]) -> tuple[str, ...]:
    """Every matching code, earliest and longest first, each code once."""
    seen: set[str] = set()
    codes: list[str] = []
    for _start, _length, code in _hits(text, entries):
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return tuple(codes)


def _best_spans(text: str | None, entries: Sequence[CatalogEntry]) -> list[tuple[int, int, str]]:
    haystack = _prepare(text)
    spans: list[tuple[int, int, str]] = []
    for entry in entries:
        if not entry.code:
            continue
        best: tuple[int, int, int] | None = None
        for label in _labels(entry, include_description=True):
            match = re.search(rf"\b{re.escape(label)}\b", haystack, re.IGNORECASE)
            if not match:
                continue
            if best is None or len(label) > best[2]:
                best = (match.start(), match.end(), len(label))
        if best is not None:
            spans.append((best[0], best[1], entry.code))
    return spans


def split_phrase(text: str | None, catalog: Mapping[str, Sequence[CatalogEntry]]) -> dict[str, Any]:
    """Every slot a phrase names. One word fills one slot, and reusable is a quality tier."""
    reading: dict[str, Any] = {field: match_one(text, catalog.get(kind, ())) for field, kind in _SLOT_FIELDS}
    color_spans = _best_spans(text, catalog.get("color", ()))
    attributes: list[str] = []
    for start, end, code in _best_spans(text, catalog.get("attribute", ())):
        if code.casefold() == "reusable" or code in attributes:
            continue
        if any(
            color_start <= start and color_end >= end and (color_end - color_start) > (end - start)
            for color_start, color_end, _color in color_spans
        ):
            continue
        attributes.append(code)
    form_codes = match_codes(text, catalog.get("form", ()))
    if reading["form"] == "LOOSE" and any(code != "LOOSE" for code in form_codes):
        reading["form"] = next(code for code in form_codes if code != "LOOSE")
        if not reading["packaging_type"]:
            reading["packaging_type"] = accept_value("loose", catalog.get("packaging", ()))
    reading["attributes"] = tuple(attributes)
    return reading


def code_list(entries: Sequence[CatalogEntry]) -> str:
    codes: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.code and entry.code not in seen:
            seen.add(entry.code)
            codes.append(entry.code)
    return ", ".join(codes) if codes else "(none)"


def labeled_list(entries: Sequence[CatalogEntry]) -> str:
    """Prompt text: code, name, and a polymer full name. The full name is not a match label."""
    rows: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not entry.code or entry.code in seen:
            continue
        seen.add(entry.code)
        label = f"{entry.code} — {entry.name or entry.code}"
        if entry.full_name:
            label = f"{label} — {entry.full_name}"
        rows.append(label)
    return "; ".join(rows) if rows else "(none)"


def restrict_to_catalog(raw: Mapping[str, Any], catalog: Mapping[str, Sequence[CatalogEntry]]) -> dict[str, Any]:
    """Drop any material code the catalog does not list. Other fields stay as validated."""
    out = dict(raw)
    for field, kind in _SINGLE_FIELDS.items():
        if field in out:
            out[field] = accept_value(out.get(field), catalog.get(kind, ()))
    if "attributes" in out:
        attributes = out.get("attributes")
        if isinstance(attributes, (list, tuple)):
            text = " ".join(str(item) for item in attributes)
        else:
            text = str(attributes or "")
        out["attributes"] = [
            code for code in match_codes(text, catalog.get("attribute", ())) if code.casefold() != "reusable"
        ]
    return out

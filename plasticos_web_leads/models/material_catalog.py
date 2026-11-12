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
    "color": "color",
    "source_type": "source_type",
    "filler_type": "filler",
    "packaging_type": "packaging",
    "process_type": "process",
}


@dataclass(frozen=True)
class CatalogEntry:
    code: str
    name: str
    description: str = ""


def _labels(entry: CatalogEntry, *, include_description: bool) -> tuple[str, ...]:
    raw = (entry.code, entry.name, entry.description if include_description else "")
    labels: list[str] = []
    seen: set[str] = set()
    for value in raw:
        text = " ".join(str(value or "").split())
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            labels.append(text)
    return tuple(labels)


def accept_value(value: object, entries: Sequence[CatalogEntry]) -> str | None:
    """Return the catalog code when a reply is exactly a code or a name."""
    token = " ".join(str(value or "").split()).casefold()
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
    haystack = str(text or "")
    found: list[tuple[int, int, str]] = []
    for entry in entries:
        if not entry.code:
            continue
        best: tuple[int, int] | None = None
        for label in _labels(entry, include_description=True):
            match = re.search(rf"\b{re.escape(label)}\b", haystack, re.IGNORECASE)
            if not match:
                continue
            rank = (-len(label), match.start())
            if best is None or rank < best:
                best = rank
        if best is not None:
            found.append((best[0], best[1], entry.code))
    found.sort()
    return found


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


def code_list(entries: Sequence[CatalogEntry]) -> str:
    codes: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.code and entry.code not in seen:
            seen.add(entry.code)
            codes.append(entry.code)
    return ", ".join(codes) if codes else "(none)"


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
        out["attributes"] = list(match_codes(text, catalog.get("attribute", ())))
    return out

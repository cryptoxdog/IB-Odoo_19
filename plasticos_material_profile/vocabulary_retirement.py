"""Retire REPRO and LOOSE as forms, and spell Supersacs one way.

ADR-134 §6. REPRO becomes Pellets plus the Repro attribute only when the
description or the ERP product line says pellets. Every other REPRO profile
stays on the review list. LOOSE becomes packaging Loose. The sheet aliases
resolve to the SUPERACS grade.
"""

from __future__ import annotations

import re

PELLET_WORD = re.compile(r"\bpellets?\b|\bpelletized\b", re.IGNORECASE)
RETIRED_FORMS = ("REPRO", "LOOSE")
SUPERSAC_ALIASES = ("superacs", "supersacks", "super sacks", "super sacs", "supersac")
REPRO_ATTRIBUTE = "repro"
LOOSE_PACKAGING = "loose"
PELLETS_FORM = "PELLETS"


def confirms_pellets(*texts: str | None) -> bool:
    """True when one of the texts names pellets as a word."""
    return any(PELLET_WORD.search(text or "") for text in texts)


def plan_repro(rows: list[dict], repro_form_id, texts_by_id: dict) -> tuple[list, list]:
    """Split REPRO profiles into pellets conversions and the review list.

    ``texts_by_id`` maps a profile id to the description and ERP product lines.
    A profile that is not on the REPRO form is left out of both lists.
    """
    pellets: list = []
    review: list = []
    for row in rows:
        if repro_form_id is None or row.get("form_id") != repro_form_id:
            continue
        if confirms_pellets(*texts_by_id.get(row["id"], ())):
            pellets.append(row["id"])
        else:
            review.append(row["id"])
    return pellets, review


def plan_loose(rows: list[dict], loose_form_id) -> tuple[list, list]:
    """LOOSE profiles whose form can be cleared, and those blocked by the key.

    Clearing the form can land on a profile that already holds that key. The
    blocked profile keeps its form and is reported. Nothing is deleted.
    """
    if loose_form_id is None:
        return [], []
    by_key: dict[tuple, list] = {}
    for row in rows:
        key = _profile_key(row)
        if key is not None:
            by_key.setdefault(key, []).append(row["id"])
    clear: list = []
    blocked: list = []
    loose_rows = sorted((row for row in rows if row.get("form_id") == loose_form_id), key=lambda row: row["id"])
    for row in loose_rows:
        target = (
            row.get("partner_id"),
            row.get("polymer_id"),
            None,
            row.get("material_grade_id") or None,
            row.get("direction") or None,
        )
        occupied = by_key.get(target, [])
        if row.get("partner_id") and any(other != row["id"] for other in occupied):
            blocked.append(row["id"])
            continue
        clear.append(row["id"])
        old = _profile_key(row)
        if old is not None and row["id"] in by_key.get(old, []):
            by_key[old] = [other for other in by_key[old] if other != row["id"]]
        if row.get("partner_id"):
            by_key.setdefault(target, []).append(row["id"])
    return clear, blocked


def _profile_key(row: dict) -> tuple | None:
    if not row.get("partner_id"):
        return None
    return (
        row.get("partner_id"),
        row.get("polymer_id"),
        row.get("form_id") or None,
        row.get("material_grade_id") or None,
        row.get("direction") or None,
    )


def retire_sheet_row(row: dict) -> dict:
    """One mapping row. REPRO and LOOSE forms are not emitted. Idempotent."""
    form = (row.get("form") or "").strip()
    if form == "REPRO":
        if confirms_pellets(row.get("source_value"), row.get("match_key")):
            row["form"] = PELLETS_FORM
        else:
            row["form"] = ""
        attributes = [part for part in (row.get("attributes") or "").split() if part]
        if REPRO_ATTRIBUTE not in attributes:
            attributes.append(REPRO_ATTRIBUTE)
        row["attributes"] = " ".join(attributes)
    elif form == "LOOSE":
        row["form"] = ""
        if not (row.get("packaging_type") or "").strip():
            row["packaging_type"] = LOOSE_PACKAGING
    return row


def ensure_supersac_aliases(rows: list[dict], fieldnames: list[str]) -> int:
    """Add a bare alias row for each missing Supersacs spelling. Return how many were added."""
    present = {(row.get("field_role"), (row.get("match_key") or "").casefold()) for row in rows}
    added = 0
    for alias in SUPERSAC_ALIASES:
        if ("material", alias) in present:
            continue
        row = dict.fromkeys(fieldnames, "")
        row.update(
            {
                "field_role": "material",
                "match_key": alias,
                "source_value": alias,
                "sources": "alias",
                "erp_lines": "0",
                "vanillasoft_contacts": "0",
                "status": "mapped",
                "rule": "approved_alias",
                "polymer": "PP",
                "material_grade": "SUPERACS",
            }
        )
        rows.append(row)
        present.add(("material", alias))
        added += 1
    return added

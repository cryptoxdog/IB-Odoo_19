"""Material-profile direction, decided once from the site and the commercial partner.

ADR-134 §5. A pickup address is out and a delivery address is in. When the site
type is not one of those, only a supplier rank is out and only a customer rank
is in. Both ranks, neither rank, and a pick-up/delivery address stay blank.
"""

from __future__ import annotations

PICKUP_TOKENS = ("PICK-UP", "PICK UP", "PICKUP")
SITE_ADDRESS_TYPES = ("delivery", "invoice")
OUT = "out"
IN = "in"


def is_site_shape(*, has_parent: bool, partner_type: str | None, is_company: bool) -> bool:
    """The ADR-131 site shape: an address of a company, before or after conversion."""
    return bool(has_parent) and (partner_type in SITE_ADDRESS_TYPES or bool(is_company))


def direction_for(
    *,
    site: bool,
    partner_type: str | None,
    source_label: str | None,
    company_role: str | None,
    supplier_rank: int,
    customer_rank: int,
) -> str | None:
    """``out``, ``in``, or None when the profile is left blank for a person.

    Ranks are the commercial company's ranks. A pickup label on the site wins
    over both ranks. An invoice address is a mailing address, so the label and
    the role do not decide it.
    """
    supplier = (supplier_rank or 0) > 0
    customer = (customer_rank or 0) > 0
    if site and partner_type != "invoice":
        label = (source_label or "").upper()
        if any(token in label for token in PICKUP_TOKENS):
            return OUT
        if not (supplier and customer):
            if company_role == "supplier":
                return OUT
            if company_role == "buyer":
                return IN
    if supplier and not customer:
        return OUT
    if customer and not supplier:
        return IN
    return None


def identity_key(row: dict) -> tuple | None:
    """The unique key, or None when no partner index covers the row.

    Empty form, grade, and direction are part of the key (NULLS NOT DISTINCT).
    """
    if not row.get("partner_id"):
        return None
    return (
        row["partner_id"],
        row.get("polymer_id"),
        row.get("form_id") or None,
        row.get("material_grade_id") or None,
        row.get("direction") or None,
    )


def collision_groups(rows: list[dict]) -> dict[tuple, list]:
    """Profile ids that share a key. Nothing here is deleted."""
    grouped: dict[tuple, list] = {}
    for row in rows:
        key = identity_key(row)
        if key is None:
            continue
        grouped.setdefault(key, []).append(row["id"])
    return {key: ids for key, ids in grouped.items() if len(ids) > 1}


def blank_direction_ids(rows: list[dict]) -> list:
    """Partner profiles the direction rule leaves blank, in id order."""
    return sorted(row["id"] for row in rows if row.get("partner_id") and not row.get("direction"))

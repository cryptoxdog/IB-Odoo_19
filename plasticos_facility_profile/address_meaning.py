"""Plain-language meaning of a partner address type.

Odoo stores Contact, Invoice, Delivery, and Other. The form shows that stored
value and, beside it, what the value means for this company.
"""

from __future__ import annotations

_PICKUP_TOKENS = ("PICK-UP", "PICK UP", "PICKUP")


def address_type_meaning(
    partner_type: str | None,
    *,
    is_company: bool,
    company_role: str | None,
    source_label: str | None,
) -> str:
    """Meaning shown beside Address Type. Empty when the type needs no gloss."""
    if partner_type == "contact" and is_company:
        return "This record is the company itself."
    if partner_type == "invoice":
        return "Mailing address"
    if partner_type == "other":
        return "Neither a mailing address nor a pickup or ship-to."
    if partner_type != "delivery":
        return ""
    role = company_role or ""
    if role == "supplier":
        return "Pickup address"
    if role == "buyer":
        return "Ship-to address"
    label = (source_label or "").upper()
    if any(token in label for token in _PICKUP_TOKENS):
        return "Pickup address"
    return "Delivery"

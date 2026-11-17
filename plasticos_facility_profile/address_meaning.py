"""What a partner address is, in plain language, and whether it is a site.

A site is an address of a company: it has a parent, and it is either a native
delivery or invoice address, or a company record parented under another company
(the shape ERP sites have until the ADR-131 data phase moves them to native
addresses). Both shapes are sites, so code that asks "is this a site" works
before and after that data change.

The form shows one label per address. Odoo stores Contact, Invoice, Delivery
and Other; where this module knows what the address means for the company, the
form shows that meaning instead of the raw type.
"""

from __future__ import annotations

SITE_ADDRESS_TYPES = ("delivery", "invoice")
# Contact types stored on res.partner.company_type (``site`` is added by this module).
CONTACT_SITE = "site"
CONTACT_COMPANY = "company"
CONTACT_PERSON = "person"
_PICKUP_TOKENS = ("PICK-UP", "PICK UP", "PICKUP")

COMPANY_ITSELF = "This record is the company itself."
PICK_UP_ADDRESS = "Pick-Up Address"
DELIVERY_ADDRESS = "Delivery Address"
PICK_UP_DELIVERY_ADDRESS = "Pick-Up / Delivery Address"
MAILING_ADDRESS = "Mailing Address"
SITE_ADDRESS = "Site Address"
OTHER_ADDRESS = "Neither a mailing address nor a pickup or ship-to."


def is_site(*, has_parent: bool, partner_type: str | None, is_company: bool) -> bool:
    """True for an address of a company, in either shape."""
    return bool(has_parent) and (partner_type in SITE_ADDRESS_TYPES or bool(is_company))


def site_domain() -> list:
    """Search domain equal to :func:`is_site`."""
    return [
        ("parent_id", "!=", False),
        "|",
        ("type", "in", list(SITE_ADDRESS_TYPES)),
        ("is_company", "=", True),
    ]


def contact_type(*, has_parent: bool, partner_type: str | None, is_company: bool) -> str:
    """The stored Contact type: ``site``, ``company`` or ``person``."""
    if is_site(has_parent=has_parent, partner_type=partner_type, is_company=is_company):
        return CONTACT_SITE
    return CONTACT_COMPANY if is_company else CONTACT_PERSON


def contact_type_inverse(company_type: str | None, partner_type: str | None) -> tuple[bool, str | None]:
    """``(is_company, type)`` a chosen Contact type writes back.

    Site clears ``is_company`` and makes the address a Delivery one unless it is
    already Delivery or Invoice. Person clears ``is_company`` and turns a
    Delivery or Invoice address back into a Contact, so the chosen type is the
    one :func:`contact_type` computes next (a choice that does not round-trip
    would be silently replaced).
    """
    if company_type == CONTACT_SITE:
        return False, (partner_type if partner_type in SITE_ADDRESS_TYPES else "delivery")
    if company_type == CONTACT_PERSON:
        return False, ("contact" if partner_type in SITE_ADDRESS_TYPES else partner_type)
    return company_type == CONTACT_COMPANY, partner_type


def address_type_meaning(
    partner_type: str | None,
    *,
    is_company: bool,
    company_role: str | None,
    source_label: str | None,
    site: bool = False,
    buyer_and_supplier: bool = False,
) -> str:
    """The one label shown for an address. Empty when the raw type needs no gloss.

    ``buyer_and_supplier`` is true when the site's company has both a customer
    and a supplier rank: its site is "Pick-Up / Delivery Address" (operator
    2026-11-17). A PICK-UP source label still wins.
    """
    if site:
        if partner_type == "invoice":
            return MAILING_ADDRESS
        label = (source_label or "").upper()
        if any(token in label for token in _PICKUP_TOKENS):
            return PICK_UP_ADDRESS
        if buyer_and_supplier:
            return PICK_UP_DELIVERY_ADDRESS
        role = company_role or ""
        if role == "supplier":
            return PICK_UP_ADDRESS
        if role == "buyer":
            return DELIVERY_ADDRESS
        return SITE_ADDRESS
    if is_company:
        return COMPANY_ITSELF
    if partner_type == "invoice":
        return MAILING_ADDRESS
    if partner_type == "other":
        return OTHER_ADDRESS
    return ""

"""Who each release document is issued to (C1 lane D2, ADR-131).

The sale order is the buyer company's order shipped to the buyer facility; the
purchase order and the transaction name the supplier company. A site, in either
ADR-131 shape, is never the customer or the vendor.

Odoo-free: exercised by pure pytest with stand-in partners. Each partner must
offer ``_plasticos_site_company()`` (``plasticos_intake``).
"""

from __future__ import annotations


class ReleasePartyError(ValueError):
    """A release party has no owning company."""


def release_parties(supplier, buyer_facility) -> dict:
    """Customer, ship-to and vendor for one release.

    ``customer`` is the company that owns ``buyer_facility``, ``ship_to`` is the
    facility itself, and ``vendor`` is the company that owns ``supplier``.
    """
    customer = buyer_facility._plasticos_site_company()
    if not customer:
        raise ReleasePartyError(f"buyer facility {buyer_facility.display_name!r} belongs to no company")
    vendor = supplier._plasticos_site_company()
    if not vendor:
        raise ReleasePartyError(f"supplier {supplier.display_name!r} belongs to no company")
    return {"customer": customer, "ship_to": buyer_facility, "vendor": vendor}

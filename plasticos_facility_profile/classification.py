"""Partner classification on native fields (ADR-131 Decision B).

Pure functions; the models in ``models/res_partner_trade_role.py``,
``models/res_partner_category.py`` and ``models/res_partner_company_type_mirror.py``
delegate to them. No Odoo import, so pure pytest covers them.
"""

from __future__ import annotations

from collections.abc import Iterable

COMPANY_TYPE_GROUP = "Company Type"
STATUS_GROUP = "Status"

# VanillaSoft is the authority for these values (ADR-131).
COMPANY_TYPE_NAMES = (
    "Distribution Center",
    "Commercial Recycler",
    "Pallet Recycler",
    "Compounder",
    "Grinder/Processor",
    "E-Waste",
    "MRF",
    "Manufacturer",
    "Broker",
    "Carrier",
    "Exporter",
    "Toll Processor",
)
STATUS_NAMES = ("Needs Enrichment", "Do Not Contact", "Key Account", "Preferred Carrier")

# Badge values the native ranks decide. Any other company_role value is kept
# only while neither rank is set.
RANK_ROLES = frozenset({"buyer", "supplier", "both"})


def trade_role(customer_rank: int | None, supplier_rank: int | None, current: str | None) -> str | bool:
    """Badge from the commercial partner's native ranks.

    Both ranks -> ``both`` (never ``broker``). One rank -> ``buyer`` / ``supplier``.
    Neither rank -> the current non-rank value (carrier, broker, internal,
    prospect, other) is kept; a stale rank value is cleared.
    """
    buys = (customer_rank or 0) > 0
    sells = (supplier_rank or 0) > 0
    if buys and sells:
        return "both"
    if buys:
        return "buyer"
    if sells:
        return "supplier"
    if not current or current in RANK_ROLES:
        return False
    return current


def mirrored_tag_ids(child_ids: Iterable[int], company_ids: Iterable[int], group_ids: Iterable[int]) -> set[int]:
    """A site's or person's tags after mirroring its company's Company Type tags.

    Only tags of the Company Type group change; every other tag (ERP Contact
    Role, Status, ...) the child carries is kept as it is.
    """
    group = set(group_ids)
    return (set(child_ids) - group) | (set(company_ids) & group)


def reparent_plan(
    tags: Iterable[tuple[int, str, int | bool | None]],
    group_id: int,
    names: Iterable[str],
) -> tuple[list[int], list[str]]:
    """Which existing tags join the group and which names are still missing.

    ``tags`` are ``(id, name, parent_id)``. A root-level tag whose name is one of
    ``names`` joins the group (lowest id first), unless the group already holds
    that name, so no duplicate is made. Returns ``(ids_to_reparent, missing_names)``
    with ``missing_names`` in the order of ``names``.
    """
    wanted = list(dict.fromkeys(names))
    rows = sorted(tags, key=lambda row: row[0])
    held = {name for _id, name, parent in rows if parent == group_id and name in wanted}
    reparent: list[int] = []
    for tag_id, name, parent in rows:
        if name in wanted and name not in held and not parent:
            reparent.append(tag_id)
            held.add(name)
    missing = [name for name in wanted if name not in held]
    return reparent, missing

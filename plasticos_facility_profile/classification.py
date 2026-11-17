"""Partner classification on native fields (ADR-131 Decision B).

Pure functions; the models in ``models/res_partner_category.py`` and
``models/res_partner_classification.py`` delegate to them. No Odoo import, so
pure pytest covers them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

COMPANY_TYPE_GROUP = "Company Type"
STATUS_GROUP = "Status"
TRADE_ROLE_GROUP = "Trade Role"

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
# VanillaSoft lead status: (external id in this module, tag name). The Status
# group holds these and DNC (``plasticos_base.tag_do_not_contact``), nothing else.
LEAD_STATUS_TAGS = (
    ("status_current", "Current"),  # VanillaSoft 1, Currently Working With
    ("status_open", "Open"),  # VanillaSoft 2
    ("status_hot", "Hot"),  # VanillaSoft 2a
    ("status_warm", "Warm"),  # VanillaSoft 2b
    ("status_cold", "Cold"),  # VanillaSoft 2c
    ("status_resist", "Resist"),  # VanillaSoft 3
    ("status_unqualified", "Unqualified"),  # VanillaSoft 4
)
DNC = "DNC"
STATUS_NAMES = (*(name for _xmlid, name in LEAD_STATUS_TAGS), DNC)
BUYER = "Buyer"
SUPPLIER = "Supplier"
TRADE_ROLE_NAMES = (BUYER, SUPPLIER)


def trade_role_names(customer_rank: int | None, supplier_rank: int | None) -> set[str]:
    """Trade Role tags the native ranks mean: Buyer, Supplier, or both tags."""
    names = set()
    if (customer_rank or 0) > 0:
        names.add(BUYER)
    if (supplier_rank or 0) > 0:
        names.add(SUPPLIER)
    return names


def synced_trade_tag_ids(
    current_ids: Iterable[int],
    member_ids_by_name: Mapping[str, int],
    customer_rank: int | None,
    supplier_rank: int | None,
) -> set[int]:
    """A company's tags with its Trade Role tags set from its ranks.

    The ranks are the source of truth: a Trade Role tag the ranks do not mean is
    removed, one they mean is added. Every other tag is kept. A name with no
    tag in the group yet is skipped.
    """
    members = set(member_ids_by_name.values())
    wanted = {
        member_ids_by_name[name]
        for name in trade_role_names(customer_rank, supplier_rank)
        if name in member_ids_by_name
    }
    return (set(current_ids) - members) | wanted


def mirrored_tag_ids(child_ids: Iterable[int], company_ids: Iterable[int], group_ids: Iterable[int]) -> set[int]:
    """A child's tags after mirroring one tag group from its company.

    Only tags of that group change; every other tag the child carries (ERP
    Contact Role, Status, ...) is kept as it is.
    """
    group = set(group_ids)
    return (set(child_ids) - group) | (set(company_ids) & group)


def newly_tagged(before: Iterable[int], after: Iterable[int], tag_id: int) -> bool:
    """True when ``tag_id`` is on the record after a write and was not before."""
    return tag_id in set(after) and tag_id not in set(before)


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


def bind_plan(
    tags: Iterable[tuple[int, str, int | bool | None]],
    group_id: int,
    bound_xmlids: Iterable[str],
    pairs: Iterable[tuple[str, str]],
) -> list[tuple[str, int]]:
    """Existing tags that become the given external ids, so none is duplicated.

    ``tags`` are ``(id, name, parent_id)``; ``pairs`` are ``(xmlid, name)``. For an
    xmlid not bound yet, a same-name tag already in the group is taken first,
    else the oldest same-name root tag. A tag is bound to one xmlid at most.
    Returns ``[(xmlid, tag_id)]``; a name with no candidate is left for the data
    record to create.
    """
    bound = set(bound_xmlids)
    rows = sorted(tags, key=lambda row: (row[2] != group_id, row[0]))
    used: set[int] = set()
    plan: list[tuple[str, int]] = []
    for xmlid, name in pairs:
        if xmlid in bound:
            continue
        for tag_id, tag_name, parent in rows:
            if tag_name == name and tag_id not in used and (not parent or parent == group_id):
                plan.append((xmlid, tag_id))
                used.add(tag_id)
                break
    return plan

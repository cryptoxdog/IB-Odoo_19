"""When a VanillaSoft record becomes a partner, and how its Company Type is read.

Pure functions (no Odoo import), so pure pytest covers the operator rules.
The orchestrator applies them; see ``SyncOrchestrator._resolve_vanillasoft_partner``.

Operator decisions D32/D33 (C1 lane C4):

* A record whose Buyer/Supplier field names **Buyer** becomes a partner at
  every Lead Status except 2c COLD, 5 Dead Lead, 6 Wrong #, 7 Do Not Call and
  8 Duplicate.
* A **Supplier-only or unspecified** record becomes a partner only at 2a HOT,
  2b WARM, 3 Resist, or when the contact is already approved (crosswalk).
* Every other record stays a CRM lead only.
* **7 Do Not Call** never creates a partner. When the company already exists
  as a partner, it gets the DNC status tag and the lead's email and phones are
  blacklisted.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .approved_identity import comment_blocks

STATUS_HOT = "2a=Qualified/HOT"
STATUS_WARM = "2b=Qualified/WARM"
STATUS_RESIST = "3=Qualified/Resist"
STATUS_COLD = "2c=Qualified/COLD"
STATUS_DEAD = "5=Dead Lead"
STATUS_WRONG_NUMBER = "6=Wrong #"
STATUS_DO_NOT_CALL = "7=Do Not Call"
STATUS_DUPLICATE = "8=Duplicate"

# A Buyer becomes a partner at every status except these.
BUYER_EXCLUDED_STATUSES = frozenset(
    {STATUS_COLD, STATUS_DEAD, STATUS_WRONG_NUMBER, STATUS_DO_NOT_CALL, STATUS_DUPLICATE}
)
# A Supplier-only or unspecified record becomes a partner only at these (or when approved).
SUPPLIER_QUALIFIED_STATUSES = frozenset({STATUS_HOT, STATUS_WARM, STATUS_RESIST})

ROLE_BUYER = "Buyer"
ROLE_SUPPLIER = "Supplier"

# Gate reads Company Roles until it moves to ranks (C1 F1+C4, CTO directive).
COMPANY_ROLE_TAG_XMLIDS = {
    ROLE_BUYER: "plasticos_facility_profile.company_role_buyer",
    ROLE_SUPPLIER: "plasticos_facility_profile.company_role_supplier",
}

_ROLE_WORDS = {"buyer": ROLE_BUYER, "supplier": ROLE_SUPPLIER}
_COMPANY_TYPE_PARAGRAPH = re.compile(r"^VanillaSoft (?:ContactID \S+ )?Company Type: (.+)$")
_NAME_SUFFIXES = frozenset(
    {"inc", "incorporated", "llc", "co", "corp", "corporation", "company", "ltd", "limited", "lp", "llp"}
)


def _squash(value: str | None) -> str:
    return " ".join(str(value or "").split())


def parse_roles(raw: str | None) -> frozenset[str]:
    """The Buyer/Supplier roles a source value names. Unknown words are ignored."""
    words = re.split(r"[,;\n/&]+|\band\b", _squash(raw), flags=re.IGNORECASE)
    return frozenset(_ROLE_WORDS[word.strip().casefold()] for word in words if word.strip().casefold() in _ROLE_WORDS)


def partner_allowed(status: str | None, roles: Iterable[str], *, approved: bool) -> bool:
    """True when this record becomes (or links to) a partner under D32/D33."""
    status = _squash(status)
    if status == STATUS_DO_NOT_CALL:
        return False
    if ROLE_BUYER in set(roles):
        return status not in BUYER_EXCLUDED_STATUSES
    return approved or status in SUPPLIER_QUALIFIED_STATUSES


def is_do_not_call(status: str | None) -> bool:
    return _squash(status) == STATUS_DO_NOT_CALL


def trade_ranks(roles: Iterable[str]) -> dict[str, int]:
    """``customer_rank`` / ``supplier_rank`` floors the roles mean. A role never lowers a rank."""
    roles = set(roles)
    ranks = {}
    if ROLE_BUYER in roles:
        ranks["customer_rank"] = 1
    if ROLE_SUPPLIER in roles:
        ranks["supplier_rank"] = 1
    return ranks


def company_type_from_text(html: str | None) -> str:
    """The VanillaSoft Company Type recorded in a lead description or person comment.

    The importer writes ``VanillaSoft Company Type: X`` on a lead and
    ``VanillaSoft ContactID n Company Type: X`` on an approved person. The last
    recorded value wins. Empty when none is recorded.
    """
    found = ""
    for block in comment_blocks(html):
        match = _COMPANY_TYPE_PARAGRAPH.match(block)
        if match:
            found = _squash(match.group(1))
    return found


def normalized_company_name(name: str | None) -> str:
    """Company name for duplicate matching: case, punctuation and legal suffixes ignored."""
    text = re.sub(r"&", " and ", _squash(name).casefold())
    # "L.L.C." and "Inc." lose their dots so the suffix is one word.
    text = re.sub(r"\b(\w)\.(?=\w\.)", r"\1", text).replace(".", " ")
    words = re.sub(r"[^\w\s]", " ", text).split()
    while len(words) > 1 and words[-1] in _NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def pick_existing(erp_matches: Iterable[int], other_matches: Iterable[int]) -> tuple[int | None, str]:
    """The one partner a record links to, ERP partners first. ``(None, reason)`` refuses to guess.

    ``("", None)`` with no reason means no partner exists and one may be created.
    """
    erp = sorted(set(erp_matches))
    if len(erp) == 1:
        return erp[0], ""
    if len(erp) > 1:
        return None, "BLOCKED_PARTNER_AMBIGUOUS: several ERP companies match"
    other = sorted(set(other_matches))
    if len(other) == 1:
        return other[0], ""
    if len(other) > 1:
        return None, "BLOCKED_PARTNER_AMBIGUOUS: several companies match"
    return None, ""


def backfill_company_type_tags(leads, tag_for, link) -> dict[str, int]:
    """Put the recorded Company Type on each lead as its CRM tag. Idempotent.

    ``leads`` yields objects with ``description`` and ``tag_ids`` (ids);
    ``tag_for(canonical_name)`` returns the tag id or ``None``;
    ``link(lead, tag_id)`` adds the tag. Returns counts: ``set``,
    ``already_set``, ``no_source_value`` and ``unmapped`` (a recorded value with
    no Company Type tag).
    """
    counts = {"set": 0, "already_set": 0, "no_source_value": 0, "unmapped": 0}
    for lead in leads:
        value = company_type_from_text(getattr(lead, "description", ""))
        if not value:
            counts["no_source_value"] += 1
            continue
        tag_id = tag_for(value)
        if not tag_id:
            counts["unmapped"] += 1
            continue
        if tag_id in set(lead.tag_ids):
            counts["already_set"] += 1
            continue
        link(lead, tag_id)
        counts["set"] += 1
    return counts

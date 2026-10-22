"""Locked VanillaSoft owner email → Odoo user login.

The operator workbook ``OWNER CROSSWALK`` is the decision record. Tiffany's
destination login is ``sa@scrapmanagement.com``. ``tw@scrapmanagement.com`` is
the stale seed and is not a target. A blank owner falls back to Mack.
"""

from __future__ import annotations

import csv

BLANK_OWNER_LOGIN = "sales2@scrapmanagement.com"
SALESMAN_GROUP_XMLID = "sales_team.group_sale_salesman"

# Source email, destination login. Built below so the table is not a short-key
# dispatch dict (those are scanned as selection values).
_OWNER_ROWS = (
    ("ibeylin@ucsincny.com", "ib@scrapmanagement.com"),
    ("sales2@scrapmanagement.com", "sales2@scrapmanagement.com"),
    ("ss@scrapmanagement.com", "sales2@scrapmanagement.com"),
    ("aakopyan@ucsincny.com", "aa@scrapmanagement.com"),
    ("rpereira@ucsincny.com", "rp@scrapmanagement.com"),
    ("ab@ucsincny.com", "ab@scrapmanagement.com"),
    ("sa@scrapmanagement.com", "sa@scrapmanagement.com"),
    ("va@scrapmanagement.com", "sales2@scrapmanagement.com"),
    ("lm@ucsincny.com", "lm@scrapmanagement.com"),
    ("sales5@scrapmanagement.com", "sales2@scrapmanagement.com"),
    ("nc@scrapmanagement.com", "sales2@scrapmanagement.com"),
)

OWNER_LOGIN_BY_SOURCE = {source.casefold(): login for source, login in _OWNER_ROWS}

_BLANK_TOKENS = frozenset({"", "false", "[blank / no owner]"})


class OwnerResolutionError(Exception):
    """The owner did not resolve to exactly one eligible Odoo user."""


def target_login(owner_raw: str | None) -> str:
    """Return the Odoo login for a VanillaSoft owner value.

    Empty, ``false``, and the workbook's blank label use Mack's login.
    """
    token = " ".join(str(owner_raw or "").split()).casefold()
    if token in _BLANK_TOKENS:
        return BLANK_OWNER_LOGIN
    login = OWNER_LOGIN_BY_SOURCE.get(token)
    if not login:
        raise OwnerResolutionError(f"VanillaSoft owner {owner_raw!r} is not in the locked owner map")
    return login


def resolve_salesperson(env, owner_raw: str | None):
    """Return the one active internal salesperson allowed to own CRM leads."""
    login = target_login(owner_raw)
    users = env["res.users"].search([("login", "=ilike", login)])
    eligible = users.filtered(lambda user: user.active and not user.share and user.has_group(SALESMAN_GROUP_XMLID))
    if len(eligible) != 1:
        raise OwnerResolutionError(
            f"VanillaSoft owner {owner_raw!r} resolves to {login} but matched {len(eligible)} eligible users"
        )
    return eligible


def owner_pairs_from_csv(path: str) -> dict[str, str]:
    """Read ``ContactID`` → ``Contact Owner`` from a VanillaSoft lead export."""
    pairs: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "ContactID" not in reader.fieldnames or "Contact Owner" not in reader.fieldnames:
            raise OwnerResolutionError(f"{path} is missing ContactID or Contact Owner")
        for row in reader:
            external_id = (row.get("ContactID") or "").strip()
            if external_id:
                pairs[external_id] = row.get("Contact Owner") or ""
    return pairs

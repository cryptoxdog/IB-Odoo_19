"""Source-value normalization and ERP -> PlasticOS vocabulary maps.

Odoo-free on purpose: every rule here is exercised by the pure-Python CI tier
against the real payload, so a vocabulary drift in a future extract fails a test
rather than silently coercing to a default.

Two hard rules govern this module:

* **No silent coercion.** An unmapped source code returns ``None`` together with
  an anomaly string. The importer records it; it does not guess. (The retired
  CSV service defaulted unknown weight UOMs to ``"L"`` — that is exactly the
  behaviour these functions replace.)
* **Existing fields first.** Every target named here already exists on
  ``res.partner`` or on the deal header and line models. This import adds no
  field to any model.
"""

from __future__ import annotations

import re
from datetime import datetime

__all__ = [
    "ADDRESS_TYPE_KIND",
    "INTERNAL_MAILBOX_DOMAINS",
    "ODOO_ADDRESS_TYPE",
    "PRIMARY_CONTACT_ROLE",
    "COMPANY_ROLE_BY_ERP_ROLE",
    "SALES_REP_LOGINS",
    "SALES_REP_NAMES",
    "SALES_REP_REASSIGNED",
    "UNIT_TYPE_MAP",
    "WEIGHT_UOM",
    "address_kind",
    "company_role",
    "external_emails",
    "sales_rep_code",
    "is_kind_only_label",
    "mailbox_key",
    "site_mailbox_keys",
    "site_mailbox_target",
    "normalize_contact_role",
    "sort_contact_roles",
    "parse_bool",
    "parse_date",
    "parse_decimal",
    "trade_ranks",
    "unit_type",
    "weight_uom",
]

# ---------------------------------------------------------------------------
# CounterParty.Role -> res.partner.company_role
# ---------------------------------------------------------------------------
# Semantics proven by behaviour on the tracked payload rather than by letter:
# every counterparty was cross-referenced against the material-supplier set
# (Payables with no delivery leg), the buyer set (ReceiptBatch.CPID), and the
# freight set (WksDelivery.VendorID).
#
#   V  543  material supplier 330, buyer 0            -> supplier
#   S  137  material supplier  61, buyer 0            -> supplier
#   D  160  freight/delivery only, never material     -> carrier
#   X  111  buyer 70, material supplier 0             -> buyer
#   C   30  buyer 16, material supplier 0             -> buyer
#   A  262  supplier 173, buyer 176, freight 175      -> broker (dual-sided)
#   P   47  supplier  29, buyer  28, freight  24      -> broker (dual-sided)
#
# ``A``/``P`` trade on both sides, which single-valued ``company_role`` cannot
# express; ``broker`` is the existing selection member for a dual-sided
# counterparty. The multi-role truth is carried by Odoo's native
# ``supplier_rank`` / ``customer_rank`` (see :func:`trade_ranks`), which is the
# repository's designated mechanism for this (CLAUDE.md, "Partner Hierarchy").
COMPANY_ROLE_BY_ERP_ROLE: dict[str, str] = {
    "V": "supplier",
    "S": "supplier",
    "D": "carrier",
    "X": "buyer",
    "C": "buyer",
    "A": "broker",
    "P": "broker",
}

# supplier_rank / customer_rank seeded from the same evidence.
_RANKS_BY_ROLE: dict[str, tuple[int, int]] = {
    "V": (1, 0),
    "S": (1, 0),
    "D": (0, 0),
    "X": (0, 1),
    "C": (0, 1),
    "A": (1, 1),
    "P": (1, 1),
}

# ---------------------------------------------------------------------------
# Address.Type -> address kind
# ---------------------------------------------------------------------------
# ``Address.Type`` is free text (the payload contains city names such as
# "OMAHA, NE" used as a label). PRIMARY is the company's mailing address.
# A place name is a delivery site. The raw label stays on the partner.
ADDRESS_TYPE_KIND: dict[str, str] = {
    "INVOICE": "invoice",
    "REMIT": "invoice",
    "PRIMARY": "invoice",
    "PRIMARY ADDRESS": "invoice",
    "DELIVERY ADDRESS": "delivery",
    "PICK UP ADDRESS": "delivery",
    "PICK-UP ADDRESS": "delivery",
    "PICK UP LOCATION": "delivery",
    "WAREHOUSE": "delivery",
}

# Internal address kind -> Odoo's native ``res.partner.type`` selection.
ODOO_ADDRESS_TYPE: dict[str, str] = {
    "invoice": "invoice",
    "delivery": "delivery",
    "primary": "invoice",
    "other": "delivery",
}

# ---------------------------------------------------------------------------
# ContactRoleAssignment.RoleNm
# ---------------------------------------------------------------------------
# The ERP role naming the main contact for a counterparty. It is the most
# common value in the payload (1680 of 3091 assignments). Job Position is one
# value: Decision Maker wins, otherwise a single other tag is written.
PRIMARY_CONTACT_ROLE = "Primary"

# ---------------------------------------------------------------------------
# WKSDetail UOM / unit type selections
# ---------------------------------------------------------------------------
# ``weight_uom`` selection is exactly L / S / E.
WEIGHT_UOM: frozenset[str] = frozenset({"L", "S", "E"})

# ``unit_type`` selection members, plus the source numeric code the model's own
# import path already recognises.
_UNIT_TYPES: frozenset[str] = frozenset({"B", "G", "X", "P", "L", "A", "F", "H", "C", "E", "O"})
UNIT_TYPE_MAP: dict[str, str] = {"9": "O"}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def parse_decimal(value: str | None) -> float | None:
    """Exact numeric parse. A non-numeric value is an anomaly, not a zero.

    The retired CSV service stripped every non-numeric character and returned
    ``0.0`` on failure, which turned malformed money into silent zero. This
    returns ``None`` so the caller can record the row instead.
    """
    raw = _clean(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_bool(value: str | None) -> bool | None:
    """Parse the payload's boolean spellings (``Y``/``N``, ``1``/``0``)."""
    raw = _clean(value).upper()
    if raw in {"Y", "1", "TRUE"}:
        return True
    if raw in {"N", "0", "FALSE"}:
        return False
    return None


def explicitly_active_contact(value: str | None) -> bool:
    """A contact row is eligible only when ``IsActive`` is an explicit true spelling.

    Blank and unknown spellings parse as ``None``. ``None`` is not active.
    """
    return parse_bool(value) is True


def eligible_contact_rows(members: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Keep rows whose ``IsActive`` is explicitly true. Inactive aliases are dropped."""
    return [(contact_id, row) for contact_id, row in members if explicitly_active_contact(row.get("IsActive"))]


def parse_date(value: str | None) -> datetime | None:
    """Parse an exported SQL Server datetime; unknown shapes yield ``None``."""
    raw = _clean(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def company_role(raw_role: str | None) -> tuple[str | None, str | None]:
    """``CounterParty.Role`` -> ``res.partner.company_role``.

    Returns ``(role, anomaly)``. An unknown code maps to nothing and is
    reported, so a new ERP role code surfaces instead of being absorbed.
    """
    code = _clean(raw_role).upper()
    if not code:
        return None, "blank CounterParty.Role"
    mapped = COMPANY_ROLE_BY_ERP_ROLE.get(code)
    if mapped is None:
        return None, f"unmapped CounterParty.Role {code!r}"
    return mapped, None


def trade_ranks(raw_role: str | None) -> tuple[int, int]:
    """``CounterParty.Role`` -> native ``(supplier_rank, customer_rank)``."""
    return _RANKS_BY_ROLE.get(_clean(raw_role).upper(), (0, 0))


_KIND_BASES = ("INVOICE", "REMIT", "PRIMARY", "PICKUP", "DELIVERY", "WAREHOUSE")
_ROLE_MAILBOX_WORDS = frozenset({"PRIMARY", "INVOICE"})


def _alnum(value: str | None) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def is_kind_only_label(label: str | None) -> bool:
    """True when an ERP Type is only a kind word, not a place name.

    ``INVOICE``, ``PRIMARY``, ``PICK UP LOCATION``, and ``DELIVERY ADDRESS`` are kind words.
    ``LINCOLN, IL`` and ``HOUSTON TX - PICK UP`` are place names.
    """
    key = _alnum(label)
    if not key:
        return False
    return any(key in {base, base + "ADDRESS", base + "LOCATION"} for base in _KIND_BASES)


def mailbox_key(name: str | None) -> str | None:
    """Identity of a site mailbox. A person's name, or a role word, is not one.

    A name with a space is a person. A name shorter than four characters is a
    person, so ``AR`` is not treated as a mailbox just because those letters
    occur inside ``PRIMARY ADDRESS``. ``PRIMARY`` and ``INVOICE`` stay people.
    """
    raw = (name or "").strip()
    if not raw or " " in raw:
        return None
    key = _alnum(raw)
    if len(key) < 4 or key in _ROLE_MAILBOX_WORDS:
        return None
    return key


def site_mailbox_keys(companies: list[tuple[list[str], list[str]]]) -> set[str]:
    """No-space names that occur inside an address Type for the same company.

    ``companies`` is ``(contact names, address types)`` per counterparty. A key
    found for one company is a mailbox everywhere that name appears.
    """
    found: set[str] = set()
    for names, labels in companies:
        folded = [_alnum(label) for label in labels]
        for name in names:
            key = mailbox_key(name)
            if key and any(key in label for label in folded):
                found.add(key)
    return found


def site_mailbox_target(
    name: str | None,
    addresses: list[tuple[str, str]],
    location: str | None,
    known_keys: set[str],
) -> str | None:
    """Address id that should carry this mailbox, or ``None`` when it is a person.

    Prefer the address whose Type contains the name. Otherwise use the address
    whose Type is the contact's Location, when that Type is a place and not a
    kind word.
    """
    key = mailbox_key(name)
    if not key or key not in known_keys:
        return None
    for address_id, label in addresses:
        if key in _alnum(label):
            return address_id
    loc = _alnum(location)
    if not loc:
        return None
    for address_id, label in addresses:
        if _alnum(label) == loc and not is_kind_only_label(label):
            return address_id
    return None


def address_kind(row) -> str:
    """Resolve an address to its operational kind.

    ``Address.Type`` is free text (the payload uses city names such as
    "OMAHA, NE" as labels), so the billing flags carry signal the label does
    not: 289 addresses are flagged ``InvoiceAddr='Y'`` without an invoice-like
    ``Type``, and 88 more carry ``RemitToAddress=1``. Any of the three makes an
    address a billing address, which is what the invoice/remit/billing mapping
    requirement asks for.

    PRIMARY and PRIMARY ADDRESS are the mailing address. An unrecognised place
    name is a delivery site. The raw text is preserved as the partner name.
    """
    label = _clean(row.get("Type")).upper()
    labelled = ADDRESS_TYPE_KIND.get(label)
    if labelled == "invoice":
        return "invoice"
    if parse_bool(row.get("InvoiceAddr")) or parse_bool(row.get("RemitToAddress")):
        return "invoice"
    if parse_bool(row.get("isBillingAddressOnly")):
        return "invoice"
    if labelled:
        return labelled
    return "delivery"


def weight_uom(sale_uom: str | None, purchase_uom: str | None) -> tuple[str | None, str | None]:
    """Resolve the single shared ``weight_uom`` for a transaction line.

    The shared field is the intended model (locked business decision), so:

    * both sides agree -> that code;
    * exactly one side populated -> the populated code;
    * both populated and different -> ``None`` plus an anomaly, per the locked
      rule that a genuine mismatch is a source-data anomaly to investigate and
      never a reason to widen the schema.

    A code outside the ``L``/``S``/``E`` selection is likewise reported, never
    silently defaulted.
    """
    sale = _clean(sale_uom).upper()
    purchase = _clean(purchase_uom).upper()

    if sale and purchase and sale != purchase:
        return None, f"weight UOM mismatch: SWeightUOM={sale!r} PWeightUOM={purchase!r}"

    code = sale or purchase
    if not code:
        return None, "no weight UOM on either side"
    if code not in WEIGHT_UOM:
        return None, f"unmapped weight UOM {code!r}"
    return code, None


def unit_type(raw_unit_type: str | None) -> tuple[str | None, str | None]:
    """``WKSDetail.UnitType`` -> the ``unit_type`` selection."""
    code = _clean(raw_unit_type).upper()
    if not code:
        return None, None
    code = UNIT_TYPE_MAP.get(code, code)
    if code not in _UNIT_TYPES:
        return None, f"unmapped UnitType {code!r}"
    return code, None


# ERP role words that mean the same job collapse to one tag.
# ``RR`` is not in this map: it stays unresolved.
CONTACT_ROLE_TAGS: dict[str, str] = {
    "primary": "Decision Maker",
    "dm": "Decision Maker",
    "pricing": "Decision Maker",
    "owner": "Decision Maker",
    "collections": "AR/AP",
    "ar/ap": "AR/AP",
    "billing": "AR/AP",
    "ship / del appt": "Logistics",
    "freight": "Logistics",
    "admin:pics/docs": "Admin",
    "operations mgr": "Operations Manager",
    "sales": "Sales",
    "dm assistant": "Assistant",
}


def normalize_contact_role(raw_role: str | None) -> str:
    """Normalize ``ContactRoleAssignment.RoleNm`` for deterministic tag keys."""
    return " ".join(_clean(raw_role).split())


def map_contact_role(raw_role: str | None) -> tuple[str | None, str | None]:
    """Map an ERP role word onto one tag.

    Returns ``(tag, None)`` when the word is known. ``RR`` returns
    ``(None, "rr")`` and is not guessed. Anything else returns
    ``(None, "unmapped")``.
    """
    key = normalize_contact_role(raw_role).casefold()
    if not key:
        return None, "blank"
    if key == "rr":
        return None, "rr"
    tag = CONTACT_ROLE_TAGS.get(key)
    if not tag:
        return None, "unmapped"
    return tag, None


# SalesReps.ReferrerNo initials -> the existing res.users login written to
# res.partner.user_id. The mailbox is the match. Display names are not:
# AA and AB are both Arthur, and TF's mailbox is sa@, not tf@.
# MM and DAVE are Mack's account. LR is Lindsey; the mailbox prefix is lm.
SALES_REP_LOGINS: dict[str, str] = {
    "IB": "ib@scrapmanagement.com",
    "AA": "aa@scrapmanagement.com",
    "RP": "rp@scrapmanagement.com",
    "AB": "ab@scrapmanagement.com",
    "TF": "sa@scrapmanagement.com",
    "MM": "sales2@scrapmanagement.com",
    "LR": "lm@scrapmanagement.com",
    "DAVE": "sales2@scrapmanagement.com",
}

# Worksheet commission still names the historical recipient. That lookup is
# the display name, and it does not apply the partner-ownership logins above.
SALES_REP_NAMES: dict[str, str] = {
    "IB": "Igor Beylin",
    "AA": "Arthur Akopyan",
    "RP": "Ricardo Pereira",
    "AB": "Arthur Buyanovskiy",
    "TF": "Tiffany White",
    "MM": "Mack McMurray",
    "LR": "Lindsey Malyavko",
    "DAVE": "David McLawhorn",
}

# Former representatives whose accounts the brokerage reassigned to MM.
# The restored database may still carry the former initials on those rows.
# The reassignment is this mapping rule, not an edit of the source.
# Contract: docs/adr/ADR-021-erp-sql-crm-api-import.md.
SALES_REP_REASSIGNED: dict[str, str] = {
    "JB": "MM",
    "YK": "MM",
    "WC": "MM",
    "RF": "MM",
    "GS": "MM",
    "AK": "MM",
    "IG": "MM",
}


def sales_rep_code(code: str | None) -> str:
    """Current rep initials for a source ``ReferrerNo``: trimmed, upper-cased, reassigned."""
    key = _clean(code).upper()
    return SALES_REP_REASSIGNED.get(key, key)


def default_sales_rep(rows) -> tuple[str | None, str | None]:
    """The rep initials that set one company's Salesperson.

    A unique ``IsDefault=1`` row wins, including when other reps are also
    present. When the source marks none as default, the sole assigned rep is
    the Salesperson: an ``IsDefault=0`` row is still an assignment. Two
    different defaults, or several assigned reps and no default, return
    ``(None, reason)`` and set nobody.
    """
    defaults = _sales_rep_codes(rows, default_only=True)
    if len(defaults) > 1:
        return None, f"more than one default rep: {', '.join(defaults)}"
    if len(defaults) == 1:
        return defaults[0], None
    assigned = _sales_rep_codes(rows, default_only=False)
    if len(assigned) > 1:
        return None, f"more than one rep and no default: {', '.join(assigned)}"
    if not assigned:
        return None, None
    return assigned[0], None


def _sales_rep_codes(rows, *, default_only: bool) -> list[str]:
    selected = rows
    if default_only:
        selected = [row for row in rows if _clean(row.get("IsDefault")) == "1"]
    return sorted({sales_rep_code(row.get("ReferrerNo")) for row in selected} - {""})


def sales_rep_login(code: str | None) -> str | None:
    """Odoo user login for rep initials, or ``None`` for unknown initials.

    Former initials are reassigned first, so a live ``JB`` row is Mack's login.
    """
    return SALES_REP_LOGINS.get(sales_rep_code(code))


def sales_rep_name(code: str | None) -> str | None:
    """Display name for rep initials. Worksheet history uses this, not the login."""
    return SALES_REP_NAMES.get(sales_rep_code(code))


# The brokerage's own staff mailboxes. The ERP keeps them as CC recipients on
# counterparty address and contact rows; they are not the counterparty's
# channel and are never written to a partner. The source row is left as is.
INTERNAL_MAILBOX_DOMAINS: frozenset[str] = frozenset(
    {"scrapmanagement.com", "scrapmanagment.com", "ucsincny.com", "ussmrecycle.com"}
)
_INTERNAL_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@(?:" + "|".join(re.escape(domain) for domain in sorted(INTERNAL_MAILBOX_DOMAINS)) + r")\b",
    re.IGNORECASE,
)
_EMAIL_LIST_SPLIT_RE = re.compile(r"[;,]")


def external_emails(value: str | None) -> str:
    """The source e-mail cell without the brokerage's own mailboxes.

    A cell that names no internal mailbox is returned verbatim. Otherwise the
    ``;`` / ``,`` separated entries that carry an internal address are dropped
    and the rest are re-joined with ``; ``. An empty result is ``""``.
    """
    text = value or ""
    if not _INTERNAL_EMAIL_RE.search(text):
        return text
    kept = [part.strip() for part in _EMAIL_LIST_SPLIT_RE.split(text)]
    return "; ".join(part for part in kept if part and not _INTERNAL_EMAIL_RE.search(part))


def job_position(tags: list[str]) -> str:
    """One Job Position from the tags already mapped for this person.

    Decision Maker wins when that tag is present. Otherwise exactly one other
    tag is written. Two or more other tags stay on the tags and return empty
    so the caller leaves ``function`` unchanged.
    """
    if "Decision Maker" in tags:
        return "Decision Maker"
    others = [tag for tag in tags if tag and tag != "Decision Maker"]
    if len(others) == 1:
        return others[0]
    return ""


def is_person_name(name: str | None) -> bool:
    """A contact title needs a letter. A phone number is not a person."""
    return any(char.isalpha() for char in (name or ""))


def person_key(name: str | None) -> str:
    """Identity of a person within one company.

    The first word and the last word match, without case or punctuation.
    A single word, or a cell that contains ``;`` or ``/``, stays one person
    as written and is not split.
    """
    raw = (name or "").strip()
    folded = _alnum(raw) or raw.casefold()
    if not raw or ";" in raw or "/" in raw:
        return folded
    words = [word for word in raw.split() if word]
    if len(words) < 2:
        return folded
    return f"{_alnum(words[0])}|{_alnum(words[-1])}"


def real_phone(value: str | None) -> str:
    """A dialable number. Blank, the word NULL, and short ids are empty."""
    text = (value or "").strip()
    if not text or text.upper() == "NULL":
        return ""
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) < 7:
        return ""
    return text


def fax_from_notes(notes: str | None) -> str:
    """A ``Fax:`` line in contact notes, when the remainder is a real number."""
    for line in (notes or "").splitlines():
        cleaned = line.strip()
        if cleaned.lower().startswith("fax:"):
            return real_phone(cleaned.split(":", 1)[1])
    return ""


def location_title(
    type_label: str | None,
    city: str | None,
    street: str | None,
    street2: str | None,
    parent_name: str | None,
) -> str:
    """Title of a location. Never the street.

    A place-name Type stays the title. A kind word, a Type that repeats the
    company, or a Type that is itself a street uses the city.
    """
    label = (type_label or "").strip()
    parent = (parent_name or "").strip()
    if (
        label
        and _alnum(label) != _alnum(parent)
        and not is_kind_only_label(label)
        and not _label_is_street(label, street, street2)
    ):
        return label
    place = (city or "").strip()
    if place and place.upper() != "NULL":
        return place
    if parent:
        return parent
    return "Location"


def _label_is_street(label: str, street: str | None, street2: str | None) -> bool:
    folded = _alnum(label)
    for raw in (street, street2):
        road = _alnum(raw)
        if road and len(road) >= 6 and (road == folded or road in folded):
            return True
    return bool(label[:1].isdigit())


def sort_contact_roles(roles: list[str]) -> list[str]:
    """Order a contact's roles deterministically, primary first."""
    primary = PRIMARY_CONTACT_ROLE.lower()
    return sorted(roles, key=lambda role: (role.lower() != primary, role.lower()))

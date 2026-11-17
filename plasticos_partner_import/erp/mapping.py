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
  ``res.partner`` or on the deal header and line models. This module adds no
  field.
"""

from __future__ import annotations

import re
from datetime import datetime

__all__ = [
    "ADDRESS_TYPE_KIND",
    "INTERNAL_MAILBOX_DOMAINS",
    "ODOO_ADDRESS_TYPE",
    "PRIMARY_CONTACT_ROLE",
    "COMPANY_ROLE_TAGS_BY_ERP_ROLE",
    "COMPANY_ROLE_TAG_XMLID",
    "SALES_REP_LOGINS",
    "SALES_REP_NAMES",
    "SALES_REP_REASSIGNED",
    "UNIT_TYPE_MAP",
    "WEIGHT_UOM",
    "address_kind",
    "company_role",
    "company_role_tags",
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
    "payment_term_name",
    "trade_ranks",
    "unit_type",
    "weight_uom",
]

# ---------------------------------------------------------------------------
# CounterParty.Role -> company role tags
# ---------------------------------------------------------------------------
# The source stores one character and no legend. The letter meanings used here:
#
#   C  Customer
#   S  Supplier
#   P  Customer and Supplier
#   X  Customer and Expense
#   D  Expense
#   V  Supplier and Expense
#   A  Customer, Supplier, and Expense
#
# A company that only has Expense stays Carrier. Service ("Service Provider")
# is added only when Expense is combined with Buyer, Supplier, or both.
# A company that is both a buyer and a supplier gets both tags. The import
# does not write the Broker badge for that letter.
COMPANY_ROLE_TAGS_BY_ERP_ROLE: dict[str, tuple[str, ...]] = {
    "C": ("buyer",),
    "S": ("supplier",),
    "P": ("buyer", "supplier"),
    "X": ("buyer", "service"),
    "D": ("carrier",),
    "V": ("supplier", "service"),
    "A": ("buyer", "supplier", "service"),
}

COMPANY_ROLE_TAG_XMLID: dict[str, str] = {
    "buyer": "plasticos_facility_profile.company_role_buyer",
    "supplier": "plasticos_facility_profile.company_role_supplier",
    "carrier": "plasticos_facility_profile.company_role_carrier",
    "service": "plasticos_facility_profile.company_role_service",
}

# Single company_role badge when the letter still has one trade side.
# Buyer+Supplier has no single badge. Service does not change the side.
_SELECTION_BY_TAGS: dict[tuple[str, ...], str] = {
    ("buyer",): "buyer",
    ("supplier",): "supplier",
    ("carrier",): "carrier",
    ("buyer", "service"): "buyer",
    ("supplier", "service"): "supplier",
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


def contact_exclusion(is_active: str | None) -> str:
    """Why a ``Contact`` row is not imported, or ``""`` when it is explicitly active.

    Only an explicit active flag imports. ``N`` is inactive, and a blank or
    unrecognised value is not active either: it is excluded, never guessed.
    """
    flag = parse_bool(is_active)
    if flag is True:
        return ""
    if flag is False:
        return "IsActive is inactive"
    raw = _clean(is_active)
    return f"IsActive {raw!r} is not an explicit active flag" if raw else "IsActive is blank"


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


def company_role_tags(raw_role: str | None) -> tuple[tuple[str, ...], str | None]:
    """``CounterParty.Role`` -> company role tag keys.

    Returns ``(tags, anomaly)``. An unknown code maps to no tags and is
    reported, so a new ERP role code surfaces instead of being absorbed.
    Expense alone is ``carrier``. ``service`` is present only beside buyer,
    supplier, or both.
    """
    code = _clean(raw_role).upper()
    if not code:
        return (), "blank CounterParty.Role"
    tags = COMPANY_ROLE_TAGS_BY_ERP_ROLE.get(code)
    if tags is None:
        return (), f"unmapped CounterParty.Role {code!r}"
    return tags, None


def company_role(raw_role: str | None) -> tuple[str | None, str | None]:
    """``CounterParty.Role`` -> the single ``company_role`` badge, when one exists.

    Buyer+Supplier letters return ``(None, None)``: those companies carry both
    tags and no Broker badge. An unknown code is still reported.
    """
    tags, anomaly = company_role_tags(raw_role)
    if anomaly:
        return None, anomaly
    return _SELECTION_BY_TAGS.get(tags), None


def trade_ranks(raw_role: str | None) -> tuple[int, int]:
    """``CounterParty.Role`` -> native ``(supplier_rank, customer_rank)``.

    Service and Carrier do not set a rank. Buyer sets customer rank, Supplier
    sets supplier rank, and a company that is both sets both.
    """
    tags, _anomaly = company_role_tags(raw_role)
    return (1 if "supplier" in tags else 0, 1 if "buyer" in tags else 0)


# ERP TermsCode / APTerms wording that is not the installed account.payment.term
# name. A name absent from this map is looked up as written. Nothing here
# creates a term.
PAYMENT_TERM_NAME_BY_ERP: dict[str, str] = {
    "N45": "Net 45",
    "Due on receipt": "Immediate Payment",
    "Prepayment": "Prepaid",
    "Net 10": "15 Days",
    "Net 14": "15 Days",
    "Net 20": "Net 30",
    "N 25": "Net 30",
    "Wire Against Docs": "Immediate Payment",
    "Wire On Documents": "COD",
    "50% Prepayment": "50% Down / 50% Net 30",
    "1% 10 Net 30": "1/10 Net 30",
    "1% Net10": "1/10 Net 30",
}


def payment_term_name(raw: str | None) -> str:
    """ERP term text -> the installed ``account.payment.term`` name.

    A blank stays blank. A wording with no alias is returned unchanged, so a
    term that already uses the ERP text still matches and an unknown wording
    still fails the lookup.
    """
    text = _clean(raw)
    return PAYMENT_TERM_NAME_BY_ERP.get(text, text)


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

# Former representatives whose accounts the brokerage reassigned to MM
# (docs/erp_import_mapping.md §3a). The restored database may still carry the
# former initials on those rows; the reassignment is a mapping rule, not an
# edit of the source.
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


# ``local@domain.tld`` once lower-cased. A display name, an angle-bracket form,
# or a fragment without a top-level domain is not an address.
_EMAIL_SHAPE_RE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;.]+(?:\.[^@\s<>,;.]+)*\.[a-z]{2,}$")


def clean_emails(value: str | None) -> list[str]:
    """The addresses of one source e-mail cell, in source order.

    Step 1 drops the brokerage's own mailboxes (:func:`external_emails`).
    Step 2 splits on ``;`` or ``,``, trims, drops empty entries and entries
    not shaped ``local@domain.tld``, lower-cases, and de-duplicates keeping
    the first occurrence.
    """
    addresses: list[str] = []
    for part in _EMAIL_LIST_SPLIT_RE.split(external_emails(value)):
        entry = part.strip().lower()
        if entry and _EMAIL_SHAPE_RE.match(entry) and entry not in addresses:
            addresses.append(entry)
    return addresses


def email_cell(value: str | None) -> str:
    """Step 3: the cleaned addresses joined with ``", "``. Nothing usable is ``""``."""
    return ", ".join(clean_emails(value))


def phone_digits(value: str | None) -> str:
    """Digits of a dialable number, for matching only. ``1`` + ten digits drops the ``1``."""
    digits = "".join(char for char in real_phone(value) if char.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def phone_keys(value: str | None, region: str | None = "US") -> frozenset[str]:
    """Comparison keys of one phone value. Two numbers are the same when their keys meet.

    Always the digit key (:func:`phone_digits`). When the ``phonenumbers`` library
    is installed (it ships with Odoo) and parses the value as a possible number in
    ``region`` (the partner's country, else its company's, else ``US``), the E.164
    form too, with ``x<extension>`` when the number has one. A ``+44`` number and
    the same number written nationally then match. Blank or not dialable: empty.
    """
    digits = phone_digits(value)
    if not digits:
        return frozenset()
    keys = {digits}
    parsed = parse_phone(value, region)
    if parsed:
        keys.add(parsed)
    return frozenset(keys)


def parse_phone(value: str | None, region: str | None = "US") -> str | None:
    """E.164 (plus ``x<extension>``) of a dialable value, or ``None``.

    ``None`` when the value is not dialable, when ``phonenumbers`` is not
    installed, or when it does not parse as a possible number.
    """
    text = real_phone(value)
    if not text:
        return None
    try:
        import phonenumbers
    except ImportError:
        return None
    try:
        number = phonenumbers.parse(text, (region or "US").upper())
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        return None
    key = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    return f"{key}x{number.extension}" if number.extension else key


# Function mailboxes never become a person (operator decision 2026-11-17).
# Accounting mailboxes belong to the commercial company; operational ones to the
# one site they match, else to the company.
ACCOUNTING_MAILBOX_LOCALS: frozenset[str] = frozenset(
    {"ap", "ar", "accounting", "accounts", "invoices", "invoice", "billing", "payables", "receivables"}
)
OPERATIONAL_MAILBOX_LOCALS: frozenset[str] = frozenset(
    {"shipping", "receiving", "orders", "office", "customerservice", "info", "sales", "purchasing"}
)
MAILBOX_ACCOUNTING = "accounting"
MAILBOX_OPERATIONAL = "operational"


def function_mailbox(emails: list[str]) -> str | None:
    """``accounting`` or ``operational`` when an address has a function local part, else ``None``.

    Accounting wins when a cell carries both (``ap@`` and ``orders@``).
    """
    locals_ = {"".join(char for char in address.split("@", 1)[0].casefold() if char.isalnum()) for address in emails}
    if locals_ & ACCOUNTING_MAILBOX_LOCALS:
        return MAILBOX_ACCOUNTING
    if locals_ & OPERATIONAL_MAILBOX_LOCALS:
        return MAILBOX_OPERATIONAL
    return None


def name_local_forms(name: str | None) -> frozenset[str]:
    """The mailbox local parts a person's name produces, case-folded and alphanumeric only.

    ``first.last`` and ``firstlast`` (the same once punctuation is dropped),
    ``flast``, ``firstl``, ``first`` and ``last``. First and last are the first
    and last words of the title.
    """
    words = [_alnum(word).casefold() for word in (name or "").split()]
    words = [word for word in words if word]
    if not words:
        return frozenset()
    first, last = words[0], words[-1]
    return frozenset({first + last, first[:1] + last, first + last[:1], first, last})


def is_role_word(name: str | None) -> bool:
    """True when a contact title is an ERP role word (``BILLING``, ``COLLECTIONS``)."""
    return normalize_contact_role(name).casefold() in CONTACT_ROLE_TAGS


# ``weak_name_kind`` results. Plain constants, not a Selection.
WEAK_BLANK = "blank"
WEAK_ROLE = "role"
WEAK_EMAIL_PREFIX = "email_prefix"
WEAK_FIRST_NAME = "first_name"


def weak_name_kind(name: str | None, emails: list[str]) -> str | None:
    """Why a contact title does not name a person by itself, or ``None`` for a full name.

    ``blank``: no title. ``role``: a role word. ``email_prefix``: one word equal
    to the local part of one of the row's own external ``emails``.
    ``first_name``: any other single word. A title of two or more words that is
    not a role word is a full name, a multi-person title such as ``A B & C D``
    included.
    """
    raw = " ".join((name or "").split())
    if not raw:
        return WEAK_BLANK
    if is_role_word(raw):
        return WEAK_ROLE
    if len(raw.split(" ")) >= 2:
        return None
    if raw.casefold() in {address.split("@", 1)[0] for address in emails}:
        return WEAK_EMAIL_PREFIX
    return WEAK_FIRST_NAME


def email_prefix_title(name: str | None) -> str:
    """``todd.antonick`` -> ``Todd Antonick``. Separators are ``.``, ``_`` and ``-``.

    Only a title written in lower case, the way an address local part is, is
    rewritten. A title with any capital (``AP``) was typed by a person and is
    kept as written.
    """
    raw = (name or "").strip()
    if raw != raw.lower():
        return raw
    words = [word for word in re.split(r"[._\-]+", raw) if word]
    return " ".join(word[:1].upper() + word[1:].lower() for word in words)


def first_word_key(name: str | None) -> str:
    """The first word of a title, without case or punctuation."""
    words = (name or "").split()
    return _alnum(words[0]) if words else ""


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

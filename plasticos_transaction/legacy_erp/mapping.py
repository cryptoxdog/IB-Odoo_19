"""Source-value normalization and LegacyErp -> PlasticOS vocabulary maps.

Odoo-free on purpose: every rule here is exercised by the pure-Python CI tier
against the real payload, so a vocabulary drift in a future extract fails a test
rather than silently coercing to a default.

Two hard rules govern this module:

* **No silent coercion.** An unmapped source code returns ``None`` together with
  an anomaly string. The importer records it; it does not guess. (The retired
  CSV service defaulted unknown weight UOMs to ``"L"`` — that is exactly the
  behaviour these functions replace.)
* **Existing fields first.** Every target named here already exists on
  ``res.partner``, ``plasticos.transaction``, or ``plasticos.transaction.line``.
  This import adds no field to any model.
"""

from __future__ import annotations

from datetime import datetime

__all__ = [
    "ADDRESS_TYPE_KIND",
    "ODOO_ADDRESS_TYPE",
    "PRIMARY_CONTACT_ROLE",
    "COMPANY_ROLE_BY_LEGACY_ERP_ROLE",
    "UNIT_TYPE_MAP",
    "WEIGHT_UOM",
    "address_kind",
    "company_role",
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
COMPANY_ROLE_BY_LEGACY_ERP_ROLE: dict[str, str] = {
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
# "OMAHA, NE" used as a label). Only the recognised operational vocabulary is
# mapped; anything else falls back to a generic location, which loses no data
# because the raw label is preserved on the partner name.
ADDRESS_TYPE_KIND: dict[str, str] = {
    "INVOICE": "invoice",
    "REMIT": "invoice",
    "PRIMARY": "primary",
    "PRIMARY ADDRESS": "primary",
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
    "primary": "other",
    "other": "other",
}

# ---------------------------------------------------------------------------
# ContactRoleAssignment.RoleNm
# ---------------------------------------------------------------------------
# The LegacyErp role naming the main contact for a counterparty. It is the most
# common value in the payload (1680 of 3091 assignments) and is the one that
# fills ``res.partner.function`` when a contact holds several roles.
PRIMARY_CONTACT_ROLE = "Primary"

# ---------------------------------------------------------------------------
# WKSDetail UOM / unit type -> plasticos.transaction.line selections
# ---------------------------------------------------------------------------
# ``weight_uom`` selection is exactly L / S / E.
WEIGHT_UOM: frozenset[str] = frozenset({"L", "S", "E"})

# ``unit_type`` selection members, plus the legacy numeric code the model's own
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
    reported, so a new LegacyErp role code surfaces instead of being absorbed.
    """
    code = _clean(raw_role).upper()
    if not code:
        return None, "blank CounterParty.Role"
    mapped = COMPANY_ROLE_BY_LEGACY_ERP_ROLE.get(code)
    if mapped is None:
        return None, f"unmapped CounterParty.Role {code!r}"
    return mapped, None


def trade_ranks(raw_role: str | None) -> tuple[int, int]:
    """``CounterParty.Role`` -> native ``(supplier_rank, customer_rank)``."""
    return _RANKS_BY_ROLE.get(_clean(raw_role).upper(), (0, 0))


def address_kind(row) -> str:
    """Resolve an address to its operational kind.

    ``Address.Type`` is free text (the payload uses city names such as
    "OMAHA, NE" as labels), so the billing flags carry signal the label does
    not: 289 addresses are flagged ``InvoiceAddr='Y'`` without an invoice-like
    ``Type``, and 88 more carry ``RemitToAddress=1``. Any of the three makes an
    address a billing address, which is what the invoice/remit/billing mapping
    requirement asks for.

    An unrecognised label is a location, not a loss: the raw text is preserved
    as the partner name.
    """
    labelled = ADDRESS_TYPE_KIND.get(_clean(row.get("Type")).upper())
    if labelled == "invoice":
        return "invoice"
    if parse_bool(row.get("InvoiceAddr")) or parse_bool(row.get("RemitToAddress")):
        return "invoice"
    if parse_bool(row.get("isBillingAddressOnly")):
        return "invoice"
    return labelled or "other"


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
    """``WKSDetail.UnitType`` -> ``plasticos.transaction.line.unit_type``."""
    code = _clean(raw_unit_type).upper()
    if not code:
        return None, None
    code = UNIT_TYPE_MAP.get(code, code)
    if code not in _UNIT_TYPES:
        return None, f"unmapped UnitType {code!r}"
    return code, None


def normalize_contact_role(raw_role: str | None) -> str:
    """Normalize ``ContactRoleAssignment.RoleNm`` for deterministic tag keys."""
    return " ".join(_clean(raw_role).split())


def sort_contact_roles(roles: list[str]) -> list[str]:
    """Order a contact's roles deterministically, primary first."""
    primary = PRIMARY_CONTACT_ROLE.lower()
    return sorted(roles, key=lambda role: (role.lower() != primary, role.lower()))

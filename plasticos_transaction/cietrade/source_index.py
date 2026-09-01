"""Deterministic source indexes keyed by stable CieTrade identifiers.

Every mapper consumes source rows through this layer, never through raw file
order, so the whole import is replay-safe: the same source key always resolves
to the same source record, and therefore to the same Odoo record.

Identity contract (source key -> imported entity)::

    CpID       -> counterparty            (res.partner company)
    AddressID  -> facility / location     (res.partner child company)
    CT_ID      -> contact                 (res.partner person)
    CRA_ID     -> contact role assignment
    BuySellNo  -> transaction             (plasticos.transaction)
    DetailID   -> transaction line        (plasticos.transaction.line)

Company names, e-mail addresses, phone numbers, address text, and Odoo database
ids are never identity. They are business data.

Foreign keys are validated, not assumed. The export intentionally carries only
active counterparties, so children whose ``CpID`` was never exported are
reported as *unresolved* rather than being attached to an invented parent.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .reader import SourcePayload, SourcePayloadError

__all__ = ["IdentityViolation", "SourceIndex", "build_source_index"]

# Source key column per indexed table.
PRIMARY_KEYS: dict[str, str] = {
    "CounterParty": "CpID",
    "Address": "AddressID",
    "Contact": "CT_ID",
    "ContactRoleAssignment": "CRA_ID",
    "WKSDetail": "DetailID",
}


@dataclass(frozen=True)
class IdentityViolation:
    """A source row that cannot participate in a deterministic import."""

    table: str
    kind: str
    key: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"table": self.table, "kind": self.kind, "key": self.key, "detail": self.detail}


def _key(row: dict[str, str | None], column: str) -> str:
    """Trimmed source key. ``None`` and whitespace collapse to ``""``."""
    return (row.get(column) or "").strip()


@dataclass
class SourceIndex:
    """Source rows addressed by CieTrade identity."""

    counterparties: dict[str, dict[str, str | None]] = field(default_factory=dict)
    addresses: dict[str, dict[str, str | None]] = field(default_factory=dict)
    contacts: dict[str, dict[str, str | None]] = field(default_factory=dict)
    contact_roles: dict[str, dict[str, str | None]] = field(default_factory=dict)
    lines: dict[str, dict[str, str | None]] = field(default_factory=dict)

    # Grouped relationships
    addresses_by_cp: dict[str, list[str]] = field(default_factory=dict)
    contacts_by_cp: dict[str, list[str]] = field(default_factory=dict)
    roles_by_contact: dict[str, list[str]] = field(default_factory=dict)
    lines_by_buysell: dict[str, list[str]] = field(default_factory=dict)

    # Supporting rows needed for transaction-header reconstruction
    ledger_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    payables_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    receipts_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    deliveries_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    receipt_batches: dict[str, dict[str, str | None]] = field(default_factory=dict)
    delivery_item_ids: set[str] = field(default_factory=set)

    violations: list[IdentityViolation] = field(default_factory=list)

    # -- ordered identity accessors (deterministic iteration order) ----------
    def counterparty_ids(self) -> list[str]:
        return sorted(self.counterparties)

    def address_ids(self) -> list[str]:
        return sorted(self.addresses)

    def contact_ids(self) -> list[str]:
        return sorted(self.contacts)

    def contact_role_ids(self) -> list[str]:
        return sorted(self.contact_roles)

    def buysell_numbers(self) -> list[str]:
        """Transaction universe: every BuySellNo that owns at least one line."""
        return sorted(self.lines_by_buysell)

    def detail_ids(self, buysell_no: str) -> list[str]:
        return sorted(self.lines_by_buysell.get(buysell_no, []))

    # -- unresolved foreign keys -------------------------------------------
    def unresolved(self, kind: str) -> list[IdentityViolation]:
        return [v for v in self.violations if v.kind == kind]

    def counts(self) -> dict[str, int]:
        return {
            "counterparties": len(self.counterparties),
            "addresses": len(self.addresses),
            "contacts": len(self.contacts),
            "contact_roles": len(self.contact_roles),
            "transactions": len(self.lines_by_buysell),
            "transaction_lines": len(self.lines),
            "violations": len(self.violations),
        }


def build_source_index(payload: SourcePayload) -> SourceIndex:
    """Index the payload by source identity and validate PK/FK integrity.

    Raises:
        SourcePayloadError: a declared primary key is blank or duplicated. That
            breaks replay-safety outright and cannot be reported as a per-row
            anomaly.
    """
    index = SourceIndex()

    index.counterparties = _index_by_pk(payload, "CounterParty")
    index.addresses = _index_by_pk(payload, "Address")
    index.contacts = _index_by_pk(payload, "Contact")
    index.contact_roles = _index_by_pk(payload, "ContactRoleAssignment")
    index.lines = _index_by_pk(payload, "WKSDetail")

    _link_children(index)
    _link_lines(index)
    _index_supporting_tables(payload, index)
    return index


def _index_by_pk(payload: SourcePayload, table: str) -> dict[str, dict[str, str | None]]:
    column = PRIMARY_KEYS[table]
    indexed: dict[str, dict[str, str | None]] = {}
    for position, row in enumerate(payload.rows(table), start=1):
        key = _key(row, column)
        if not key:
            raise SourcePayloadError(f"{table} row {position}: blank primary key {column}")
        if key in indexed:
            raise SourcePayloadError(f"{table}: duplicate primary key {column}={key!r}")
        indexed[key] = row
    return indexed


def _link_children(index: SourceIndex) -> None:
    """Attach addresses and contacts to their counterparty by CpID only."""
    addresses: dict[str, list[str]] = defaultdict(list)
    for address_id in sorted(index.addresses):
        cp_id = _key(index.addresses[address_id], "CpID")
        if not cp_id:
            index.violations.append(IdentityViolation("Address", "missing_parent_key", address_id, "blank CpID"))
            continue
        if cp_id not in index.counterparties:
            index.violations.append(
                IdentityViolation(
                    "Address",
                    "unresolved_counterparty",
                    address_id,
                    f"CpID={cp_id} not in exported (active) counterparties",
                )
            )
            continue
        addresses[cp_id].append(address_id)
    index.addresses_by_cp = dict(addresses)

    contacts: dict[str, list[str]] = defaultdict(list)
    for contact_id in sorted(index.contacts):
        cp_id = _key(index.contacts[contact_id], "CpID")
        if not cp_id:
            index.violations.append(IdentityViolation("Contact", "missing_parent_key", contact_id, "blank CpID"))
            continue
        if cp_id not in index.counterparties:
            index.violations.append(
                IdentityViolation(
                    "Contact",
                    "unresolved_counterparty",
                    contact_id,
                    f"CpID={cp_id} not in exported (active) counterparties",
                )
            )
            continue
        contacts[cp_id].append(contact_id)
    index.contacts_by_cp = dict(contacts)

    roles: dict[str, list[str]] = defaultdict(list)
    for role_id in sorted(index.contact_roles):
        contact_id = _key(index.contact_roles[role_id], "CT_ID")
        if not contact_id:
            index.violations.append(
                IdentityViolation("ContactRoleAssignment", "missing_parent_key", role_id, "blank CT_ID")
            )
            continue
        if contact_id not in index.contacts:
            index.violations.append(
                IdentityViolation(
                    "ContactRoleAssignment",
                    "unresolved_contact",
                    role_id,
                    f"CT_ID={contact_id} not in exported contacts",
                )
            )
            continue
        roles[contact_id].append(role_id)
    index.roles_by_contact = dict(roles)


def _link_lines(index: SourceIndex) -> None:
    grouped: dict[str, list[str]] = defaultdict(list)
    for detail_id in sorted(index.lines):
        buysell_no = _key(index.lines[detail_id], "BuySellNo")
        if not buysell_no:
            index.violations.append(IdentityViolation("WKSDetail", "missing_parent_key", detail_id, "blank BuySellNo"))
            continue
        grouped[buysell_no].append(detail_id)
    index.lines_by_buysell = dict(grouped)


def _index_supporting_tables(payload: SourcePayload, index: SourceIndex) -> None:
    """Index the tables that transaction-header reconstruction depends on."""
    for table, target in (
        ("GPLedger", index.ledger_by_buysell),
        ("Payables", index.payables_by_buysell),
        ("Receipt", index.receipts_by_buysell),
        ("WksDelivery", index.deliveries_by_buysell),
    ):
        for row in payload.rows(table):
            buysell_no = _key(row, "BuySellNo")
            if buysell_no:
                target.setdefault(buysell_no, []).append(row)

    for row in payload.rows("ReceiptBatch"):
        batch_no = _key(row, "ARBatchNo")
        if batch_no:
            index.receipt_batches[batch_no] = row

    index.delivery_item_ids = {
        item_id for row in payload.rows("WksDelivery") if (item_id := _key(row, "ItemID")) and item_id != "0"
    }

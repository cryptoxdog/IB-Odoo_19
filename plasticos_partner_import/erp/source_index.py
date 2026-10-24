"""Deterministic source indexes keyed by stable ERP identifiers.

Every mapper consumes source rows through this layer, never through raw file
order, so the whole import is replay-safe: the same source key always resolves
to the same source record, and therefore to the same Odoo record.

Identity contract (source key -> imported entity)::

    CpID       -> counterparty            (res.partner company)
    AddressID  -> facility / location     (res.partner child company)
    CT_ID      -> contact                 (res.partner person)
    CRA_ID     -> contact role assignment
    CpID       -> SalesReps rows          (res.partner.user_id on the company)
    BuySellNo  -> deal header
    DetailID   -> deal line
    APBatchNo  -> payables batch header   (source evidence only; no Odoo record)

Company names, e-mail addresses, phone numbers, address text, and Odoo database
ids are never identity. They are business data.

Foreign keys are validated, not assumed. The export intentionally carries only
active counterparties, so children whose ``CpID`` was never exported are
reported as *unresolved* rather than being attached to an invented parent.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from .reader import SourcePayload, SourcePayloadError

__all__ = [
    "INVENTORY_COUNTERPARTY",
    "IdentityViolation",
    "SourceIndex",
    "account_inventory_destinations",
    "build_source_index",
    "payables_batch_census",
]

# BuySell.CustID / Address.CpID for an internal inventory receipt. The address
# Type is the site selector (BuySell.ShipToID). It is not a commercial partner.
INVENTORY_COUNTERPARTY = "(INV)"

# Source key column per indexed table.
PRIMARY_KEYS: dict[str, str] = {
    "CounterParty": "CpID",
    "Address": "AddressID",
    "Contact": "CT_ID",
    "ContactRoleAssignment": "CRA_ID",
    "WKSDetail": "DetailID",
    "PO": "POID",
    "PODetail": "PO_ID",
    "BuySell": "BuySellNo",
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
    """Source rows addressed by ERP identity."""

    counterparties: dict[str, dict[str, str | None]] = field(default_factory=dict)
    addresses: dict[str, dict[str, str | None]] = field(default_factory=dict)
    contacts: dict[str, dict[str, str | None]] = field(default_factory=dict)
    contact_roles: dict[str, dict[str, str | None]] = field(default_factory=dict)
    lines: dict[str, dict[str, str | None]] = field(default_factory=dict)

    # Grouped relationships
    addresses_by_cp: dict[str, list[str]] = field(default_factory=dict)
    # (INV) sites, keyed by AddressID. Not commercial children and not partners.
    inventory_destinations: dict[str, dict[str, str | None]] = field(default_factory=dict)
    # (CpID, Type) -> AddressIDs. A worksheet resolves only an exact one-row match.
    inventory_by_selector: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    contacts_by_cp: dict[str, list[str]] = field(default_factory=dict)
    roles_by_contact: dict[str, list[str]] = field(default_factory=dict)
    sales_reps_by_cp: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    # Every SalesReps row the payload carried, linked or not. The file has no
    # primary key, so this is the row count the summary reconciles against.
    sales_rep_rows: int = 0
    lines_by_buysell: dict[str, list[str]] = field(default_factory=dict)

    # Supporting rows needed for transaction-header reconstruction
    ledger_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    payables_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    receipts_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    deliveries_by_buysell: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    receipt_batches: dict[str, dict[str, str | None]] = field(default_factory=dict)
    delivery_item_ids: set[str] = field(default_factory=set)

    # Commercial graph. Present on a direct SQL read. Absent on the frozen grid.
    orders: dict[str, dict[str, str | None]] = field(default_factory=dict)
    order_lines: dict[str, dict[str, str | None]] = field(default_factory=dict)
    buysells: dict[str, dict[str, str | None]] = field(default_factory=dict)
    orders_by_source_number: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    prepay_batches: set[str] = field(default_factory=set)
    # PayablesBatch headers by APBatchNo, and Payables rows grouped by the
    # APBatchNo they carry. Source evidence only: no importer reads them, and
    # their violations are kept apart from ``violations`` so the import
    # summary does not change. A duplicated APBatchNo is left out of the lookup.
    payables_batches: dict[str, dict[str, str | None]] = field(default_factory=dict)
    payables_by_batch: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    payables_batch_violations: list[IdentityViolation] = field(default_factory=list)

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

    def inventory_destination_ids(self, cust_id: str, ship_to_id: str) -> list[str]:
        """AddressIDs where ``(CpID, Type)`` equals ``(cust_id, ship_to_id)``.

        Blank and multi-row matches are returned as they are. The caller holds
        a worksheet unless the list has exactly one id.
        """
        key = ((cust_id or "").strip(), (ship_to_id or "").strip())
        return list(self.inventory_by_selector.get(key, []))

    # -- unresolved foreign keys -------------------------------------------
    def unresolved(self, kind: str) -> list[IdentityViolation]:
        return [v for v in self.violations if v.kind == kind]

    def counts(self) -> dict[str, int]:
        """Source rows per table (plus the transaction universe), and the violation tally.

        Every per-table figure counts the rows the payload carried, including
        the rows later reported as identity violations, so each source row is
        counted exactly once. ``violations`` is a diagnostic tally of those
        reported rows, not an extra population; the summary excludes it when
        it reconciles ``records_seen``.
        """
        return {
            "counterparties": len(self.counterparties),
            "addresses": len(self.addresses),
            "contacts": len(self.contacts),
            "contact_roles": len(self.contact_roles),
            "sales_reps": self.sales_rep_rows,
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

    if "CounterParty" in payload.tables:
        index.counterparties = _index_by_pk(payload, "CounterParty")
    if "Address" in payload.tables:
        index.addresses = _index_by_pk(payload, "Address")
    if "Contact" in payload.tables:
        index.contacts = _index_by_pk(payload, "Contact")
    if "ContactRoleAssignment" in payload.tables:
        index.contact_roles = _index_by_pk(payload, "ContactRoleAssignment")
    if "WKSDetail" in payload.tables:
        index.lines = _index_by_pk(payload, "WKSDetail")
        _link_lines(index)
    if "PO" in payload.tables:
        index.orders = _index_by_pk(payload, "PO")
        _link_orders(index)
    if "PODetail" in payload.tables:
        index.order_lines = _index_by_pk(payload, "PODetail")
    if "BuySell" in payload.tables:
        index.buysells = _index_by_pk(payload, "BuySell")
    if "PayablesBatch" in payload.tables:
        _index_prepay_batches(payload, index)
        _index_payables_batches(payload, index)
    if payload.tables.keys() & {"GPLedger", "Payables", "Receipt", "ReceiptBatch", "WksDelivery"}:
        _index_supporting_tables(payload, index)
    if "Payables" in payload.tables:
        _group_payables_by_batch(payload, index, headers_loaded="PayablesBatch" in payload.tables)

    _link_children(
        index,
        counterparties_loaded="CounterParty" in payload.tables,
        contacts_loaded="Contact" in payload.tables,
    )
    if "SalesReps" in payload.tables:
        _link_sales_reps(payload, index, counterparties_loaded="CounterParty" in payload.tables)
    return index


def _link_sales_reps(payload: SourcePayload, index: SourceIndex, *, counterparties_loaded: bool) -> None:
    """Group SalesReps rows by CpID. The file has no primary key of its own."""
    grouped: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    rows = payload.rows("SalesReps")
    index.sales_rep_rows = len(rows)
    for position, row in enumerate(rows, start=2):
        cp_id = _key(row, "CpID")
        rep = _key(row, "ReferrerNo")
        if not cp_id:
            index.violations.append(
                IdentityViolation("SalesReps", "missing_parent_key", f"line {position}", "blank CpID")
            )
            continue
        if counterparties_loaded and cp_id not in index.counterparties:
            index.violations.append(
                IdentityViolation(
                    "SalesReps",
                    "unresolved_counterparty",
                    f"{cp_id}/{rep}",
                    f"CpID={cp_id} not in exported (active) counterparties",
                )
            )
            continue
        grouped[cp_id].append(row)
    index.sales_reps_by_cp = dict(grouped)


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


def account_inventory_destinations(index: SourceIndex, report) -> None:
    """Count each ``(INV)`` address once, without creating a partner for it.

    The row stays in the address population. ``skipped`` is the unchanged
    outcome: no ``res.partner`` is written on the first run or on replay.
    """
    for _address_id in sorted(index.inventory_destinations):
        report.skip("locations")


def _link_children(index: SourceIndex, *, counterparties_loaded: bool, contacts_loaded: bool) -> None:
    """Attach addresses and contacts to their counterparty by CpID only.

    A layer that does not include the parent file still groups the child rows.
    The importer resolves that parent from the database. A parent file that is
    present and does not contain the id stays unresolved. ``(INV)`` is the
    inventory-site counterparty: those rows are destinations, not partners,
    and they are not unresolved. Every other placeholder CpID stays unresolved
    when the counterparty file is present and does not contain it.
    """
    addresses: dict[str, list[str]] = defaultdict(list)
    inventory: dict[tuple[str, str], list[str]] = defaultdict(list)
    for address_id in sorted(index.addresses):
        row = index.addresses[address_id]
        cp_id = _key(row, "CpID")
        if not cp_id:
            index.violations.append(IdentityViolation("Address", "missing_parent_key", address_id, "blank CpID"))
            continue
        if cp_id == INVENTORY_COUNTERPARTY:
            index.inventory_destinations[address_id] = row
            inventory[(cp_id, _key(row, "Type"))].append(address_id)
            continue
        if counterparties_loaded and cp_id not in index.counterparties:
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
    index.inventory_by_selector = dict(inventory)

    contacts: dict[str, list[str]] = defaultdict(list)
    for contact_id in sorted(index.contacts):
        cp_id = _key(index.contacts[contact_id], "CpID")
        if not cp_id:
            index.violations.append(IdentityViolation("Contact", "missing_parent_key", contact_id, "blank CpID"))
            continue
        if counterparties_loaded and cp_id not in index.counterparties:
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
        if contacts_loaded and contact_id not in index.contacts:
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


def _link_orders(index: SourceIndex) -> None:
    """Group headers by (Source, PONumber). More than one header is a conflict."""
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for po_id in sorted(index.orders):
        row = index.orders[po_id]
        source = _key(row, "Source").upper()
        number = _key(row, "PONumber")
        if source and number:
            grouped[(source, number)].append(po_id)
    index.orders_by_source_number = dict(grouped)


def _index_prepay_batches(payload: SourcePayload, index: SourceIndex) -> None:
    for row in payload.rows("PayablesBatch"):
        if _key(row, "PrePay") == "1":
            batch = _key(row, "APBatchNo")
            if batch:
                index.prepay_batches.add(batch)


def _index_payables_batches(payload: SourcePayload, index: SourceIndex) -> None:
    """Index PayablesBatch headers by APBatchNo. Blank and duplicated keys are violations."""
    grouped: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    for position, row in enumerate(payload.rows("PayablesBatch"), start=1):
        batch = _key(row, "APBatchNo")
        if not batch:
            index.payables_batch_violations.append(
                IdentityViolation("PayablesBatch", "missing_primary_key", f"row {position}", "blank APBatchNo")
            )
            continue
        grouped[batch].append(row)
    for batch in sorted(grouped):
        rows = grouped[batch]
        if len(rows) > 1:
            index.payables_batch_violations.append(
                IdentityViolation("PayablesBatch", "duplicate_batch_header", batch, f"{len(rows)} header rows")
            )
            continue
        index.payables_batches[batch] = rows[0]


def _group_payables_by_batch(payload: SourcePayload, index: SourceIndex, *, headers_loaded: bool) -> None:
    """Group Payables rows by APBatchNo. A batch with no header is a violation when headers are loaded."""
    grouped: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    for row in payload.rows("Payables"):
        batch = _key(row, "APBatchNo")
        if batch:
            grouped[batch].append(row)
    index.payables_by_batch = {batch: grouped[batch] for batch in sorted(grouped)}
    if not headers_loaded:
        return
    duplicated = {v.key for v in index.payables_batch_violations if v.kind == "duplicate_batch_header"}
    for batch, rows in index.payables_by_batch.items():
        if batch not in index.payables_batches and batch not in duplicated:
            index.payables_batch_violations.append(
                IdentityViolation(
                    "Payables", "missing_batch_header", batch, f"{len(rows)} Payables rows; no PayablesBatch header"
                )
            )


def _decimal(value: str | None) -> Decimal | None:
    try:
        return Decimal((value or "").strip())
    except InvalidOperation:
        return None


def payables_batch_census(index: SourceIndex) -> dict[str, int]:
    """Classify PayablesBatch headers against their Payables rows. Counts only; nothing is written.

    The amount check compares the header ``FXAmount`` with the signed sum of
    its rows' ``FxAmount`` when every row carries the header currency. Rows
    in another currency or with no parseable amount are counted, not compared.
    """
    census = {
        "headers": len(index.payables_batches),
        "prepay_headers": len(index.prepay_batches),
        "prepay_member_rows": sum(len(index.payables_by_batch.get(b, [])) for b in index.prepay_batches),
        "headers_without_payables": 0,
        "headers_with_one_payable": 0,
        "headers_with_many_payables": 0,
        "payables_without_batch": sum(
            1 for rows in index.payables_by_buysell.values() for row in rows if not _key(row, "APBatchNo")
        ),
        "duplicate_headers": 0,
        "blank_header_keys": 0,
        "missing_header_batches": 0,
        "missing_header_rows": 0,
        "batches_mixing_gl": 0,
        "batches_mixing_vendor": 0,
        "header_vendor_mismatch": 0,
        "num_of_items_mismatch": 0,
        "amount_residual_batches": 0,
        "amount_currency_mismatch_batches": 0,
        "amount_uncomparable_batches": 0,
    }
    for violation in index.payables_batch_violations:
        if violation.kind == "duplicate_batch_header":
            census["duplicate_headers"] += 1
        elif violation.kind == "missing_primary_key":
            census["blank_header_keys"] += 1
        elif violation.kind == "missing_batch_header":
            census["missing_header_batches"] += 1
            census["missing_header_rows"] += len(index.payables_by_batch.get(violation.key, []))
    for batch, header in index.payables_batches.items():
        rows = index.payables_by_batch.get(batch, [])
        if not rows:
            census["headers_without_payables"] += 1
            continue
        census["headers_with_one_payable" if len(rows) == 1 else "headers_with_many_payables"] += 1
        if len({_key(row, "GLAcct") for row in rows}) > 1:
            census["batches_mixing_gl"] += 1
        vendors = {_key(row, "CpID") for row in rows}
        if len(vendors) > 1:
            census["batches_mixing_vendor"] += 1
        if _key(header, "CpID") and vendors != {_key(header, "CpID")}:
            census["header_vendor_mismatch"] += 1
        items = _key(header, "NumofItems")
        if items and items != str(len(rows)):
            census["num_of_items_mismatch"] += 1
        currency = _key(header, "CurrencyCd")
        total = _decimal(header.get("FXAmount"))
        amounts = [_decimal(row.get("FxAmount")) for row in rows]
        if any(_key(row, "CurrencyCd") != currency for row in rows):
            census["amount_currency_mismatch_batches"] += 1
        elif total is None or any(amount is None for amount in amounts):
            census["amount_uncomparable_batches"] += 1
        elif total != sum(amounts, Decimal(0)):
            census["amount_residual_batches"] += 1
    return census


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
            # A payable with no worksheet reference is still a source bill the
            # import must account for; it is kept under the empty key so the
            # census can report it. Other supporting rows need a worksheet.
            if buysell_no or table == "Payables":
                target.setdefault(buysell_no, []).append(row)

    for row in payload.rows("ReceiptBatch"):
        batch_no = _key(row, "ARBatchNo")
        if batch_no:
            index.receipt_batches[batch_no] = row

    index.delivery_item_ids = {
        item_id for row in payload.rows("WksDelivery") if (item_id := _key(row, "ItemID")) and item_id != "0"
    }

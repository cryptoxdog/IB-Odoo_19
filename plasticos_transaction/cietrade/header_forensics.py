"""Authoritative transaction-header reconstruction (gap G05).

``WKSDetail`` carries the transaction *lines*. The export carries no worksheet
header table, and ``WKSDetail`` has no party, date, or status column — its full
104-column inventory (``data/legacy_erp_sm_export/diagnostics/q4_columns.csv``)
contains no status-like column at all. Supplier, buyer, date, and state are
therefore reconstructed from the accounting relationships that *do* exist, and
are proven from the payload rather than inferred from names or PO text.

Proven join path
----------------
::

    BuySellNo
       |
       +-- Payables (ItemID empty)  --> Payables.CpID          = SUPPLIER
       |
       +-- Receipt --ARBatchNo--> ReceiptBatch.CPID            = BUYER
       |
       +-- GPLedger.TradeDt                                    = TRADE DATE
       |
       +-- WKSDetail --> DetailID[]                            = LINES

Evidence measured on the tracked payload (8257 BuySellNo carrying lines):

* ``Payables.ItemID`` is a foreign key into ``WksDelivery.ItemID`` (8054 of the
  8210 populated values resolve). A payable carrying one is a **freight** cost
  for a delivery leg, not the material purchase; its ``CpID`` agrees with
  ``WksDelivery.VendorID`` for 5250 of 5524 shared BuySellNo. Splitting on that
  column turns an ambiguous vendor set (3849 BuySellNo carried two distinct
  ``CpID``) into a single material supplier for 6060 of 6062 BuySellNo.
* ``Receipt -> ReceiptBatch.CPID`` yields exactly one customer for **all** 6938
  BuySellNo it covers — no BuySellNo has two.
* ``CounterParty.Role`` corroborates both directions: the material-supplier set
  is ``V``/``S``-dominant and contains no ``X``/``C``; the buyer set is
  ``X``/``C``/``A``-only and contains no ``V``; carrier code ``D`` appears only
  on freight legs.

Deliberately rejected
---------------------
``WKSDetail.DesignatedCpID`` is populated on only 22 of 8257 BuySellNo and
matches neither the buyer (0 of 0 overlapping) nor the material supplier (0 of
15 overlapping). It is not a party identifier and is never used as one. Company
names, PO text, description text, and database ids are likewise never used.

Determinism, not universality
-----------------------------
A BuySellNo whose supplier or buyer is not carried by the source resolves to
``None`` for that party, with the reason recorded. That is a deterministic
outcome and is reported as unresolved. It is never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .source_index import SourceIndex

__all__ = [
    "HISTORICAL_STATES",
    "TransactionHeader",
    "reconstruct_transaction_header",
    "reconstruct_all_headers",
]

# Historical states this reconstruction can emit, in settlement order. Every
# value is a member of the plasticos.transaction ``state`` selection.
HISTORICAL_STATES = ("draft", "delivered", "invoiced", "closed")

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d")

# Payables.ItemID values meaning "no delivery leg", i.e. a material payable.
_EMPTY_ITEM_IDS = frozenset({"", "0"})


@dataclass(frozen=True)
class TransactionHeader:
    """Deterministic reconstruction result for one ``BuySellNo``."""

    buysell_no: str
    supplier_cp_id: str | None
    buyer_cp_id: str | None
    trade_date: datetime | None
    state: str
    detail_ids: tuple[str, ...]
    anomalies: tuple[str, ...] = field(default=())

    @property
    def is_complete(self) -> bool:
        """Both parties and a trade date were resolved from the source."""
        return bool(self.supplier_cp_id and self.buyer_cp_id and self.trade_date)

    def as_dict(self) -> dict[str, object]:
        return {
            "buysell_no": self.buysell_no,
            "supplier_cp_id": self.supplier_cp_id,
            "buyer_cp_id": self.buyer_cp_id,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "state": self.state,
            "line_count": len(self.detail_ids),
            "anomalies": list(self.anomalies),
        }


def _value(row: dict[str, str | None], column: str) -> str:
    return (row.get(column) or "").strip()


def _parse_datetime(raw: str) -> datetime | None:
    """Parse an exported SQL Server datetime. Unknown shapes yield ``None``."""
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _resolve_supplier(index: SourceIndex, buysell_no: str) -> tuple[str | None, list[str]]:
    """Material supplier = ``Payables.CpID`` on payables with no delivery leg."""
    anomalies: list[str] = []
    candidates: set[str] = set()
    for row in index.payables_by_buysell.get(buysell_no, []):
        if _value(row, "ItemID") in _EMPTY_ITEM_IDS:
            cp_id = _value(row, "CpID")
            if cp_id:
                candidates.add(cp_id)

    if not candidates:
        return None, ["no material payable (supplier not carried by source)"]
    if len(candidates) > 1:
        anomalies.append(
            "ambiguous supplier: material payables name " + ", ".join(sorted(candidates)) + " (source-data anomaly)"
        )
        return None, anomalies
    return candidates.pop(), anomalies


def _resolve_buyer(index: SourceIndex, buysell_no: str) -> tuple[str | None, list[str]]:
    """Buyer = ``ReceiptBatch.CPID`` reached through ``Receipt.ARBatchNo``."""
    anomalies: list[str] = []
    candidates: set[str] = set()
    for row in index.receipts_by_buysell.get(buysell_no, []):
        batch_no = _value(row, "ARBatchNo")
        if not batch_no:
            continue
        batch = index.receipt_batches.get(batch_no)
        if batch is None:
            anomalies.append(f"receipt batch {batch_no} not carried by source")
            continue
        cp_id = _value(batch, "CPID")
        if cp_id:
            candidates.add(cp_id)

    if not candidates:
        anomalies.append("no settled receipt (buyer not carried by source)")
        return None, anomalies
    if len(candidates) > 1:
        anomalies.append(
            "ambiguous buyer: receipt batches name " + ", ".join(sorted(candidates)) + " (source-data anomaly)"
        )
        return None, anomalies
    return candidates.pop(), anomalies


def _resolve_trade_date(index: SourceIndex, buysell_no: str) -> tuple[datetime | None, list[str]]:
    """Trade date = earliest ``GPLedger.TradeDt`` booked against the BuySellNo.

    365 BuySellNo carry more than one ledger row with differing dates (later
    adjustments). The earliest is the trade itself, so ``min`` is both correct
    and deterministic.
    """
    anomalies: list[str] = []
    dates: list[datetime] = []
    for row in index.ledger_by_buysell.get(buysell_no, []):
        raw = _value(row, "TradeDt")
        parsed = _parse_datetime(raw)
        if parsed is not None:
            dates.append(parsed)
        elif raw:
            anomalies.append(f"unparsable GPLedger.TradeDt {raw!r}")
    if not dates:
        anomalies.append("no GPLedger trade date")
        return None, anomalies
    return min(dates), anomalies


def _derive_state(index: SourceIndex, buysell_no: str) -> str:
    """Derive historical state from settlement evidence.

    The source carries **no** status column, so state is derived, never read:

    ``closed``    booked in GPLedger, supplier paid (posted material payable),
                  and customer receipt settled — the trade is complete;
    ``invoiced``  booked in GPLedger but not fully settled on both sides;
    ``delivered`` a delivery leg exists but the trade was never booked;
    ``draft``     lines only, no accounting or delivery evidence.
    """
    booked = bool(index.ledger_by_buysell.get(buysell_no))
    payables = index.payables_by_buysell.get(buysell_no, [])
    supplier_paid = any(_value(row, "ItemID") in _EMPTY_ITEM_IDS and _value(row, "Posted") == "1" for row in payables)
    customer_paid = bool(index.receipts_by_buysell.get(buysell_no))
    delivered = bool(index.deliveries_by_buysell.get(buysell_no))

    if booked and supplier_paid and customer_paid:
        return "closed"
    if booked:
        return "invoiced"
    if delivered:
        return "delivered"
    return "draft"


def reconstruct_transaction_header(index: SourceIndex, buysell_no: str) -> TransactionHeader:
    """Reconstruct one transaction header from authoritative source joins."""
    supplier_cp_id, supplier_notes = _resolve_supplier(index, buysell_no)
    buyer_cp_id, buyer_notes = _resolve_buyer(index, buysell_no)
    trade_date, date_notes = _resolve_trade_date(index, buysell_no)

    anomalies = [*supplier_notes, *buyer_notes, *date_notes]

    # A party the source names but the export never carried cannot be linked.
    if supplier_cp_id and supplier_cp_id not in index.counterparties:
        anomalies.append(f"supplier CpID={supplier_cp_id} not in exported counterparties")
        supplier_cp_id = None
    if buyer_cp_id and buyer_cp_id not in index.counterparties:
        anomalies.append(f"buyer CpID={buyer_cp_id} not in exported counterparties")
        buyer_cp_id = None

    return TransactionHeader(
        buysell_no=buysell_no,
        supplier_cp_id=supplier_cp_id,
        buyer_cp_id=buyer_cp_id,
        trade_date=trade_date,
        state=_derive_state(index, buysell_no),
        detail_ids=tuple(index.detail_ids(buysell_no)),
        anomalies=tuple(anomalies),
    )


def reconstruct_all_headers(index: SourceIndex) -> dict[str, TransactionHeader]:
    """Reconstruct every transaction in the source universe, in key order."""
    return {buysell_no: reconstruct_transaction_header(index, buysell_no) for buysell_no in index.buysell_numbers()}

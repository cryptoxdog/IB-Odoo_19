"""Result accounting for one ERP import run.

Odoo-free: the report is a plain record of what the import did, so it is built
and asserted in the pure-Python CI tier alongside the rest of the source layer.
"""

from __future__ import annotations

__all__ = ["ImportReport"]


class ImportReport:
    """Result accounting for one import run."""

    BUCKETS = (
        "counterparties",
        "locations",
        "contacts",
        "contact_roles",
        "salespersons",
        "transactions",
        "transaction_lines",
    )

    def __init__(self) -> None:
        self.payload_kind: str = ""
        # Where the rows came from (database label, statement folder, or grid
        # root). Never a credential.
        self.source_origin: str = ""
        self.source_counts: dict[str, int] = {}
        self.counts: dict[str, dict[str, int]] = {
            bucket: {"created": 0, "updated": 0, "skipped": 0, "rejected": 0} for bucket in self.BUCKETS
        }
        self.unresolved: list[dict[str, str]] = []
        self.anomalies: list[dict[str, str]] = []
        self.errors: list[dict[str, str]] = []
        # Run-level failures: a mandatory check of the whole run that did not
        # pass (the payables identity reconciliation). Not a row, so never a
        # counter; the run is ``failed`` and exits nonzero while every row
        # keeps the outcome it actually had.
        self.failures: list[dict[str, str]] = []
        # Source exceptions grouped by root cause with their dollar exposure
        # (order links, price precision, payables routing). Filled by the
        # historical extension; empty for a partner-only run.
        self.census: dict = {}

    def bump(self, bucket: str, outcome: str, amount: int = 1) -> None:
        self.counts[bucket][outcome] += amount

    def skip(self, bucket: str, amount: int = 1) -> None:
        """Record a no-write replay (unchanged record or dry-run preview)."""
        self.bump(bucket, "skipped", amount)

    def reject(self, bucket: str, amount: int = 1) -> None:
        """Record a source row that was refused (invalid, not silently lost)."""
        self.bump(bucket, "rejected", amount)

    def unresolved_ref(self, table: str, kind: str, key: str, detail: str) -> None:
        """Record a source reference that could not be resolved."""
        self.unresolved.append({"table": table, "kind": kind, "key": key, "detail": detail})

    def anomaly(self, table: str, key: str, detail: str) -> None:
        self.anomalies.append({"table": table, "key": key, "detail": detail})

    def error(self, key: str, detail: str) -> None:
        self.errors.append({"buysell_no": key, "error": detail})

    def fail(self, check: str, detail: str) -> None:
        """Record that a mandatory run-level check did not pass. The run cannot succeed."""
        self.failures.append({"check": check, "detail": detail})

    def as_dict(self) -> dict:
        return {
            "payload_kind": self.payload_kind,
            "source_origin": self.source_origin,
            "source_counts": self.source_counts,
            "counts": self.counts,
            "unresolved": self.unresolved,
            "anomalies": self.anomalies,
            "errors": self.errors,
            "failures": self.failures,
            "census": self.census,
        }

"""Result accounting for one LegacyErp import run.

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
        "transactions",
        "transaction_lines",
    )

    def __init__(self) -> None:
        self.payload_kind: str = ""
        self.source_counts: dict[str, int] = {}
        self.counts: dict[str, dict[str, int]] = {
            bucket: {"created": 0, "updated": 0, "skipped": 0} for bucket in self.BUCKETS
        }
        self.unresolved: list[dict[str, str]] = []
        self.anomalies: list[dict[str, str]] = []
        self.errors: list[dict[str, str]] = []

    def bump(self, bucket: str, outcome: str, amount: int = 1) -> None:
        self.counts[bucket][outcome] += amount

    def skip(self, bucket: str, amount: int = 1) -> None:
        self.bump(bucket, "skipped", amount)

    def unresolved_ref(self, table: str, kind: str, key: str, detail: str) -> None:
        """Record a source reference that could not be resolved."""
        self.unresolved.append({"table": table, "kind": kind, "key": key, "detail": detail})

    def anomaly(self, table: str, key: str, detail: str) -> None:
        self.anomalies.append({"table": table, "key": key, "detail": detail})

    def error(self, key: str, detail: str) -> None:
        self.errors.append({"buysell_no": key, "error": detail})

    def as_dict(self) -> dict:
        return {
            "payload_kind": self.payload_kind,
            "source_counts": self.source_counts,
            "counts": self.counts,
            "unresolved": self.unresolved,
            "anomalies": self.anomalies,
            "errors": self.errors,
        }

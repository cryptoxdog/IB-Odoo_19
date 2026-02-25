"""Negotiation audit log for traceability.

Records every negotiation outcome with full trace for compliance
and analytics.  Designed as a lightweight dict-based factory so the
negotiation engine (pure Python, no Odoo env) can call
``NegotiationAudit.create(payload)`` without an ORM dependency.
"""

import json
import logging
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)

# In-memory buffer; a production deployment would flush to the Odoo
# model ``plasticos.negotiation.audit`` via a scheduled job.
_audit_buffer: list[dict] = []


class NegotiationAudit:
    """Append-only audit log for negotiation outcomes."""

    @staticmethod
    def create(payload: dict) -> dict:
        """Persist a negotiation audit record.

        Args:
            payload: Dict with keys tenant_code, intake_id, facility_id,
                     agreed_price, rounds, confidence_score,
                     relationship_score, full_trace.

        Returns:
            The stored audit record with timestamp.
        """
        record = {
            **payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _audit_buffer.append(record)
        _logger.info(
            "Negotiation audit: intake=%s facility=%s price=%.2f rounds=%d",
            payload.get("intake_id"),
            payload.get("facility_id"),
            payload.get("agreed_price", 0),
            payload.get("rounds", 0),
        )
        return record

    @staticmethod
    def flush() -> list[dict]:
        """Return and clear the in-memory audit buffer."""
        records = list(_audit_buffer)
        _audit_buffer.clear()
        return records

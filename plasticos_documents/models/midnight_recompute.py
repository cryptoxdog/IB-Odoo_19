"""Document half of the midnight recompute.

The cron itself stays on plasticos.midnight.recompute in plasticos_base and
runs daily at 00:05. Until that job, stored compliance_status may still show
the previous day. Invoice and close authorization use the live read-only
decision, not that stored snapshot. This extension only refreshes the stored
document expiry flag and the transactions those rows name explicitly.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

_EXPIRY_KEYSET_LIMIT = 1000
_UNIQUE_SUBJECT_FIELDS = {
    "plasticos.load": "load_id",
    "sale.order": "sale_order_id",
    "purchase.order": "purchase_order_ids",
}


class PlasticosMidnightRecomputeDocument(models.AbstractModel):
    _inherit = "plasticos.midnight.recompute"

    def _recompute_document_expiry(self):
        """Align stored expiry and attributable transaction projections with the server date.

        The live predicate is expiry_date < today, the same rule as eligibility.
        A document expiring today stays current and is not part of the batch.
        Keyset pages of 1,000 include inactive rows and always advance by id.
        """
        if "plasticos.document" not in self.env:
            _logger.debug("plasticos.document not installed, skipping.")
            return
        document_model = self.env["plasticos.document"].with_context(active_test=False)
        today = document_model._evidence_today()
        newly_expired = self._recompute_expiry_keyset(
            document_model,
            [
                ("expiry_date", "!=", False),
                ("expiry_date", "<", today),
                ("is_expired", "=", False),
            ],
        )
        corrected = self._recompute_expiry_keyset(
            document_model,
            [
                ("is_expired", "=", True),
                "|",
                ("expiry_date", "=", False),
                ("expiry_date", ">=", today),
            ],
        )
        if newly_expired or corrected:
            _logger.info(
                "Midnight document expiry projected %s newly expired and corrected %s rows.",
                newly_expired,
                corrected,
            )

    def _recompute_expiry_keyset(self, document_model, domain):
        last_id = 0
        touched = 0
        while True:
            batch = document_model.search(
                [*domain, ("id", ">", last_id)],
                order="id ASC",
                limit=_EXPIRY_KEYSET_LIMIT,
            )
            if not batch:
                return touched
            last_id = batch[-1].id
            batch._compute_is_expired()
            self._project_named_transactions(batch)
            self.env.flush_all()
            touched += len(batch)

    def _project_named_transactions(self, documents):
        """Recompute stored status only for transactions the evidence already names."""
        transactions = self._named_transactions(documents)
        if not transactions:
            return
        if hasattr(transactions, "_compute_missing_doc_flags"):
            transactions._compute_missing_doc_flags()
        if hasattr(transactions, "_compute_compliance"):
            transactions._compute_compliance()

    def _named_transactions(self, documents):
        tx_model = self.env["plasticos.transaction"]
        ids = set()
        for document in documents:
            named = self._one_named_transaction(tx_model, document)
            if named:
                ids.add(named)
        return tx_model.browse(sorted(ids)).exists()

    def _one_named_transaction(self, tx_model, document):
        if document.transaction_id:
            return document.transaction_id.id
        if document.res_model == "plasticos.transaction" and document.res_id:
            return document.res_id
        field_name = _UNIQUE_SUBJECT_FIELDS.get(document.res_model)
        if not field_name or field_name not in tx_model._fields or not document.res_id:
            if document.res_model in {"stock.picking", *_UNIQUE_SUBJECT_FIELDS}:
                _logger.info(
                    "UNKNOWN transaction attribution for document %s on %s,%s.",
                    document.id,
                    document.res_model,
                    document.res_id,
                )
            return None
        value = [document.res_id] if field_name == "purchase_order_ids" else document.res_id
        operator = "in" if field_name == "purchase_order_ids" else "="
        found = tx_model.search([(field_name, operator, value)])
        if len(found) == 1:
            return found.id
        if len(found) > 1:
            _logger.info(
                "UNKNOWN transaction attribution for document %s; %s transactions match.",
                document.id,
                len(found),
            )
        return None

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PlasticosDocument(models.Model):
    _name = "plasticos.document"
    _description = "Plasticos Document"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)

    attachment_id = fields.Many2one("ir.attachment", required=True)
    tag_id = fields.Many2one("plasticos.document.tag", required=True)

    verified = fields.Boolean(default=False)
    verified_by = fields.Many2one("res.users")
    verified_at = fields.Datetime()

    override = fields.Boolean(default=False)
    override_reason = fields.Text()

    active = fields.Boolean(default=True)

    # ── Expiry Tracking ────────────────────────────────────────────
    x_expiry_date = fields.Date(
        string="Expiry Date",
        help="Date after which this document is no longer valid.",
    )
    x_is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        store=True,
        help="Computed flag indicating whether the document has expired.",
    )

    # ── Versioning ─────────────────────────────────────────────────
    x_version = fields.Integer(
        string="Version",
        default=1,
        help="Document version number. Incremented on re-upload.",
    )
    x_superseded_by = fields.Many2one(
        "plasticos.document",
        string="Superseded By",
        help="Reference to the newer version of this document.",
    )
    x_is_current = fields.Boolean(
        string="Current Version",
        default=True,
        help="Whether this is the current (latest) version of the document.",
    )

    # ── Transaction Link ───────────────────────────────────────────
    x_transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        help="Link this document to a specific transaction.",
    )

    # ── Document Category ──────────────────────────────────────────
    x_doc_category = fields.Selection(
        [
            ("supplier", "Supplier Document"),
            ("carrier", "Carrier Document"),
            ("buyer", "Buyer Document"),
            ("internal", "Internal Document"),
        ],
        string="Document Category",
        help="Classification of the document by party responsible.",
    )

    @api.depends("x_expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.today()
        for rec in self:
            if rec.x_expiry_date:
                rec.x_is_expired = rec.x_expiry_date < today
            else:
                rec.x_is_expired = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._trigger_transaction_recompute(records)
        return records

    def write(self, vals):
        result = super().write(vals)
        # Recompute if tag or active status changed (affects missing doc flags)
        if "tag_id" in vals or "active" in vals or "x_transaction_id" in vals:
            self._trigger_transaction_recompute(self)
        return result

    def unlink(self):
        # Capture transactions before delete
        transactions = self._get_related_transactions(self)
        result = super().unlink()
        # Trigger recompute after delete
        if transactions:
            transactions._compute_missing_doc_flags()
        return result

    def _trigger_transaction_recompute(self, records):
        """Trigger recomputation of doc-related fields on related transactions.

        R2 fix: Ensures real-time updates when documents are created/modified.
        Issue 3 fix: Also recomputes compliance_status.
        """
        transactions = self._get_related_transactions(records)
        if transactions:
            transactions._compute_missing_doc_flags()
            # Issue 3 fix: compliance_status depends on documents too
            if hasattr(transactions, "_compute_compliance"):
                transactions._compute_compliance()

    def _get_related_transactions(self, records):
        """Find all transactions related to the given document records.

        Handles both direct link (x_transaction_id) and polymorphic link (res_model/res_id).
        """
        tx_model = self.env["plasticos.transaction"]
        tx_ids = set()

        for record in records:
            # Direct link
            if record.x_transaction_id:
                tx_ids.add(record.x_transaction_id.id)

            # Polymorphic link: document on transaction directly
            if record.res_model == "plasticos.transaction":
                tx_ids.add(record.res_id)

            # Polymorphic link: document on load -> find transaction
            elif record.res_model == "plasticos.load":
                tx = tx_model.search([("load_id", "=", record.res_id)], limit=1)
                if tx:
                    tx_ids.add(tx.id)

            # Polymorphic link: document on sale order -> find transaction
            elif record.res_model == "sale.order":
                tx = tx_model.search([("sale_order_id", "=", record.res_id)], limit=1)
                if tx:
                    tx_ids.add(tx.id)

        return tx_model.browse(list(tx_ids)) if tx_ids else tx_model

    def action_verify(self):
        for rec in self:
            rec.verified = True
            rec.verified_by = self.env.user.id
            rec.verified_at = fields.Datetime.now()

    def action_override(self, reason=None):
        """Override document verification.

        Args:
            reason: Optional override reason string. When called from a
                    button action (no positional args), the reason can be
                    set later via the ``override_reason`` field.
        """
        if not self.env.user.has_group("plasticos_documents.group_documents_manager"):
            raise UserError("Not authorized to override.")
        for rec in self:
            rec.override = True
            if reason:
                rec.override_reason = reason

    def action_supersede(self, new_doc_id):
        """Mark this document as superseded by a newer version."""
        for rec in self:
            rec.x_is_current = False
            rec.x_superseded_by = new_doc_id
            _logger.info(
                "Document %s (v%d) superseded by document %s",
                rec.name,
                rec.x_version,
                new_doc_id,
            )

    @api.model
    def _cron_compliance_audit(self):
        """Batch compliance audit: flag verified documents that have expired.

        Called by the scheduled action ``cron_document_compliance_check``.
        Resets ``verified`` on any document whose ``x_is_expired`` is True
        so that the compliance service no longer considers them valid.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_documents.cron_document_compliance_check"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping compliance audit cron: lock is already held.")
            return

        try:
            expired = self.search(
                [
                    ("verified", "=", True),
                    ("x_is_expired", "=", True),
                    ("active", "=", True),
                ],
                order="write_date ASC, id ASC",
                limit=500,
            )
            if expired:
                expired.write({"verified": False})
                _logger.info("Compliance audit: reset verified flag on %d expired documents.", len(expired))
            else:
                _logger.info("Compliance audit: no expired verified documents found.")
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_document_compliance_check"]
            )

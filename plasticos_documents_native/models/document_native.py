"""Extend Odoo Enterprise ``documents.document`` with plastics-specific fields.

This module adds relational links to the Plasticos domain models so that
every native document can be associated with a polymer type, load, transaction,
or intake record.  The native ``documents.document`` model already provides
``attachment_id``, ``folder_id``, ``tag_ids``, ``res_model``, ``res_id``,
``partner_id``, and ``owner_id`` — we do **not** duplicate any of those.

Fields prefixed with ``x_`` follow the Odoo convention for extension fields
to avoid future collisions with upstream Enterprise changes.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DocumentNative(models.Model):
    """Plastics-specific extension of the native Enterprise document."""

    _inherit = "documents.document"

    # ── Plastics Domain Links ────────────────────────────────
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer Type",
        index=True,
        tracking=True,
        help="Primary polymer type referenced in this document.",
    )
    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        index=True,
        tracking=True,
        help="Load this document is associated with (BOL, scale ticket).",
    )
    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        tracking=True,
        help="Transaction this document belongs to.",
    )
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        index=True,
        tracking=True,
        help="Intake record this document originated from.",
    )

    # ── Classification ───────────────────────────────────────
    doc_type = fields.Selection(
        [
            ("bol", "Bill of Lading"),
            ("invoice", "Invoice / Vendor Bill"),
            ("scale_ticket", "Scale Ticket"),
            ("loading_pic", "Loading Pic"),
            ("customer_order", "Customer Order (CO)"),
            ("certification", "Certification"),
            ("permit", "Permit"),
            ("lab_report", "Lab / Test Report"),
            ("photo", "Photo / Image"),
            ("contract", "Contract"),
            ("correspondence", "Correspondence"),
            ("other", "Other"),
        ],
        string="Document Type",
        index=True,
        tracking=True,
        help="Plastics-specific document classification.",
    )

    # ── Verification Workflow ────────────────────────────────
    verified = fields.Boolean(
        string="Verified",
        default=False,
        tracking=True,
    )
    verified_by = fields.Many2one(
        "res.users",
        string="Verified By",
        readonly=True,
    )
    verified_at = fields.Datetime(
        string="Verified At",
        readonly=True,
    )

    # ── Override (manager-only) ──────────────────────────────
    override = fields.Boolean(
        string="Override",
        default=False,
        tracking=True,
    )
    override_reason = fields.Text(
        string="Override Reason",
    )

    # ── Sync Reference ───────────────────────────────────────
    plasticos_doc_id = fields.Many2one(
        "plasticos.document",
        string="Plasticos Document",
        readonly=True,
        help="Link to the legacy plasticos.document record for backward compatibility.",
    )

    # ── Actions ──────────────────────────────────────────────
    def action_verify(self):
        """Mark the document as verified by the current user."""
        for rec in self:
            rec.write(
                {
                    "verified": True,
                    "verified_by": self.env.user.id,
                    "verified_at": fields.Datetime.now(),
                }
            )
        _logger.info(
            "Documents verified: %s",
            ", ".join(str(r.id) for r in self),
        )

    def action_override(self):
        """Mark the document as overridden (requires manager group)."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            from odoo.exceptions import UserError

            raise UserError("Only administrators can override documents.")
        self.write({"override": True})
        _logger.info(
            "Document %s overridden by %s",
            self.id,
            self.env.user.login,
        )

    # ── Auto-Link Helper ─────────────────────────────────────
    @api.model
    def _auto_link_partner(self, document):
        """Attempt to match the document's partner to a transaction or load.

        Called after AI auto-sort populates ``partner_id``.  If the document
        has a partner but no transaction/load link, search for the most recent
        open transaction for that partner and link it.
        """
        if not document.partner_id:
            return
        if document.transaction_id or document.load_id:
            return

        tx = self.env["plasticos.transaction"].search(
            [
                ("partner_id", "=", document.partner_id.id),
                ("state", "in", ["draft", "in_progress", "pending"]),
            ],
            order="create_date desc",
            limit=1,
        )
        if tx:
            vals = {"transaction_id": tx.id}
            if tx.load_id:
                vals["load_id"] = tx.load_id.id
            document.write(vals)
            _logger.info(
                "Auto-linked document %s to transaction %s (partner %s)",
                document.id,
                tx.id,
                document.partner_id.name,
            )

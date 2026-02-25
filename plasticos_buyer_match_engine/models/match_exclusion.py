"""
Match Exclusion Model (Enhancement #11)
Buyer-supplier exclusion list with expiry for QC disputes, legal holds, declined quality.
"""

from odoo import api, fields, models


class PlasticosMatchExclusion(models.Model):
    _name = "plasticos.match.exclusion"
    _description = "Buyer-Supplier Match Exclusion"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    supplier_partner_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="Supplier partner to exclude from matching.",
    )
    buyer_partner_id = fields.Many2one(
        "res.partner",
        string="Buyer",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="Buyer partner to exclude from matching.",
    )

    reason = fields.Selection(
        [
            ("qc_dispute", "QC Dispute"),
            ("legal_hold", "Legal Hold"),
            ("quality_declined", "Quality Declined"),
            ("payment_issue", "Payment Issue"),
            ("logistics_issue", "Logistics Issue"),
            ("other", "Other"),
        ],
        required=True,
        tracking=True,
        help="Reason for the exclusion.",
    )
    reason_notes = fields.Text(
        string="Notes",
        help="Additional details about the exclusion reason.",
    )

    exclusion_type = fields.Selection(
        [
            ("permanent", "Permanent"),
            ("temporary", "Temporary"),
        ],
        required=True,
        default="temporary",
        tracking=True,
        help="Permanent exclusions never expire. Temporary exclusions expire on the expiry date.",
    )
    expiry_date = fields.Date(
        string="Expiry Date",
        help="For temporary exclusions: date when the exclusion automatically expires.",
    )

    active = fields.Boolean(default=True, tracking=True)

    created_by_uid = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.uid,
        readonly=True,
    )

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _sql_constraints = [
        (
            "unique_pair",
            "unique(supplier_partner_id, buyer_partner_id)",
            "An exclusion already exists for this supplier-buyer pair.",
        ),
    ]

    # ═════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════

    @api.constrains("exclusion_type", "expiry_date")
    def _check_expiry_date(self):
        for rec in self:
            if rec.exclusion_type == "temporary" and not rec.expiry_date:
                raise models.ValidationError("Temporary exclusions require an expiry date.")

    @api.constrains("supplier_partner_id", "buyer_partner_id")
    def _check_different_partners(self):
        for rec in self:
            if rec.supplier_partner_id == rec.buyer_partner_id:
                raise models.ValidationError("Supplier and buyer must be different partners.")

    # ═════════════════════════════════════════════════════════
    # Business Logic
    # ═════════════════════════════════════════════════════════

    @api.model
    def get_excluded_buyer_ids(self, supplier_partner_id):
        """Get list of buyer IDs excluded for a given supplier.

        Args:
            supplier_partner_id: res.partner ID of the supplier

        Returns:
            list[int]: IDs of buyers excluded for this supplier
        """
        exclusions = self.search(
            [
                ("supplier_partner_id", "=", supplier_partner_id),
                ("active", "=", True),
                "|",
                ("exclusion_type", "=", "permanent"),
                "&",
                ("exclusion_type", "=", "temporary"),
                ("expiry_date", ">=", fields.Date.today()),
            ]
        )
        return exclusions.mapped("buyer_partner_id").ids

    @api.model
    def is_pair_excluded(self, supplier_partner_id, buyer_partner_id):
        """Check if a supplier-buyer pair is currently excluded.

        Args:
            supplier_partner_id: res.partner ID of the supplier
            buyer_partner_id: res.partner ID of the buyer

        Returns:
            bool: True if pair is excluded, False otherwise
        """
        return (
            self.search_count(
                [
                    ("supplier_partner_id", "=", supplier_partner_id),
                    ("buyer_partner_id", "=", buyer_partner_id),
                    ("active", "=", True),
                    "|",
                    ("exclusion_type", "=", "permanent"),
                    "&",
                    ("exclusion_type", "=", "temporary"),
                    ("expiry_date", ">=", fields.Date.today()),
                ]
            )
            > 0
        )

    # ═════════════════════════════════════════════════════════
    # Cron: Expire Temporary Exclusions
    # ═════════════════════════════════════════════════════════

    @api.model
    def _cron_expire_temporary_exclusions(self):
        """Deactivate temporary exclusions past their expiry date.

        Called daily by scheduled action.
        """
        expired = self.search(
            [
                ("exclusion_type", "=", "temporary"),
                ("expiry_date", "<", fields.Date.today()),
                ("active", "=", True),
            ]
        )
        if expired:
            expired.write({"active": False})
            return f"Expired {len(expired)} temporary exclusions."
        return "No exclusions to expire."

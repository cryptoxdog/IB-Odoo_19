import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PlasticosAutomationConfig(models.Model):
    _name = "plasticos.automation.config"
    _description = "PlasticOS Automation Configuration"
    _rec_name = "name"

    name = fields.Char(
        default="Environment Configuration",
        required=True,
    )

    # ── Sale Approval ──────────────────────────────────────────────
    sale_approval_threshold = fields.Float(
        string="Sale Approval Threshold",
        required=True,
        default=10000.0,
        help="Orders exceeding this amount require approval before confirmation.",
    )

    # ── Invoice Reminder ───────────────────────────────────────────
    invoice_overdue_days = fields.Integer(
        string="Invoice Overdue Days",
        required=True,
        default=30,
        help="Number of days past due date before an overdue reminder is sent.",
    )

    # ── Contract Renewal ───────────────────────────────────────────
    contract_alert_days_before = fields.Integer(
        string="Contract Alert Days Before",
        required=True,
        default=30,
        help="Number of days before contract end date to trigger a renewal alert.",
    )

    # ── Stock Alert ────────────────────────────────────────────────
    stock_threshold_default = fields.Float(
        string="Default Stock Threshold",
        required=True,
        default=100.0,
        help="Default minimum stock level. Per-product overrides take precedence.",
    )

    active = fields.Boolean(default=True)

    _check_singleton_active = models.Constraint(
        "EXCLUDE (active WITH =) WHERE (active = true)",
        "Only one active automation configuration record is allowed.",
    )

    @api.constrains("active")
    def _check_singleton(self):
        """Ensure only one active configuration record exists."""
        for record in self:
            if record.active:
                existing = self.search(
                    [
                        ("active", "=", True),
                        ("id", "!=", record.id),
                    ]
                )
                if existing:
                    raise ValidationError(
                        "Only one active automation configuration record is allowed. "
                        "Deactivate the existing record before creating a new one."
                    )

    @api.model
    def get_config(self):
        """Return the singleton configuration record.

        Raises ValidationError if no active configuration is found.
        This method is called by all automation crons to retrieve
        environment-driven thresholds.
        """
        config = self.search([("active", "=", True)], limit=1)
        if not config:
            raise ValidationError(
                "Automation configuration not defined. Please configure PlasticOS Automation settings."
            )
        return config

    @api.constrains(
        "sale_approval_threshold",
        "invoice_overdue_days",
        "contract_alert_days_before",
        "stock_threshold_default",
    )
    def _check_positive_values(self):
        """Ensure all threshold values are non-negative."""
        for record in self:
            if record.sale_approval_threshold < 0:
                raise ValidationError("Sale approval threshold must be non-negative.")
            if record.invoice_overdue_days < 0:
                raise ValidationError("Invoice overdue days must be non-negative.")
            if record.contract_alert_days_before < 0:
                raise ValidationError("Contract alert days must be non-negative.")
            if record.stock_threshold_default < 0:
                raise ValidationError("Default stock threshold must be non-negative.")

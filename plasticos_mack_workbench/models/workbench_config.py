"""Versioned, company-scoped reviewer policy for the Mack workbench."""

from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PlasticosMackWorkbenchConfig(models.Model):
    """One active Odoo-native Mack reviewer route per company.

    The review-request caller never supplies a reviewer.  This record is the
    server-owned policy that resolves the eligible internal reviewer and whose
    ``write_date`` becomes the route-policy revision recorded on each receipt.
    """

    _name = "plasticos.mack.workbench.config"
    _description = "Mack Workbench Configuration"
    _check_company_auto = True
    _rec_name = "name"
    _order = "company_id, id"

    name = fields.Char(required=True, default="Mack Workbench Configuration")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )
    internal_reviewer_id = fields.Many2one(
        "res.users",
        string="Internal Reviewer",
        required=True,
        domain="[('share', '=', False), ('active', '=', True)]",
        ondelete="restrict",
        help="Active internal Odoo user who receives governed Mack review activities for this company.",
    )
    active = fields.Boolean(default=True)

    @api.constrains("active", "company_id")
    def _check_one_active_configuration_per_company(self):
        for record in self:
            if record.active and self.search_count(
                [
                    ("company_id", "=", record.company_id.id),
                    ("active", "=", True),
                    ("id", "!=", record.id),
                ]
            ):
                raise ValidationError(_("Only one active Mack Workbench configuration is allowed per company."))

    @api.constrains("internal_reviewer_id")
    def _check_internal_reviewer(self):
        for record in self:
            reviewer = record.internal_reviewer_id
            if not reviewer or reviewer.share or not reviewer.active:
                raise ValidationError(_("Mack Workbench reviewer must be an active internal Odoo user."))

    @api.model
    def get_active_config(self, *, company=None):
        """Return the sole active route for a company or fail closed."""
        company = company or self.env.company
        config = self.search(
            [("company_id", "=", company.id), ("active", "=", True)],
            limit=1,
        )
        if not config:
            raise ValidationError(_("Mack Workbench routing is not configured for company %s.") % company.display_name)
        if (
            not config.internal_reviewer_id
            or config.internal_reviewer_id.share
            or not config.internal_reviewer_id.active
        ):
            raise ValidationError(_("Mack Workbench routing has no active internal reviewer."))
        return config

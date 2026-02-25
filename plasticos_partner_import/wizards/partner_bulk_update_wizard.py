"""
Partner Bulk Update Wizard
Bulk update fields on multiple res.partner records at once.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PartnerBulkUpdateWizard(models.TransientModel):
    _name = "plasticos.partner.bulk.update.wizard"
    _description = "Bulk Update Partners"

    action_type = fields.Selection(
        [
            ("assign_salesperson", "Assign Salesperson"),
            ("assign_category", "Assign Category/Tags"),
            ("set_private", "Set Private Flag"),
            ("set_company_type", "Set Company Type"),
            ("assign_payment_terms", "Assign Payment Terms"),
        ],
        string="Action",
        required=True,
        default="assign_salesperson",
    )

    # Salesperson assignment
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        domain=[("share", "=", False)],
    )

    # Category/Tags assignment
    category_ids = fields.Many2many(
        "res.partner.category",
        string="Categories/Tags",
    )
    category_mode = fields.Selection(
        [
            ("add", "Add to existing"),
            ("replace", "Replace all"),
        ],
        string="Category Mode",
        default="add",
    )

    # Private flag
    x_private = fields.Boolean(
        string="Private Partner",
        help="Mark partners as private (restricted visibility).",
    )

    # Company type
    company_type = fields.Selection(
        [
            ("company", "Company"),
            ("person", "Individual"),
        ],
        string="Company Type",
    )

    # Payment terms
    property_payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Customer Payment Terms",
    )
    property_supplier_payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Vendor Payment Terms",
    )

    # Common fields
    reason = fields.Text(
        string="Reason",
        required=True,
        help="Reason for the bulk update (will be logged in chatter).",
    )
    partner_ids = fields.Many2many(
        "res.partner",
        string="Partners",
        readonly=True,
    )
    partner_count = fields.Integer(
        compute="_compute_partner_count",
        string="Partner Count",
    )

    # Stats
    company_count = fields.Integer(
        compute="_compute_stats",
        string="Companies",
    )
    contact_count = fields.Integer(
        compute="_compute_stats",
        string="Contacts",
    )

    @api.depends("partner_ids")
    def _compute_partner_count(self):
        for rec in self:
            rec.partner_count = len(rec.partner_ids)

    @api.depends("partner_ids")
    def _compute_stats(self):
        for rec in self:
            rec.company_count = len(rec.partner_ids.filtered(lambda p: p.is_company))
            rec.contact_count = len(rec.partner_ids.filtered(lambda p: not p.is_company))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["partner_ids"] = [(6, 0, active_ids)]
        return res

    def action_execute(self):
        """Execute the selected bulk action."""
        self.ensure_one()
        if not self.partner_ids:
            raise UserError(_("No partners selected."))

        if self.action_type == "assign_salesperson":
            return self._action_assign_salesperson()
        elif self.action_type == "assign_category":
            return self._action_assign_category()
        elif self.action_type == "set_private":
            return self._action_set_private()
        elif self.action_type == "set_company_type":
            return self._action_set_company_type()
        elif self.action_type == "assign_payment_terms":
            return self._action_assign_payment_terms()

    def _action_assign_salesperson(self):
        """Assign salesperson to selected partners."""
        if not self.user_id:
            raise UserError(_("Please select a salesperson."))

        updated = 0
        for partner in self.partner_ids:
            old_user = partner.user_id.name if partner.user_id else "None"
            partner.user_id = self.user_id
            partner.message_post(
                body=_(
                    "Salesperson changed from <b>%(old)s</b> to <b>%(new)s</b><br/>"
                    "Reason: %(reason)s<br/>"
                    "Updated by: %(user)s (Bulk Update)"
                )
                % {
                    "old": old_user,
                    "new": self.user_id.name,
                    "reason": self.reason,
                    "user": self.env.user.name,
                },
                message_type="notification",
            )
            updated += 1

        return self._return_notification(_("%d partner(s) assigned to salesperson '%s'") % (updated, self.user_id.name))

    def _action_assign_category(self):
        """Assign categories/tags to selected partners."""
        if not self.category_ids:
            raise UserError(_("Please select at least one category/tag."))

        updated = 0
        tag_names = ", ".join(self.category_ids.mapped("name"))

        for partner in self.partner_ids:
            old_tags = ", ".join(partner.category_id.mapped("name")) or "None"

            if self.category_mode == "replace":
                partner.category_id = self.category_ids
            else:  # add
                partner.category_id = [(4, cat.id) for cat in self.category_ids]

            new_tags = ", ".join(partner.category_id.mapped("name"))
            partner.message_post(
                body=_(
                    "Categories %(mode)s: <b>%(tags)s</b><br/>"
                    "Before: %(old)s<br/>"
                    "After: %(new)s<br/>"
                    "Reason: %(reason)s<br/>"
                    "Updated by: %(user)s (Bulk Update)"
                )
                % {
                    "mode": "replaced with" if self.category_mode == "replace" else "added",
                    "tags": tag_names,
                    "old": old_tags,
                    "new": new_tags,
                    "reason": self.reason,
                    "user": self.env.user.name,
                },
                message_type="notification",
            )
            updated += 1

        return self._return_notification(_("%d partner(s) updated with categories: %s") % (updated, tag_names))

    def _action_set_private(self):
        """Set private flag on selected partners."""
        updated = 0
        status = "Private" if self.x_private else "Public"

        for partner in self.partner_ids:
            # Check if field exists (from plasticos_security_base)
            if hasattr(partner, "x_private"):
                old_status = "Private" if partner.x_private else "Public"
                partner.x_private = self.x_private
                partner.message_post(
                    body=_(
                        "Privacy changed from <b>%(old)s</b> to <b>%(new)s</b><br/>"
                        "Reason: %(reason)s<br/>"
                        "Updated by: %(user)s (Bulk Update)"
                    )
                    % {
                        "old": old_status,
                        "new": status,
                        "reason": self.reason,
                        "user": self.env.user.name,
                    },
                    message_type="notification",
                )
                updated += 1
            else:
                raise UserError(
                    _("The x_private field is not available. Please install the plasticos_security_base module.")
                )

        return self._return_notification(_("%d partner(s) marked as %s") % (updated, status))

    def _action_set_company_type(self):
        """Set company type on selected partners."""
        if not self.company_type:
            raise UserError(_("Please select a company type."))

        updated = 0
        for partner in self.partner_ids:
            old_type = "Company" if partner.is_company else "Individual"
            is_company = self.company_type == "company"
            partner.is_company = is_company
            new_type = "Company" if is_company else "Individual"

            partner.message_post(
                body=_(
                    "Company type changed from <b>%(old)s</b> to <b>%(new)s</b><br/>"
                    "Reason: %(reason)s<br/>"
                    "Updated by: %(user)s (Bulk Update)"
                )
                % {
                    "old": old_type,
                    "new": new_type,
                    "reason": self.reason,
                    "user": self.env.user.name,
                },
                message_type="notification",
            )
            updated += 1

        return self._return_notification(_("%d partner(s) set to type '%s'") % (updated, self.company_type))

    def _action_assign_payment_terms(self):
        """Assign payment terms to selected partners."""
        if not self.property_payment_term_id and not self.property_supplier_payment_term_id:
            raise UserError(_("Please select at least one payment term."))

        updated = 0
        for partner in self.partner_ids:
            changes = []

            if self.property_payment_term_id:
                old_term = partner.property_payment_term_id.name if partner.property_payment_term_id else "None"
                partner.property_payment_term_id = self.property_payment_term_id
                changes.append(
                    _("Customer payment term: %(old)s → %(new)s")
                    % {"old": old_term, "new": self.property_payment_term_id.name}
                )

            if self.property_supplier_payment_term_id:
                old_term = (
                    partner.property_supplier_payment_term_id.name
                    if partner.property_supplier_payment_term_id
                    else "None"
                )
                partner.property_supplier_payment_term_id = self.property_supplier_payment_term_id
                changes.append(
                    _("Vendor payment term: %(old)s → %(new)s")
                    % {"old": old_term, "new": self.property_supplier_payment_term_id.name}
                )

            if changes:
                partner.message_post(
                    body=_(
                        "Payment terms updated:<br/>%(changes)s<br/>"
                        "Reason: %(reason)s<br/>"
                        "Updated by: %(user)s (Bulk Update)"
                    )
                    % {
                        "changes": "<br/>".join(changes),
                        "reason": self.reason,
                        "user": self.env.user.name,
                    },
                    message_type="notification",
                )
                updated += 1

        return self._return_notification(_("%d partner(s) payment terms updated") % updated)

    def _return_notification(self, message):
        """Return a notification action."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Update Complete"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

from odoo import _, models


class PlasticosPartnerBulkUpdateWizardPrivacy(models.Model):
    """Partner privacy writes stay in the module that owns is_private."""

    _inherit = "plasticos.partner.bulk.update.wizard"

    def _apply_partner_privacy(self, partner):
        old_status = "Private" if partner.is_private else "Public"
        partner.is_private = self.is_private
        status = "Private" if self.is_private else "Public"
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

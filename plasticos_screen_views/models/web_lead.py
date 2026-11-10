"""Activity follow-ups on a web lead, including after an intake exists."""

from __future__ import annotations

from odoo import models

# Exact fields declared on mail.activity.mixin. A prefix match would let a later field past the guard.
_ACTIVITY_MIXIN_FIELDS = frozenset(
    {
        "activity_ids",
        "activity_state",
        "activity_user_id",
        "activity_type_id",
        "activity_type_icon",
        "activity_date_deadline",
        "my_activity_date_deadline",
        "activity_summary",
        "activity_exception_decoration",
        "activity_exception_icon",
    }
)


class PlasticosWebLead(models.Model):
    _inherit = ["plasticos.web.lead", "mail.activity.mixin"]
    _description = "Web Lead"

    def write(self, vals):
        """Pass activity fields around the intake guard. Every other field still hits that guard."""
        if vals and set(vals) <= _ACTIVITY_MIXIN_FIELDS:
            from odoo.addons.plasticos_web_leads.models.web_lead import PlasticosWebLead as GuardedLead

            return super(GuardedLead, self).write(vals)
        return super().write(vals)

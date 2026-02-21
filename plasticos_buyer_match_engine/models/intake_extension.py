from odoo import _, models
from odoo.exceptions import UserError

from ..services.matcher import PlasticosMatcher


class PlasticosIntake(models.Model):
    _inherit = "plasticos.intake"

    def action_match_to_buyers(self):
        """Run the deterministic buyer match engine for selected intakes.

        Requires a linked material_profile_id.  Results are written to
        plasticos.match.result and displayed in a list/form window.
        """
        for record in self:
            if not record.material_profile_id:
                raise UserError(
                    _(
                        "Intake '%s' has no material profile. " "Link a material profile before matching.",
                        record.name,
                    )
                )
            matcher = PlasticosMatcher(self.env)
            matcher.match(record)

        return {
            "type": "ir.actions.act_window",
            "name": _("Match Results"),
            "res_model": "plasticos.match.result",
            "view_mode": "list,form",
            "domain": [("intake_id", "in", self.ids)],
            "target": "current",
        }

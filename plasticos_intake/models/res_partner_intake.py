"""Extend res.partner with intake-related fields and actions.

This module adds intake navigation and creation capabilities to
res.partner. The extension lives here (in plasticos_intake)
rather than in plasticos_material_profile to avoid circular dependencies.
"""

from odoo import api, fields, models


class ResPartnerIntake(models.Model):
    """Add intake-related fields and actions to partner."""

    _inherit = "res.partner"

    # ── Navigation: Intake Count ──────────────────────────────────
    intake_count = fields.Integer(
        string="Intakes",
        compute="_compute_intake_count",
    )

    @api.depends()
    def _compute_intake_count(self):
        """Count intakes linked to this partner as supplier or as facility, each intake once.

        Two grouped reads replace one OR search per partner: intakes by partner,
        then intakes by facility whose partner is not that same facility (those
        were already counted by the first read).
        """
        Intake = self.env["plasticos.intake"]
        stored_ids = [record_id for record_id in self.ids if isinstance(record_id, int) and record_id > 0]
        counts = dict.fromkeys(stored_ids, 0)
        if stored_ids:
            for partner, count in Intake._read_group([("partner_id", "in", stored_ids)], ["partner_id"], ["__count"]):
                counts[partner.id] = counts.get(partner.id, 0) + count
            for facility, partner, count in Intake._read_group(
                [("facility_id", "in", stored_ids)], ["facility_id", "partner_id"], ["__count"]
            ):
                if partner != facility:
                    counts[facility.id] = counts.get(facility.id, 0) + count
        for rec in self:
            rec.intake_count = counts.get(rec.id, 0) if isinstance(rec.id, int) else 0

    # ── Navigation Actions ────────────────────────────────────────
    def action_view_intakes(self):
        """Navigate to intakes for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes - {self.name}",
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("partner_id", "=", self.id),
                ("facility_id", "=", self.id),
            ],
        }

    def action_create_intake(self):
        """Create a new intake for this facility."""
        self.ensure_one()
        # Determine company and facility
        if self.parent_id:
            # This is a facility under a parent company
            company_id = self.parent_id.id
            facility_id = self.id
        else:
            # Standalone company (both HQ and facility)
            company_id = self.id
            facility_id = self.id

        return {
            "type": "ir.actions.act_window",
            "name": f"New Intake - {self.name}",
            "res_model": "plasticos.intake",
            "view_mode": "form",
            "context": {
                "default_partner_id": company_id,
                "default_facility_id": facility_id,
            },
        }

"""Start a converge v2 enrichment run from a material or facility profile.

No stored field is added to either profile. The run carries the target
(``material_profile_id`` / ``facility_profile_id``) and takes its partner from
the profile (ADR-012 amendment 2026-11-13).
"""

from odoo import _, models
from odoo.exceptions import UserError

ENRICHMENT_RUN = "plasticos.enrichment.run"


def _open_new_run(profile, target_field):
    profile.ensure_one()
    if not profile.partner_id:
        raise UserError(_("A facility profile with no partner (lead-owned) cannot be enriched."))
    run = profile.env[ENRICHMENT_RUN].create({"partner_id": profile.partner_id.id, target_field: profile.id})
    return {
        "type": "ir.actions.act_window",
        "res_model": ENRICHMENT_RUN,
        "res_id": run.id,
        "view_mode": "form",
        "target": "current",
    }


class PlasticosMaterialProfileEnrichment(models.Model):
    _inherit = "plasticos.material.profile"

    def action_start_enrichment_run(self):
        """Create a draft enrichment run targeting this material profile and open it."""
        return _open_new_run(self, "material_profile_id")


class PlasticosFacilityProfileEnrichment(models.Model):
    _inherit = "plasticos.facility.profile"

    def action_start_enrichment_run(self):
        """Create a draft enrichment run targeting this facility profile and open it."""
        return _open_new_run(self, "facility_profile_id")

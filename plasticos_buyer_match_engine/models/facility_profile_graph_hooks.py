"""Write-through hooks for facility profile — trigger Neo4j graph sync.

Moved from Buyer Matching Using Neo4j/facility_profile_hooks.py;
realigned to call plasticos.graph.service sync (no vector/embedding).
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResPartnerGraphHooks(models.Model):
    """Extend res.partner to trigger graph sync when facility data changes."""

    _inherit = "res.partner"

    def write(self, vals):
        result = super().write(vals)
        trigger = {"name", "street", "city", "state_id", "country_id", "partner_latitude", "partner_longitude"}
        if trigger & set(vals.keys()):
            for partner in self:
                if partner.facility_profile_ids:
                    _trigger_facility_graph_sync(self.env)
        return result


class FacilityProfileGraphHooks(models.Model):
    """Extend plasticos.facility.profile to sync Facility nodes to Neo4j on change."""

    _inherit = "plasticos.facility.profile"

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)
        _trigger_facility_graph_sync(self.env)
        return profiles

    def write(self, vals):
        result = super().write(vals)
        sync_trigger = {
            "freeform_notes",
            "application_notes",
            "process_type",
            "can_remove_metal",
            "can_filter_fr",
            "min_lot_size_lbs",
            "max_lot_size_lbs",
            "partner_id",
        }
        if sync_trigger & set(vals.keys()):
            _trigger_facility_graph_sync(self.env)
        return result


def _trigger_facility_graph_sync(env):
    """Run facility graph sync if graph service is available."""
    if "plasticos.graph.service" not in env:
        return
    try:
        # sudo: graph sync runs in background, may be triggered by any user
        env["plasticos.graph.service"].sudo().sync_facility_nodes(trigger="facility_write")
    except Exception as exc:
        _logger.warning("Graph sync (facility) skipped: %s", exc)

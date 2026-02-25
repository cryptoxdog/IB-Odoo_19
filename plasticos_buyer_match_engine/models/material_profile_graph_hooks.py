"""Write-through hooks for material profile — trigger Neo4j graph sync.

Moved from Buyer Matching Using Neo4j/material_profile_hooks.py;
realigned to call plasticos.graph.service sync (no vector/embedding).
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MaterialProfileGraphHooks(models.Model):
    """Extend plasticos.material.profile to sync MaterialProfile nodes to Neo4j on change."""

    _inherit = "plasticos.material.profile"

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)
        self._trigger_material_sync(profiles)
        return profiles

    def write(self, vals):
        result = super().write(vals)
        sync_trigger = {
            "polymer_id",
            "form_id",
            "color",
            "freeform_notes",
            "certification_notes",
            "min_density",
            "max_density",
            "contamination_tolerance",
            "moisture_tolerance",
            "partner_id",
        }
        if sync_trigger & set(vals.keys()):
            self._trigger_material_sync(self)
        return result

    def _trigger_material_sync(self, profiles):
        """Run material graph sync if graph service is available."""
        if "plasticos.graph.service" not in self.env:
            return
        try:
            self.env["plasticos.graph.service"].sudo().sync_material_nodes(trigger="material_write")
        except Exception as exc:
            _logger.warning("Graph sync (material) skipped: %s", exc)

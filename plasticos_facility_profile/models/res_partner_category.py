"""Company Type and Status tag groups (ADR-131 Decision B).

A root-level tag created with a Company Type name joins the Company Type group,
unless the group already holds that name. This covers tags another module
creates after this one is installed (``plasticos_crm_bridge`` ``categ_*``),
so the same name is never made twice.
"""

import logging

from odoo import api, models

from ..classification import COMPANY_TYPE_NAMES, reparent_plan

_logger = logging.getLogger(__name__)

COMPANY_TYPE_XMLID = "plasticos_facility_profile.partner_category_company_type"
STATUS_XMLID = "plasticos_facility_profile.partner_category_status"
CRM_BRIDGE = "plasticos_crm_bridge"


class ResPartnerCategory(models.Model):
    _inherit = "res.partner.category"

    @api.model_create_multi
    def create(self, vals_list):
        group = self.env.ref(COMPANY_TYPE_XMLID, raise_if_not_found=False)
        if group:
            held = set(group.child_ids.mapped("name"))
            for vals in vals_list:
                name = vals.get("name")
                if not vals.get("parent_id") and name in COMPANY_TYPE_NAMES and name not in held:
                    vals["parent_id"] = group.id
                    held.add(name)
        return super().create(vals_list)

    @api.model
    def _plasticos_ensure_company_type_tags(self):
        """Move same-name root tags into the group; create a missing name.

        A missing name is created here only when ``plasticos_crm_bridge`` is not
        installed or about to be: that module creates its own tags, and
        ``create`` above puts them in the group.
        """
        group = self.env.ref(COMPANY_TYPE_XMLID, raise_if_not_found=False)
        if not group:
            return
        existing = self.with_context(active_test=False).search([("name", "in", list(COMPANY_TYPE_NAMES))])
        rows = [(tag.id, tag.name, tag.parent_id.id) for tag in existing]
        reparent, missing = reparent_plan(rows, group.id, COMPANY_TYPE_NAMES)
        if reparent:
            self.browse(reparent).write({"parent_id": group.id})
        bridge = self.env["ir.module.module"].search(
            [("name", "=", CRM_BRIDGE), ("state", "in", ("installed", "to install", "to upgrade"))], limit=1
        )
        if missing and not bridge:
            self.create([{"name": name, "parent_id": group.id} for name in missing])
        _logger.info(
            "Company Type tags: %d moved into the group, %d created, %d left to %s",
            len(reparent),
            0 if bridge else len(missing),
            len(missing) if bridge else 0,
            CRM_BRIDGE,
        )

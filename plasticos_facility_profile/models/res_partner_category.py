"""Company Type, Trade Role and Status tag groups (ADR-131 Decision B).

A root-level tag created with a Company Type or Trade Role name joins its group,
unless the group already holds that name. This covers tags another module
creates after this one is installed (``plasticos_crm_bridge`` ``categ_*``), so
the same name is never made twice.
"""

import logging

from odoo import api, models

from ..classification import COMPANY_TYPE_NAMES, LEAD_STATUS_TAGS, TRADE_ROLE_NAMES, bind_plan, reparent_plan

_logger = logging.getLogger(__name__)

COMPANY_TYPE_XMLID = "plasticos_facility_profile.partner_category_company_type"
TRADE_ROLE_XMLID = "plasticos_facility_profile.partner_category_trade_role"
STATUS_XMLID = "plasticos_facility_profile.partner_category_status"
DO_NOT_CONTACT_XMLID = "plasticos_base.tag_do_not_contact"
# Group xmlid -> the tag names it holds.
GROUPS = {COMPANY_TYPE_XMLID: COMPANY_TYPE_NAMES, TRADE_ROLE_XMLID: TRADE_ROLE_NAMES}
CRM_BRIDGE = "plasticos_crm_bridge"
# ir.module.module states in which that module loads its own tags.
BRIDGE_LOADING_STATES = frozenset({"installed", "to install", "to upgrade"})


class ResPartnerCategory(models.Model):
    _inherit = "res.partner.category"

    @api.model_create_multi
    def create(self, vals_list):
        for xmlid, names in GROUPS.items():
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            held = set(group.child_ids.mapped("name"))
            for vals in vals_list:
                name = vals.get("name")
                if not vals.get("parent_id") and name in names and name not in held:
                    vals["parent_id"] = group.id
                    held.add(name)
        return super().create(vals_list)

    @api.model
    def _plasticos_group_members(self, xmlid):
        """``{name: tag id}`` of the tags in the group ``xmlid`` (empty if absent)."""
        group = self.env.ref(xmlid, raise_if_not_found=False)
        return {tag.name: tag.id for tag in group.child_ids} if group else {}

    @api.model
    def _plasticos_bind_status_tags(self):
        """Give an existing same-name tag the Status external id, in the group.

        Runs before the Status data records, so a tag that already exists (a
        root-level "Hot", say) becomes ``status_hot`` instead of a second "Hot".
        """
        group = self.env.ref(STATUS_XMLID, raise_if_not_found=False)
        if not group:
            return
        module = STATUS_XMLID.split(".", 1)[0]
        names = [name for _xmlid, name in LEAD_STATUS_TAGS]
        data = self.env["ir.model.data"].sudo()  # sudo: external ids are written by the module loader's rules
        bound = data.search([("module", "=", module), ("name", "in", [xmlid for xmlid, _name in LEAD_STATUS_TAGS])])
        existing = self.with_context(active_test=False).search([("name", "in", names)])
        rows = [(tag.id, tag.name, tag.parent_id.id) for tag in existing]
        plan = bind_plan(rows, group.id, bound.mapped("name"), LEAD_STATUS_TAGS)
        if not plan:
            return
        self.browse([tag_id for _xmlid, tag_id in plan]).write({"parent_id": group.id})
        data.create(
            [
                {"module": module, "name": xmlid, "model": self._name, "res_id": tag_id, "noupdate": True}
                for xmlid, tag_id in plan
            ]
        )
        _logger.info("Status tags: %d existing tags given their external id", len(plan))

    @api.model
    def _plasticos_ensure_classification_tags(self):
        """Move same-name root tags into their group; create a missing name.

        A missing name is created here only when ``plasticos_crm_bridge`` is not
        installed or about to be: that module creates its own tags, and
        ``create`` above puts them in the group.
        """
        module = self.env["ir.module.module"].search([("name", "=", CRM_BRIDGE)], limit=1)
        bridge = module.state in BRIDGE_LOADING_STATES
        to_create = []
        for xmlid, names in GROUPS.items():
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            existing = self.with_context(active_test=False).search([("name", "in", list(names))])
            rows = [(tag.id, tag.name, tag.parent_id.id) for tag in existing]
            reparent, missing = reparent_plan(rows, group.id, names)
            if reparent:
                self.browse(reparent).write({"parent_id": group.id})
            if not bridge:
                to_create.extend({"name": name, "parent_id": group.id} for name in missing)
            _logger.info(
                "%s tags: %d moved into the group, %d created, %d left to %s",
                group.name,
                len(reparent),
                0 if bridge else len(missing),
                len(missing) if bridge else 0,
                CRM_BRIDGE,
            )
        if to_create:
            self.create(to_create)

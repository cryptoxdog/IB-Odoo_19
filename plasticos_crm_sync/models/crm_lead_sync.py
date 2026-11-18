import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CrmLeadSync(models.Model):
    _inherit = "crm.lead"

    crm_call_event_ids = fields.One2many(
        "plasticos.crm.call.event",
        "lead_id",
        string="CRM Call Events",
    )
    crm_external_table_row_ids = fields.One2many(
        "plasticos.crm.external.table.row",
        "lead_id",
        string="CRM Custom Table Rows",
    )
    vanillasoft_sync_archived = fields.Boolean(
        string="Archived by VanillaSoft Sync",
        default=False,
        copy=False,
        index=True,
        help=(
            "Provenance flag: set when CRM sync archived this lead because VanillaSoft "
            "reported the contact deleted. Only a lead carrying this flag is reactivated "
            "when VanillaSoft later reports the contact active again — a lead an Odoo user "
            "archived for their own reasons never carries it, so sync never reopens it. "
            "Existing rows get the conservative default False on upgrade."
        ),
    )
    crm_call_event_count = fields.Integer(compute="_compute_crm_sync_counts")
    crm_table_row_count = fields.Integer(compute="_compute_crm_sync_counts")

    @api.depends("crm_call_event_ids", "crm_external_table_row_ids")
    def _compute_crm_sync_counts(self):
        for lead in self:
            lead.crm_call_event_count = len(lead.crm_call_event_ids)
            lead.crm_table_row_count = len(lead.crm_external_table_row_ids)

    @api.model
    def _plasticos_backfill_company_type_tags(self):
        """One-shot, idempotent: the recorded VanillaSoft Company Type becomes the lead's CRM tag (C1 F1).

        The importer kept Company Type only as a ``VanillaSoft Company Type: X``
        paragraph of the lead description, so that paragraph is the source.
        Returns the counts ``set`` / ``already_set`` / ``no_source_value`` /
        ``unmapped`` and logs them.
        """
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import (  # noqa: PLC0415
            COMPANY_TYPE_ALIASES,
            CRM_COMPANY_TYPE_TAG_MAPPING,
        )
        from odoo.addons.plasticos_crm_bridge.models.crm_tag_adoption import (  # noqa: PLC0415
            MISSING_ROLE_TAG_BINDING,
            role_tag_binding,
        )

        from ..services.vanillasoft_partners import backfill_company_type_tags  # noqa: PLC0415

        cache = {}

        def tag_for(value):
            canonical = COMPANY_TYPE_ALIASES.get(value, value)
            if canonical not in cache:
                xmlid = CRM_COMPANY_TYPE_TAG_MAPPING.get(canonical)
                tag = role_tag_binding(self.env, canonical, xmlid) if xmlid else None
                cache[canonical] = tag.id if tag and tag is not MISSING_ROLE_TAG_BINDING else None
            return cache[canonical]

        class _Row:
            __slots__ = ("description", "lead", "tag_ids")

            def __init__(self, lead):
                self.lead = lead
                self.description = lead.description
                self.tag_ids = lead.tag_ids.ids

        def link(row, tag_id):
            row.lead.write({"tag_ids": [(4, tag_id)]})

        leads = self.with_context(active_test=False, tracking_disable=True).search([("vanillasoft_id", "!=", False)])
        counts = backfill_company_type_tags((_Row(lead) for lead in leads), tag_for, link)
        _logger.info("VanillaSoft Company Type CRM tag backfill: %s", counts)
        return counts

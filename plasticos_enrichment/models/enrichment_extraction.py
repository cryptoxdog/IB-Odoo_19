from odoo import api, fields, models


class EnrichmentExtraction(models.Model):
    _name = "plasticos.enrichment.extraction"
    _description = "AI Extraction Result"
    _order = "extracted_at desc"

    run_id = fields.Many2one(
        "plasticos.enrichment.run",
        required=True,
        ondelete="cascade",
        index=True,
    )
    source_id = fields.Many2one(
        "plasticos.enrichment.source",
        required=True,
        ondelete="restrict",
    )

    material_json = fields.Json(
        help="Extracted material identity: polymer, form, source_type, " "quality params, volumes",
    )
    metadata_json = fields.Json(
        help="Governance metadata: flags, reasoning traces",
    )

    confidence = fields.Float(digits=(3, 2))
    governance_passed = fields.Boolean(readonly=True)
    governance_flags = fields.Json(readonly=True)
    extracted_at = fields.Datetime(readonly=True)

    is_injectable = fields.Boolean(
        compute="_compute_injectable",
        store=True,
    )

    @api.depends("confidence", "governance_passed")
    def _compute_injectable(self):
        for rec in self:
            rec.is_injectable = rec.governance_passed and (rec.confidence or 0) >= 0.85

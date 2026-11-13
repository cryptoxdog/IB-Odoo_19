from odoo import fields, models


class EnrichmentProvenance(models.Model):
    _name = "plasticos.enrichment.provenance"
    _description = "Per-field Enrichment Provenance"
    _order = "created_at desc"

    run_id = fields.Many2one(
        "plasticos.enrichment.run",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="cascade",
    )
    target_model = fields.Char(required=True)
    target_res_id = fields.Integer(
        index=True,
        help=(
            "Id of the exact record the field belongs to (a partner, material profile or facility "
            "profile). Set by converge v2 runs; empty on older rows."
        ),
    )
    target_field = fields.Char(required=True)
    value_written = fields.Char()
    previous_value = fields.Char(
        help="Value before enrichment — supports rollback",
    )
    source_url = fields.Char()
    source_sentence = fields.Text()
    confidence = fields.Float(digits=(3, 2))
    inference_type = fields.Selection(
        [
            ("explicit", "Explicit"),
            ("implicit", "Implicit"),
            ("speculative", "Speculative"),
        ]
    )
    status = fields.Selection(
        [
            ("written", "Written"),
            ("skipped_immutable", "Skipped — Immutable"),
            ("conflict", "Conflict"),
            ("unmapped", "Unmapped"),
            ("skipped_unknown", "Skipped — Unknown"),
            ("skipped_conflicting", "Skipped — Conflicting"),
            ("skipped_unit", "Skipped — Unit"),
            ("skipped_unresolved_code", "Skipped — Unresolved Code"),
            ("skipped_not_admitted", "Skipped — Not Admitted"),
        ]
    )
    created_at = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
    )

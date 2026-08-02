"""Auditable Gate match run (mothball M2 / TASK-047)."""

from odoo import api, fields, models


class PlasticosMatchRun(models.Model):
    _name = "plasticos.match.run"
    _description = "Gate Match Run"
    _inherit = ["mail.thread"]
    _order = "create_date desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    intake_id = fields.Many2one(
        "plasticos.intake",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    supplier_partner_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    mode = fields.Selection(
        [("strict", "Strict"), ("relaxed", "Relaxed")],
        default="strict",
        required=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("ok", "OK"),
            ("failed", "Failed"),
            ("degraded", "Degraded"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
    )
    engine = fields.Char(
        default="gate",
        required=True,
        help="Intelligence path used. M2 authority is Gate-mediated CEG only.",
    )
    failure_class = fields.Char(
        help="Classified Gate/transport failure (retryable/permanent/unknown).",
    )
    error_message = fields.Text()
    gate_packet_id = fields.Char(index=True)
    gate_correlation_id = fields.Char(index=True)
    match_count = fields.Integer(default=0)
    result_ids = fields.One2many(
        "plasticos.match.result",
        "match_run_id",
        string="Match Results",
    )

    @api.depends("intake_id")
    def _compute_display_name(self):
        for rec in self:
            intake = rec.intake_id.display_name if rec.intake_id else "?"
            rec.display_name = f"Match run {rec.id or 'new'} / {intake}"

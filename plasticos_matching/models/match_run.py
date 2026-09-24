"""Auditable Gate match run (mothball M2/M3)."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Server-owned write door for Gate receipt evidence. Only the Gate-only
# orchestrator opens it (the same context-key convention as the frozen legacy
# rate memory in plasticos_logistics). Every other writer -- form, RPC, server
# action, import, ``sudo()`` -- is refused at the ORM boundary, not merely
# hidden behind a readonly widget.
RECEIPT_WRITE_CONTEXT = "plasticos_matching_receipt_write"

# Server-captured receipt evidence. The orchestrator writes each value at most
# once (request identity before dispatch, Gate provenance before mapping, Gate
# lineage on success) and the value is immutable afterwards. Human review
# disposition lives on ``plasticos.match.result`` and stays ordinary state.
RECEIPT_FIELDS = (
    "request_attempt",
    "operation_id",
    "request_fingerprint",
    "gate_packet_id",
    "gate_correlation_id",
    "gate_query_id",
    "gate_contract_version",
    "gate_domain_spec_version",
    "gate_model_version",
    "gate_response_digest",
)


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
            ("retryable", "Retryable"),
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
        help="Intelligence path used. Authority is Gate-mediated CEG only.",
    )
    failure_class = fields.Char(
        help="Classified Gate/transport failure (retryable/permanent/unknown).",
    )
    availability_status = fields.Char(
        help="Structured Gate availability status at run time.",
    )
    error_message = fields.Text()
    request_attempt = fields.Integer(
        default=1,
        required=True,
        readonly=True,
        copy=False,
        help="Recorded Gate request attempt; an operator retry creates a new match run and attempt.",
    )
    operation_id = fields.Char(
        readonly=True,
        copy=False,
        index=True,
        help="Stable Gate business idempotency identity for this durable Odoo match run attempt.",
    )
    request_fingerprint = fields.Char(
        readonly=True,
        copy=False,
        index=True,
        help="SHA-256 fingerprint of the exact allowlisted Gate request material.",
    )
    gate_packet_id = fields.Char(readonly=True, copy=False, index=True)
    gate_correlation_id = fields.Char(readonly=True, copy=False, index=True)
    gate_query_id = fields.Char(
        readonly=True,
        copy=False,
        index=True,
        help="Gate/CEG query identity reported on the match response; server-captured evidence.",
    )
    gate_contract_version = fields.Char(
        readonly=True,
        copy=False,
        help="Gate contract version reported on the match response; server-captured evidence.",
    )
    gate_domain_spec_version = fields.Char(
        readonly=True,
        copy=False,
        help="CEG domain-spec version reported on the match response; server-captured evidence.",
    )
    gate_model_version = fields.Char(
        readonly=True,
        copy=False,
        help="CEG model version reported on the match response; server-captured evidence.",
    )
    gate_response_digest = fields.Char(
        readonly=True,
        copy=False,
        index=True,
        help="SHA-256 digest of the exact Gate response payload; raw response ownership remains with Gate.",
    )
    match_count = fields.Integer(default=0)
    retry_of_id = fields.Many2one(
        "plasticos.match.run",
        string="Retry Of",
        index=True,
        ondelete="set null",
        help="Prior run this attempt retries (idempotent lineage).",
    )
    result_ids = fields.One2many(
        "plasticos.match.result",
        "match_run_id",
        string="Match Results",
    )

    @api.depends("intake_id", "state")
    def _compute_display_name(self):
        for rec in self:
            intake = rec.intake_id.display_name if rec.intake_id else "?"
            rec.display_name = f"Match run {rec.id or 'new'} [{rec.state}] / {intake}"

    # ── Receipt evidence guard ────────────────────────────────

    @api.model
    def _receipt_vals(self, vals):
        return {name: vals[name] for name in RECEIPT_FIELDS if name in vals}

    def _check_receipt_write(self, vals):
        """Refuse any receipt write outside the server-owned door, and any rewrite of recorded evidence."""
        receipt_vals = self._receipt_vals(vals)
        if not receipt_vals:
            return
        if not self.env.context.get(RECEIPT_WRITE_CONTEXT):
            raise AccessError(
                _("Gate receipt evidence (%s) is server-owned and cannot be written directly.")
                % ", ".join(sorted(receipt_vals))
            )
        for rec in self:
            for field_name, new_value in receipt_vals.items():
                current = rec[field_name]
                if current and current != new_value:
                    raise AccessError(
                        _("Gate receipt evidence '%(field)s' on match run %(run)s is immutable once recorded.")
                        % {"field": field_name, "run": rec.id}
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.browse()._check_receipt_write(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_receipt_write(vals)
        return super().write(vals)

    def action_retry_match(self):
        """Operator retry — creates a new Gate-only run; never local scoring."""
        self.ensure_one()
        return self.env["plasticos.match.orchestrator"].retry_match_run(self)

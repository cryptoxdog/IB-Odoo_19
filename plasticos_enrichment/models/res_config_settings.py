"""Enrichment sweep settings (system parameters only; ADR-012 amendment 2026-11-15).

Scalars bind to ``ir.config_parameter`` through ``config_parameter``. The
multi-valued buyer filters are stored as sorted JSON lists under the same
``plasticos.gate.sweep_*`` keys and validated on read by ``sweep_policy``.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..services import sweep_policy as policy


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    plasticos_sweep_enabled = fields.Boolean(
        string="Scheduled Enrichment Sweep",
        config_parameter=policy.ICP_ENABLED,
        help="Off by default. Both sweep crons also stay inactive until an administrator activates them.",
    )
    plasticos_sweep_daily_budget_usd = fields.Float(
        string="Daily Budget (USD)",
        config_parameter=policy.ICP_DAILY_BUDGET_USD,
        default=policy.DEFAULT_DAILY_BUDGET_USD,
        help="Odoo's daily cap. EIE enforces min(this, its own ceiling) per tenant per UTC day.",
    )
    plasticos_sweep_max_candidates = fields.Integer(
        string="Max Buyers per Sweep",
        config_parameter=policy.ICP_MAX_CANDIDATES,
        default=policy.DEFAULT_MAX_CANDIDATES,
        help="Upper bound on facilities sent per nightly sweep (1-500).",
    )
    plasticos_sweep_cooldown_days = fields.Integer(
        string="Cooldown (days)",
        config_parameter=policy.ICP_COOLDOWN_DAYS,
        default=policy.DEFAULT_COOLDOWN_DAYS,
        help="Skip a facility with a converge v2 enrichment run inside this many days. 0 = no cooldown.",
    )
    plasticos_sweep_process_types = fields.Char(
        string="Capability Types",
        help="Comma list of capability-type codes (e.g. injection_molding, compounding). Empty = any.",
    )
    plasticos_sweep_application_classes = fields.Char(
        string="Application Classes",
        help="Comma list of application-class keys (food, medical, automotive, ...). Empty = any.",
    )
    plasticos_sweep_feedstock_types = fields.Char(
        string="Feedstock Types",
        help="Comma list of feedstock keys (post_industrial, post_consumer, mixed, virgin, unknown). Empty = any.",
    )
    plasticos_sweep_capability_type_ids = fields.Many2many(
        "plasticos.capability.type",
        string="Capabilities (any of)",
        help="Sweep facilities that have any of these capability types. Empty = any.",
    )
    plasticos_sweep_accepted_polymer_ids = fields.Many2many(
        "plasticos.polymer",
        string="Inbound Polymers (any of)",
        help="Sweep facilities whose partner has an inbound material profile for any of these polymers. Empty = any.",
    )
    plasticos_sweep_min_capacity_lbs_month = fields.Integer(
        string="Min Capacity (lbs/month)",
        config_parameter=policy.ICP_MIN_CAPACITY_LBS_MONTH,
        help="Only facilities at or above this monthly capacity. 0 = any.",
    )

    _SWEEP_KEY_FIELDS = (
        ("plasticos_sweep_process_types", policy.ICP_CAPABILITY_TYPE_CODES, "capability_type_codes"),
        ("plasticos_sweep_application_classes", policy.ICP_APPLICATION_CLASSES, "application_classes"),
        ("plasticos_sweep_feedstock_types", policy.ICP_FEEDSTOCK_TYPES, "feedstock_types"),
    )
    _SWEEP_ID_FIELDS = (
        ("plasticos_sweep_capability_type_ids", policy.ICP_CAPABILITY_TYPE_IDS, "plasticos.capability.type"),
        ("plasticos_sweep_accepted_polymer_ids", policy.ICP_POLYMER_IDS, "plasticos.polymer"),
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()  # sudo: settings read of system parameters
        for field_name, key, _attr in self._SWEEP_KEY_FIELDS:
            try:
                res[field_name] = ", ".join(policy.parse_list(icp.get_param(key), key))
            except policy.SweepSettingsError:
                res[field_name] = icp.get_param(key) or False
        for field_name, key, model in self._SWEEP_ID_FIELDS:
            try:
                ids = policy.parse_list(icp.get_param(key), key, ints=True)
            except policy.SweepSettingsError:
                ids = ()
            res[field_name] = [fields.Command.set(self.env[model].browse(ids).exists().ids)]
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()  # sudo: settings write of system parameters
        allowed = self.env["plasticos.enrichment.sweep"]._sweep_selection_keys()
        for field_name, key, attr in self._SWEEP_KEY_FIELDS:
            try:
                values = policy.parse_list(self[field_name] or "", key, allowed=getattr(allowed, attr))
            except policy.SweepSettingsError as exc:
                raise ValidationError(
                    _("%(error)s. Allowed keys: %(keys)s")
                    % {"error": exc, "keys": ", ".join(sorted(getattr(allowed, attr)))}
                ) from exc
            icp.set_param(key, policy.dump_list(values))
        for field_name, key, _model in self._SWEEP_ID_FIELDS:
            icp.set_param(key, policy.dump_list(self[field_name].ids))
        # Fail closed on save, not at 2 a.m.: the whole set must read back.
        try:
            self.env["plasticos.enrichment.sweep"]._sweep_settings()
        except policy.SweepSettingsError as exc:
            raise ValidationError(str(exc)) from exc

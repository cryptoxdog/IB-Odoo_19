import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Canonical polymer list — loaded from plasticos.polymer table
# Fallback to hardcoded list if table not available
# ─────────────────────────────────────────────────────────────
FALLBACK_POLYMERS = frozenset(
    [
        "HDPE",
        "LDPE",
        "LLDPE",
        "PP",
        "PET",
        "rPET",
        "PVC",
        "PC",
        "PS",
        "ABS",
        "PA",
        "PLA",
        "TPE",
        "TPU",
        "PEEK",
        "PEI",
        "POM",
        "PPS",
        "PTFE",
        "EVA",
    ]
)

# Packet schema version — bumped when the packet structure changes.
# L9 adapter uses this to decide how to parse the payload.
PACKET_SCHEMA_VERSION = "1.0.0"


class PlasticosNormalizerConfig(models.Model):
    """Singleton configuration for the intake normalizer.

    Controls batch-normalization behaviour and validation strictness.
    """

    _name = "plasticos.normalizer.config"
    _description = "Intake Normalizer Configuration"

    name = fields.Char(default="Normalizer Configuration", required=True)

    # ── Validation toggles ───────────────────────────────
    require_polymer_in_canonical = fields.Boolean(
        string="Require Canonical Polymer",
        default=True,
        help="When True, polymer must be in the 20-type canonical list. "
        "When False, any non-empty polymer value is accepted.",
    )
    require_partner = fields.Boolean(
        string="Require Partner",
        default=True,
        help="When True, partner_id must be set on the intake.",
    )
    require_positive_quantity = fields.Boolean(
        string="Require Positive Quantity",
        default=True,
        help="When True, quantity_per_load_lbs must be > 0.",
    )
    validate_density_range = fields.Boolean(
        string="Validate Density Range",
        default=True,
        help="When True, density_value (if set) must be > 0 and within configured range.",
    )
    density_min = fields.Float(
        string="Density Min (g/cm³)",
        default=0.0,
        help="Minimum density value. Set to 0 to disable lower bound check.",
    )
    density_max = fields.Float(
        string="Density Max (g/cm³)",
        default=0.0,
        help="Maximum density value. Set to 0 to disable upper bound check.",
    )
    validate_mfi_positive = fields.Boolean(
        string="Validate MFI Positive",
        default=True,
        help="When True, mfi_value (if set) must be >= 0.",
    )

    # ── Batch cron settings ──────────────────────────────
    batch_limit = fields.Integer(
        string="Batch Limit",
        default=200,
        help="Maximum intakes to normalize per cron run.",
    )

    # ── Singleton pattern ────────────────────────────────
    @api.model
    def get_config(self):
        """Return the singleton config record, creating it if absent."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({"name": "Normalizer Configuration"})
        return config

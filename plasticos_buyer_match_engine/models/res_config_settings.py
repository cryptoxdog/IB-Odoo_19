from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ib_matching_engine_enabled = fields.Boolean(
        string="Enable Matching Engine",
        config_parameter="ib.matching_engine.enabled",
        help="Activate buyer matching features backed by the matching engine.",
    )
    ib_inference_engine_enabled = fields.Boolean(
        string="Enable Inference Engine",
        config_parameter="ib.inference_engine.enabled",
        help="Reserve toggle for inference-driven features as they come online.",
    )
    ib_matching_engine_url = fields.Char(
        string="Matching Engine URL",
        config_parameter="ib.matching_engine.url",
        default="http://localhost:8001",
    )
    ib_inference_engine_url = fields.Char(
        string="Inference Engine URL",
        config_parameter="ib.inference_engine.url",
        default="http://localhost:8002",
    )
    ib_feature_gate_message = fields.Char(
        string="Feature Unavailable Message",
        config_parameter="ib.feature_gate.user_message",
        help="Shown to users when a disabled microservice-backed feature is invoked.",
    )

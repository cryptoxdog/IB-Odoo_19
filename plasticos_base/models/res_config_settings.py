from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Matching Engine (external microservice)
    plasticos_matching_engine_enabled = fields.Boolean(
        string="Enable Matching Engine",
        config_parameter="plasticos.matching_engine.enabled",
        help="Activate buyer/seller matching via external microservice.",
    )
    plasticos_matching_engine_url = fields.Char(
        string="Matching Engine URL",
        config_parameter="plasticos.matching_engine.url",
        default="http://localhost:8001",
    )

    # Inference Engine (external microservice)
    plasticos_inference_engine_enabled = fields.Boolean(
        string="Enable Inference Engine",
        config_parameter="plasticos.inference_engine.enabled",
        help="Activate AI-powered enrichment via external microservice.",
    )
    plasticos_inference_engine_url = fields.Char(
        string="Inference Engine URL",
        config_parameter="plasticos.inference_engine.url",
        default="http://localhost:8002",
    )

    # Shown when buyer matching is disabled (legacy intake button + v2 matcher)
    plasticos_feature_gate_message = fields.Char(
        string="Matching Unavailable Message",
        config_parameter="plasticos.feature_gate.user_message",
        help="Message shown when buyer matching is disabled (matching_engine.enabled is off).",
    )

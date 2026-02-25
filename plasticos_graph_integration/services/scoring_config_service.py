from odoo import models


class ScoringConfigService(models.AbstractModel):
    _name = "plasticos.scoring.config.service"
    _description = "Scoring Config Service"

    def get_weights(self):
        params = self.env["ir.config_parameter"].sudo()
        return {
            "structural_weight": float(params.get_param("graph.structural_weight", 0.5)),
            "similarity_weight": float(params.get_param("graph.similarity_weight", 0.3)),
            "reinforcement_weight": float(params.get_param("graph.reinforcement_weight", 0.2)),
        }

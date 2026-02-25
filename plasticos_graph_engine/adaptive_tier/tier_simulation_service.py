from odoo import models


class TierSimulationService(models.AbstractModel):
    _name = "plasticos.graph.tier.simulate"

    def simulate(self, tenant_code, grade_id, new_tier):
        return {"grade_id": grade_id, "simulated_tier": new_tier, "impact_score": 0.75}

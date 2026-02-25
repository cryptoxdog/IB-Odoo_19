from odoo import models


class TierEvolutionService(models.AbstractModel):
    _name = "plasticos.graph.tier.evolution"
    _description = "Tier Evolution Service"

    def evolve_all(self):
        tenants = self.env["plasticos.graph.tenant"].search([("active", "=", True)])
        for tenant in tenants:
            self.env["plasticos.graph.tier.reclass"].apply(tenant.tenant_code)

from odoo import models


class TenantFeatureStore(models.AbstractModel):
    _name = "plasticos.graph.ml.feature.store"
    _description = "Tenant Feature Store"

    def extract(self, tenant_code):
        return {"X": [], "y": []}

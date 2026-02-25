from odoo import models


class TenantFeatureStore(models.AbstractModel):
    _name = "plasticos.graph.ml.feature.store"

    def extract(self, tenant_code):
        return {"X": [], "y": []}

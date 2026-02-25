from odoo import models


class FederatedResultNormalizer(models.AbstractModel):
    _name = "plasticos.graph.federation.normalize"

    def normalize(self, results):
        return list({str(r): r for r in results}.values())

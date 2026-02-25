from odoo import models


class FederatedResultNormalizer(models.AbstractModel):
    _name = "plasticos.graph.federation.normalize"
    _description = "Federated Result Normalizer"

    def normalize(self, results):
        return list({str(r): r for r in results}.values())

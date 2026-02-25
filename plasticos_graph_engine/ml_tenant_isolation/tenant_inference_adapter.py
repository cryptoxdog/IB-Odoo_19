from odoo import models

from .tenant_model_registry import TenantModelRegistry


class TenantMLInference(models.AbstractModel):
    _name = "plasticos.graph.ml.tenant"

    def rerank(self, tenant_code, candidates):
        model = TenantModelRegistry.load(tenant_code)
        features = [c["feature_vector"] for c in candidates]
        scores = model.predict(features)

        for i, c in enumerate(candidates):
            c["ml_score"] = float(scores[i])

        candidates.sort(key=lambda x: -x["ml_score"])
        return candidates

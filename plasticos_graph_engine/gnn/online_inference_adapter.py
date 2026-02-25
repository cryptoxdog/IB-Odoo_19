from odoo import models


class GNNOnlineAdapter(models.AbstractModel):
    _name = "plasticos.graph.gnn.online"

    def rerank(self, tenant_code, candidates):
        for c in candidates:
            c["gnn_score"] = c.get("similarity_score", 0) * 1.2
        candidates.sort(key=lambda x: -x["gnn_score"])
        return candidates

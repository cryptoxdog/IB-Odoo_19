from graph_ml.inference_service import InferenceService

from odoo import models


class MLRankingAdapter(models.AbstractModel):
    _name = "plasticos.ml.ranking.adapter"

    def apply_ml(self, candidates):
        inference = InferenceService()
        return inference.rerank(candidates)

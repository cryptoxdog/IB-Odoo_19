import xgboost as xgb

from .tenant_model_registry import TenantModelRegistry


class TenantTrainingPipeline:
    def train(self, tenant_code, dataset):
        model = xgb.XGBRanker(
            objective="rank:pairwise",
            n_estimators=300,
            max_depth=6,
        )

        X = dataset["X"]
        y = dataset["y"]

        model.fit(X, y)
        TenantModelRegistry.save(tenant_code, model)

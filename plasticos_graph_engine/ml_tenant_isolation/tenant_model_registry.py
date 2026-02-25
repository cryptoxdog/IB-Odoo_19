import os

import joblib


class TenantModelRegistry:
    BASE_PATH = "graph_ml/artifacts/"

    @classmethod
    def load(cls, tenant_code):
        path = os.path.join(cls.BASE_PATH, f"{tenant_code}_model.joblib")
        return joblib.load(path)

    @classmethod
    def save(cls, tenant_code, model):
        path = os.path.join(cls.BASE_PATH, f"{tenant_code}_model.joblib")
        joblib.dump(model, path)

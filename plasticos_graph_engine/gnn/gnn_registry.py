import os

import torch

from .config import ARTIFACT_PATH


class GNNRegistry:
    @classmethod
    def save(cls, tenant_code, model):
        path = os.path.join(ARTIFACT_PATH, f"{tenant_code}_gnn.pt")
        torch.save(model.state_dict(), path)

    @classmethod
    def load(cls, tenant_code, model_class):
        path = os.path.join(ARTIFACT_PATH, f"{tenant_code}_gnn.pt")
        model = model_class
        model.load_state_dict(torch.load(path))
        model.eval()
        return model

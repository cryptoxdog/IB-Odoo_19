import torch

from .config import EMBEDDING_DIM, HIDDEN_DIM
from .gnn_registry import GNNRegistry
from .models import GradeGNN


class GNNInferenceService:
    def infer(self, tenant_code, dataset):
        model = GradeGNN(
            input_dim=dataset.num_node_features,
            hidden_dim=HIDDEN_DIM,
            embedding_dim=EMBEDDING_DIM,
        )

        model = GNNRegistry.load(tenant_code, model)
        with torch.no_grad():
            embeddings = model(dataset.x, dataset.edge_index)

        return embeddings

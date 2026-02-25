import torch
import torch.optim as optim

from .config import EMBEDDING_DIM, EPOCHS, HIDDEN_DIM, LEARNING_RATE
from .gnn_registry import GNNRegistry
from .models import GradeGNN


class GNNTrainingPipeline:
    def train(self, tenant_code, dataset):
        model = GradeGNN(
            input_dim=dataset.num_node_features,
            hidden_dim=HIDDEN_DIM,
            embedding_dim=EMBEDDING_DIM,
        )

        optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

        model.train()
        for _ in range(EPOCHS):
            optimizer.zero_grad()
            out = model(dataset.x, dataset.edge_index)
            loss = torch.mean(out)
            loss.backward()
            optimizer.step()

        GNNRegistry.save(tenant_code, model)
        return model

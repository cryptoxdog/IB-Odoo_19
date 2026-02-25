import torch
from torch_geometric.data import Data

from .feature_engineering import FeatureEngineering


class GNNDatasetBuilder:
    def build(self, export_data):
        nodes = export_data["nodes"]
        edges = export_data["edges"]

        x = FeatureEngineering.build_node_features(nodes)

        edge_index = torch.tensor([[e["source"], e["target"]] for e in edges], dtype=torch.long).t().contiguous()

        return Data(x=x, edge_index=edge_index)

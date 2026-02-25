import torch


class FeatureEngineering:
    @staticmethod
    def build_node_features(nodes):
        features = []
        for n in nodes:
            features.append(
                [
                    n.get("tier", 0),
                    n.get("mfi_min", 0),
                    n.get("mfi_max", 0),
                ]
            )
        return torch.tensor(features, dtype=torch.float)

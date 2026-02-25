class GNNSignalAdapter:
    @staticmethod
    def concession_modifier(gnn_similarity):
        if gnn_similarity > 0.85:
            return 0.8
        if gnn_similarity < 0.6:
            return 1.2
        return 1.0

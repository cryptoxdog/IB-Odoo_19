import math


class ReinforcementDecayAdapter:
    @staticmethod
    def compute(reinforcement_score, days_since_last_txn):
        decay = math.exp(-0.01 * days_since_last_txn)
        return reinforcement_score * decay

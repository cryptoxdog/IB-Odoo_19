class ConcessionModel:
    @staticmethod
    def compute(round_number, max_rounds, start, target, aggression):
        progress = (round_number / max_rounds) ** (1 + aggression)
        return start + (target - start) * progress

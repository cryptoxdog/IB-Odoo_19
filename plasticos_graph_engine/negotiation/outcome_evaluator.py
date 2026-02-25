class OutcomeEvaluator:
    @staticmethod
    def evaluate(acceptance, rounds, max_rounds, structural_score):
        efficiency = 1 - (rounds / max_rounds)
        confidence = acceptance * 0.5 + structural_score * 0.3 + efficiency * 0.2
        relationship = acceptance * structural_score
        return confidence, relationship

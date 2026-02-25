class RegimeIntegrationAdapter:
    @staticmethod
    def aggression_modifier(regime_state):
        if regime_state == "volatile":
            return 1.3
        if regime_state == "tight_supply":
            return 0.8
        return 1.0

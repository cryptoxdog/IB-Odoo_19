class NegotiationGovernor:
    @staticmethod
    def enforce(price, floor, ceiling, volatility):
        if volatility > 0.8:
            price *= 0.95
        return min(max(price, floor), ceiling)

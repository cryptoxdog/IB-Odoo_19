"""Belief state tracker for multi-round negotiation.

Tracks the evolving belief about whether a settlement price will be
accepted by the counterparty, decaying with reinforcement history.
"""


class BeliefState:
    """Bayesian-inspired belief tracker for negotiation rounds."""

    def __init__(self, initial_decay: float = 1.0):
        self.belief = 0.5
        self.decay = initial_decay

    def update(self, settlement: float, facility_band: tuple, reinforcement_decay: float) -> float:
        """Update belief score based on how well settlement fits the band.

        Args:
            settlement: Current round settlement price.
            facility_band: (min_price, max_price) acceptable range.
            reinforcement_decay: Historical reinforcement decay factor.

        Returns:
            Updated belief score in [0, 1].
        """
        if not facility_band or len(facility_band) < 2:
            return self.belief

        low, high = facility_band
        if high <= low:
            return self.belief

        center = (low + high) / 2.0
        distance = abs(settlement - center) / (high - low)
        alignment = max(0.0, 1.0 - distance)

        self.belief = (self.belief * 0.6) + (alignment * reinforcement_decay * 0.4)
        self.belief = max(0.0, min(1.0, self.belief))
        return self.belief

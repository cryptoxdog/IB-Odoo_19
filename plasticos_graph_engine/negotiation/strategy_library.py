from dataclasses import dataclass


@dataclass
class Strategy:
    aggressiveness: float
    patience: float


class StrategyLibrary:
    @staticmethod
    def for_tier(tier_level):
        mapping = {
            1: Strategy(0.4, 0.9),
            2: Strategy(0.6, 0.8),
            3: Strategy(0.8, 0.7),
            4: Strategy(1.0, 0.6),
        }
        return mapping.get(tier_level, Strategy(0.6, 0.8))

from dataclasses import dataclass


@dataclass
class NegotiationContext:
    grade_id: str
    facility_id: str
    structural_score: float
    gnn_similarity: float
    reinforcement_decay: float
    tier_level: int
    tier_distance: float
    mfi_distance: float
    contamination_risk: float
    capability_width: float
    facility_load: float
    market_regime: str
    volatility_index: float
    predicted_price: float
    rl_price: float
    facility_band: tuple
    hard_floor: float
    hard_ceiling: float


class NegotiationContextBuilder:
    def build(self, inputs):
        return NegotiationContext(**inputs)

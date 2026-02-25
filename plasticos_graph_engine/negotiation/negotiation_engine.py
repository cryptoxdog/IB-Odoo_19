from .bargaining_game import BargainingGame
from .belief_state_model import BeliefState
from .concession_model import ConcessionModel
from .negotiation_audit_log import NegotiationAudit
from .negotiation_governor import NegotiationGovernor
from .outcome_evaluator import OutcomeEvaluator
from .strategy_library import StrategyLibrary


class NegotiationEngine:
    MAX_ROUNDS = 7

    def execute(self, context):
        strategy = StrategyLibrary.for_tier(context.tier_level)

        supplier_anchor = context.predicted_price * 1.1
        facility_anchor = context.predicted_price * 0.9

        belief = BeliefState(context.reinforcement_decay)

        trace = []
        agreed = None

        for round_number in range(1, self.MAX_ROUNDS + 1):
            supplier_offer = ConcessionModel.compute(
                round_number,
                self.MAX_ROUNDS,
                supplier_anchor,
                context.rl_price,
                strategy.aggressiveness,
            )

            facility_offer = ConcessionModel.compute(
                round_number,
                self.MAX_ROUNDS,
                facility_anchor,
                context.predicted_price,
                strategy.aggressiveness,
            )

            settlement = BargainingGame.weighted_nash(
                supplier_offer,
                facility_offer,
                context.structural_score,
            )

            settlement = NegotiationGovernor.enforce(
                settlement,
                context.hard_floor,
                context.hard_ceiling,
                context.volatility_index,
            )

            belief_score = belief.update(
                settlement,
                context.facility_band,
                context.reinforcement_decay,
            )

            acceptance = BargainingGame.acceptance_probability(
                settlement,
                context.facility_band,
                belief_score,
            )

            trace.append(
                {
                    "round": round_number,
                    "settlement": settlement,
                    "acceptance": acceptance,
                }
            )

            if acceptance > 0.65:
                agreed = settlement
                break

        if agreed is None:
            agreed = settlement

        confidence, relationship = OutcomeEvaluator.evaluate(
            acceptance,
            round_number,
            self.MAX_ROUNDS,
            context.structural_score,
        )

        NegotiationAudit.create(
            {
                "tenant_code": "auto",
                "intake_id": context.grade_id,
                "facility_id": context.facility_id,
                "agreed_price": agreed,
                "rounds": round_number,
                "confidence_score": confidence,
                "relationship_score": relationship,
                "full_trace": trace,
            }
        )

        return {
            "agreed_price": agreed,
            "negotiation_rounds": round_number,
            "confidence_score": confidence,
            "long_term_relationship_score": relationship,
        }

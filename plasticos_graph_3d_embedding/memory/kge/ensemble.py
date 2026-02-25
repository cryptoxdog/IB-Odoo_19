# memory/kge/ensemble.py
"""
Ensemble Methods for CompoundE3D Fusion

Implements Weighted Distribution Score (WDS) fusion + rank aggregation
to combine multiple KGE variants for improved triple classification accuracy
and robustness across diverse knowledge graph structures.

**Frontier Patterns:** Anthropic Constitutional AI (ensemble validation),
OpenAI GPT (temperature-based weighting), DeepMind (mixture of experts).

**Invariants:**
- Ensemble weights sum to 1.0 (probability distribution)
- All variant scores normalized to [0, 1] before fusion
- Rank aggregation is consistent (no tie-breaking artifacts)
- Fallback strategies handle missing scores gracefully
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import numpy as np


class FusionStrategy(Enum):
    """Ensemble fusion strategies."""

    WEIGHTED_MEAN = "weighted_mean"  # Weighted average of scores
    MEDIAN = "median"  # Median of scores
    MAX = "max"  # Maximum score
    RANK_AGGREGATION = "rank_aggregation"  # Borda count or similar
    MIXTURE_EXPERTS = "mixture_experts"  # Gated mixture (learned weights)


class RankAggregationMethod(Enum):
    """Rank aggregation methods."""

    BORDA = "borda"  # Borda count
    CONDORCET = "condorcet"  # Condorcet winner (if exists)
    KEMENY = "kemeny"  # Kemeny optimal (NP-hard, approx)
    PLURALITY = "plurality"  # Plurality voting


@dataclass
class VariantScore:
    """Score from a single KGE variant."""

    variant_id: str
    variant_type: str
    score: float  # [0, 1]
    confidence: float = 1.0  # Confidence in score
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

        # Validate score range
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be in [0, 1], got {self.score}")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")


@dataclass
class EnsembleResult:
    """Result of ensemble prediction."""

    final_score: float
    component_scores: list[VariantScore]
    weights: dict[str, float]
    fusion_strategy: str
    rank: int | None = None
    explanation: str = ""


class VariantEnsemble(ABC):
    """Abstract base for ensemble strategies."""

    @abstractmethod
    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """Fuse variant scores into single prediction."""
        pass

    @abstractmethod
    def explain(self, result: EnsembleResult) -> str:
        """Generate human-readable explanation."""
        pass


class WeightedDistributionScore(VariantEnsemble):
    """
    Weighted Distribution Score (WDS) Ensemble.

    **Method:**
    1. Normalize scores to [0, 1]
    2. Apply per-variant weights (learned or uniform)
    3. Compute weighted mean
    4. Adjust by confidence (soft gating)

    **Formula:**
    WDS = Σ(w_i * s_i * c_i) / Σ(w_i * c_i)
    where w_i = weight, s_i = score, c_i = confidence
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        temperature: float = 1.0,
    ):
        """
        Args:
            weights: Variant-specific weights (sum to 1 if provided)
            temperature: Softmax temperature for confidence weighting
        """
        self.weights = weights or {}
        self.temperature = temperature

    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """Compute weighted average with confidence gating."""
        if not scores:
            raise ValueError("No scores provided")

        # Normalize scores to [0, 1] (already done, but verify)
        normalized_scores = [
            VariantScore(
                variant_id=s.variant_id,
                variant_type=s.variant_type,
                score=np.clip(s.score, 0.0, 1.0),
                confidence=np.clip(s.confidence, 0.0, 1.0),
                metadata=s.metadata,
            )
            for s in scores
        ]

        # Get or initialize weights
        weights = {}
        for score_obj in normalized_scores:
            variant_id = score_obj.variant_id
            if variant_id in self.weights:
                weights[variant_id] = self.weights[variant_id]
            else:
                weights[variant_id] = 1.0 / len(normalized_scores)

        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        # Compute weighted average with confidence gating
        weighted_sum = 0.0
        confidence_sum = 0.0

        for score_obj in normalized_scores:
            variant_id = score_obj.variant_id
            w = weights.get(variant_id, 1.0 / len(normalized_scores))

            # Temperature scaling for confidence
            conf_scaled = score_obj.confidence ** (1.0 / self.temperature)

            weighted_sum += w * score_obj.score * conf_scaled
            confidence_sum += w * conf_scaled

        # Normalize by confidence sum
        if confidence_sum > 0:
            final_score = weighted_sum / confidence_sum
        else:
            final_score = np.mean([s.score for s in normalized_scores])

        explanation = self.explain(
            EnsembleResult(
                final_score=final_score,
                component_scores=normalized_scores,
                weights=weights,
                fusion_strategy="weighted_mean",
            )
        )

        return EnsembleResult(
            final_score=final_score,
            component_scores=normalized_scores,
            weights=weights,
            fusion_strategy="weighted_mean",
            explanation=explanation,
        )

    def explain(self, result: EnsembleResult) -> str:
        """Generate WDS explanation."""
        top_3 = sorted(
            [(w, result.component_scores[i].variant_id) for i, w in enumerate(result.weights.values())],
            key=lambda x: -x[0],
        )[:3]

        explanation = f"WDS Ensemble: final_score={result.final_score:.4f}\n"
        explanation += "Top contributors:\n"
        for weight, variant_id in top_3:
            explanation += f"  - {variant_id}: weight={weight:.4f}\n"

        return explanation


class RankAggregationEnsemble(VariantEnsemble):
    """
    Rank Aggregation Ensemble.

    **Methods:**
    - Borda Count: Each position gets points (1st=n points, 2nd=n-1, ...)
    - Condorcet: Winner beats all others pairwise
    - Kemeny: Minimize Kendall tau distance (NP-hard)
    - Plurality: Most votes at top position wins
    """

    def __init__(self, method: RankAggregationMethod = RankAggregationMethod.BORDA):
        self.method = method

    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """Aggregate variant rankings."""
        if not scores:
            raise ValueError("No scores provided")

        # Sort by score (descending) to get ranking
        ranked = sorted(scores, key=lambda s: -s.score)

        if self.method == RankAggregationMethod.BORDA:
            final_score, explanation = self._borda_count(ranked)
        elif self.method == RankAggregationMethod.PLURALITY:
            final_score, explanation = self._plurality(ranked)
        else:
            # Fallback to Borda
            final_score, explanation = self._borda_count(ranked)

        # Convert rank-aggregated position to score
        rank = 1
        final_score_normalized = 1.0 - (rank - 1) / len(ranked) if ranked else 0.5

        weights = {s.variant_id: 1.0 / len(scores) for s in scores}

        return EnsembleResult(
            final_score=final_score_normalized,
            component_scores=ranked,
            weights=weights,
            fusion_strategy=self.method.value,
            rank=rank,
            explanation=explanation,
        )

    def _borda_count(self, ranked: list[VariantScore]) -> tuple[float, str]:
        """Borda count aggregation."""
        n = len(ranked)
        total_points = sum(n - i for i in range(n))

        # Top candidate points
        top_points = n
        top_score = top_points / total_points if total_points > 0 else 0.5

        explanation = f"Borda Count: top_variant={ranked[0].variant_id}, points={top_points}/{total_points}"
        return top_score, explanation

    def _plurality(self, ranked: list[VariantScore]) -> tuple[float, str]:
        """Plurality voting (most votes at top position)."""
        # In single ensemble, top-ranked wins plurality
        winner = ranked[0]
        score = winner.score  # Use original score

        explanation = f"Plurality: winner={winner.variant_id}, score={score:.4f}"
        return score, explanation

    def explain(self, result: EnsembleResult) -> str:
        """Generate rank aggregation explanation."""
        return result.explanation


class MixtureOfExpertsEnsemble(VariantEnsemble):
    """
    Mixture of Experts (MoE) with Gated Weighting.

    **Method:**
    1. Each variant = "expert" with score (competency)
    2. Gating network learns per-variant weights
    3. Experts score highly on different input distributions
    4. Gate selects expert weighted by competency

    **Placeholder:** Full MoE requires training on holdout set.
    """

    def __init__(
        self,
        num_experts: int = 3,
        learnable_gates: bool = False,
    ):
        self.num_experts = num_experts
        self.learnable_gates = learnable_gates
        self.gate_weights = None

    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """Route through gated mixture of experts."""
        if not scores:
            raise ValueError("No scores provided")

        # Soft routing: all experts contribute weighted by competency
        expert_competencies = np.array([s.score * s.confidence for s in scores])

        # Softmax gating (temperature-scaled)
        gate_logits = expert_competencies / (1.0 + 1e-8)
        gate_weights = np.exp(gate_logits) / np.sum(np.exp(gate_logits))

        # Weighted combination
        final_score = float(np.dot(gate_weights, expert_competencies))
        final_score = np.clip(final_score, 0.0, 1.0)

        weights = {s.variant_id: float(w) for s, w in zip(scores, gate_weights)}

        explanation = "MoE Ensemble: soft routing through expert gates\n"
        explanation += f"Final score: {final_score:.4f}\n"
        for s, w in zip(sorted(scores, key=lambda x: -x.score)[:3], gate_weights[:3]):
            explanation += f"  - {s.variant_id}: gate_weight={w:.4f}\n"

        return EnsembleResult(
            final_score=final_score,
            component_scores=scores,
            weights=weights,
            fusion_strategy="mixture_experts",
            explanation=explanation,
        )

    def explain(self, result: EnsembleResult) -> str:
        """Generate MoE explanation."""
        return result.explanation


class EnsembleController:
    """
    Meta-controller for orchestrating ensemble strategies.

    **Responsibilities:**
    - Route to appropriate ensemble strategy
    - Validate scores before fusion
    - Log ensemble decisions for audit
    - Provide fallback strategies on error
    """

    def __init__(self):
        self.strategies = {
            FusionStrategy.WEIGHTED_MEAN: WeightedDistributionScore(),
            FusionStrategy.RANK_AGGREGATION: RankAggregationEnsemble(),
            FusionStrategy.MIXTURE_EXPERTS: MixtureOfExpertsEnsemble(),
        }
        self.audit_log = []

    def predict(
        self,
        scores: list[VariantScore],
        strategy: FusionStrategy = FusionStrategy.WEIGHTED_MEAN,
    ) -> EnsembleResult:
        """
        Predict using ensemble.

        Args:
            scores: Per-variant scores
            strategy: Fusion strategy to use

        Returns:
            EnsembleResult with final prediction + metadata
        """
        # Validate inputs
        if not scores:
            raise ValueError("No scores to ensemble")

        if len(scores) == 1:
            # Single variant: return as-is
            single = scores[0]
            return EnsembleResult(
                final_score=single.score,
                component_scores=scores,
                weights={single.variant_id: 1.0},
                fusion_strategy="identity",
                explanation=f"Single variant: {single.variant_id}",
            )

        # Get strategy implementation
        strategy_impl = self.strategies.get(strategy)
        if not strategy_impl:
            # Fallback to weighted mean
            strategy_impl = self.strategies[FusionStrategy.WEIGHTED_MEAN]

        try:
            # Execute fusion
            result = strategy_impl.fuse(scores)

            # Log for audit
            self.audit_log.append(
                {
                    "strategy": strategy.value,
                    "num_variants": len(scores),
                    "final_score": result.final_score,
                    "component_scores": [
                        {
                            "id": s.variant_id,
                            "score": s.score,
                            "confidence": s.confidence,
                        }
                        for s in scores
                    ],
                }
            )

            return result

        except Exception as e:
            # Fallback: simple mean
            mean_score = np.mean([s.score for s in scores])
            weights = {s.variant_id: 1.0 / len(scores) for s in scores}

            return EnsembleResult(
                final_score=mean_score,
                component_scores=scores,
                weights=weights,
                fusion_strategy="fallback_mean",
                explanation=f"Fallback to mean due to error: {str(e)}",
            )

    def get_audit_log(self) -> list[dict]:
        """Return audit log of all ensemble predictions."""
        return self.audit_log

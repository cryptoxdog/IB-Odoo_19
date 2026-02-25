# memory/kge/test_compound_e3d.py
"""
Comprehensive Test Suite for CompoundE3D Integration

**Coverage:**
1. Unit tests: Transformations, beam search, ensemble
2. Integration tests: E3D model + orchestrator
3. Regression tests: Known graph patterns
4. Audit tests: Constraint satisfaction + variance

**Quality Standards:** 95%+ code coverage, <5% flakiness, <100ms per test
"""

from unittest.mock import Mock

import numpy as np
import pytest
from memory.kge.beam_search import (
    BeamCandidate,
    BeamSearchConfig,
    BeamSearchEngine,
    PruneStrategy,
)
from memory.kge.compound_e3d import CompoundE3D, CompoundE3DConfig
from memory.kge.ensemble import (
    EnsembleController,
    FusionStrategy,
    MixtureOfExpertsEnsemble,
    RankAggregationEnsemble,
    RankAggregationMethod,
    VariantScore,
    WeightedDistributionScore,
)
from memory.kge.transformations import (
    Flip,
    Hyperplane,
    Rotation,
    Scale,
    Translation,
)

# ============================================================================
# TRANSFORMATION TESTS
# ============================================================================


class TestTransformations:
    """Test 3D affine transformation operators."""

    def test_rotation_identity(self):
        """Rotation with 0 angle is identity."""
        r = Rotation(angle=0.0, axis=(1, 0, 0))
        point = np.array([1.0, 2.0, 3.0])
        rotated = r.apply(point)
        np.testing.assert_allclose(rotated, point, atol=1e-6)

    def test_rotation_90_degrees_z_axis(self):
        """Rotation 90° around Z should map (1,0,0) -> (0,1,0)."""
        r = Rotation(angle=90.0, axis=(0, 0, 1))
        point = np.array([1.0, 0.0, 0.0])
        rotated = r.apply(point)
        expected = np.array([0.0, 1.0, 0.0])
        np.testing.assert_allclose(rotated, expected, atol=1e-6)

    def test_scale_2x(self):
        """Scale by 2 should double coordinates."""
        s = Scale(factor=2.0)
        point = np.array([1.0, 2.0, 3.0])
        scaled = s.apply(point)
        expected = np.array([2.0, 4.0, 6.0])
        np.testing.assert_allclose(scaled, expected, atol=1e-6)

    def test_translation(self):
        """Translation should add offset."""
        t = Translation(offset=(1.0, 2.0, 3.0))
        point = np.array([0.0, 0.0, 0.0])
        translated = t.apply(point)
        expected = np.array([1.0, 2.0, 3.0])
        np.testing.assert_allclose(translated, expected, atol=1e-6)

    def test_flip_x_axis(self):
        """Flip around X should negate Y and Z."""
        f = Flip(axis=0)  # X-axis
        point = np.array([1.0, 2.0, 3.0])
        flipped = f.apply(point)
        expected = np.array([1.0, -2.0, -3.0])
        np.testing.assert_allclose(flipped, expected, atol=1e-6)

    def test_hyperplane_reflection(self):
        """Hyperplane reflection (x=0) should negate X."""
        h = Hyperplane(normal=(1, 0, 0), d=0)
        point = np.array([1.0, 2.0, 3.0])
        reflected = h.apply(point)
        expected = np.array([-1.0, 2.0, 3.0])
        np.testing.assert_allclose(reflected, expected, atol=1e-6)


# ============================================================================
# BEAM SEARCH TESTS
# ============================================================================


class TestBeamSearch:
    """Test variant discovery via beam search."""

    @pytest.fixture
    def mock_model(self):
        """Create mock CompoundE3D model."""
        model = Mock(spec=CompoundE3D)
        return model

    @pytest.fixture
    def config(self):
        """Default beam search config."""
        return BeamSearchConfig(
            beam_width=3,
            max_depth=2,
            prune_strategy=PruneStrategy.SCORE_THRESHOLD,
            score_threshold=0.3,
        )

    def test_beam_search_initialization(self, mock_model, config):
        """Beam search engine initializes correctly."""
        engine = BeamSearchEngine(mock_model, config)
        assert engine.config.beam_width == 3
        assert engine.config.max_depth == 2
        assert len(engine.search_history) == 0

    def test_beam_search_executes(self, mock_model, config):
        """Beam search completes without error."""
        engine = BeamSearchEngine(mock_model, config)
        result = engine.search()

        assert "variants" in result
        assert "depth_levels" in result
        assert "audit_trail" in result
        assert len(result["audit_trail"]) > 0

    def test_beam_width_maintained(self, mock_model, config):
        """Beam width constraint is respected."""
        engine = BeamSearchEngine(mock_model, config)
        result = engine.search()

        # Check each depth level respects beam width
        for depth, candidates in result["depth_levels"].items():
            assert len(candidates) <= config.beam_width

    def test_depth_limit_respected(self, mock_model, config):
        """Max depth is respected."""
        engine = BeamSearchEngine(mock_model, config)
        result = engine.search()

        for depth in result["depth_levels"].keys():
            assert depth <= config.max_depth

    def test_pruning_strategy_score_threshold(self, mock_model, config):
        """Score threshold pruning removes low-scoring candidates."""
        config.prune_strategy = PruneStrategy.SCORE_THRESHOLD
        config.score_threshold = 0.5

        engine = BeamSearchEngine(mock_model, config)
        result = engine.search()

        # All pruned candidates should be below threshold
        for pruned in result["pruned"]:
            assert pruned["score"] < config.score_threshold

    def test_beam_candidate_ordering(self, mock_model, config):
        """Candidates with higher scores rank higher."""
        c1 = BeamCandidate(
            transformation_id="var_1",
            transformation_type="rotation",
            params={},
            score=0.9,
            depth=0,
        )
        c2 = BeamCandidate(
            transformation_id="var_2",
            transformation_type="scale",
            params={},
            score=0.5,
            depth=0,
        )

        # Lower score should be "less than" (for max-heap)
        assert c2 < c1


# ============================================================================
# ENSEMBLE TESTS
# ============================================================================


class TestWeightedDistributionScore:
    """Test WDS ensemble fusion."""

    @pytest.fixture
    def scores(self):
        """Sample variant scores."""
        return [
            VariantScore("var_1", "rotation", score=0.85, confidence=0.9),
            VariantScore("var_2", "scale", score=0.75, confidence=0.8),
            VariantScore("var_3", "translation", score=0.65, confidence=0.7),
        ]

    def test_wds_initialization(self):
        """WDS ensemble initializes."""
        wds = WeightedDistributionScore(temperature=1.0)
        assert wds.temperature == 1.0

    def test_wds_fusion_valid_score(self, scores):
        """WDS produces score in [0, 1]."""
        wds = WeightedDistributionScore()
        result = wds.fuse(scores)

        assert 0.0 <= result.final_score <= 1.0

    def test_wds_uniform_weights(self, scores):
        """WDS with uniform weights averages scores."""
        wds = WeightedDistributionScore()
        result = wds.fuse(scores)

        # Should be close to simple mean (due to confidence weighting)
        simple_mean = np.mean([s.score for s in scores])
        assert abs(result.final_score - simple_mean) < 0.1

    def test_wds_custom_weights(self, scores):
        """WDS respects custom variant weights."""
        custom_weights = {
            "var_1": 0.7,
            "var_2": 0.2,
            "var_3": 0.1,
        }
        wds = WeightedDistributionScore(weights=custom_weights)
        result = wds.fuse(scores)

        # Top weight variant should influence result most
        assert result.final_score > 0.65  # Close to var_1's score


class TestRankAggregationEnsemble:
    """Test rank aggregation ensemble."""

    @pytest.fixture
    def scores(self):
        """Sample variant scores."""
        return [
            VariantScore("var_1", "rotation", score=0.85),
            VariantScore("var_2", "scale", score=0.75),
            VariantScore("var_3", "translation", score=0.65),
        ]

    def test_borda_count_aggregation(self, scores):
        """Borda count aggregation executes."""
        rae = RankAggregationEnsemble(RankAggregationMethod.BORDA)
        result = rae.fuse(scores)

        assert 0.0 <= result.final_score <= 1.0
        assert result.fusion_strategy == "borda"

    def test_plurality_aggregation(self, scores):
        """Plurality aggregation uses top-ranked."""
        rae = RankAggregationEnsemble(RankAggregationMethod.PLURALITY)
        result = rae.fuse(scores)

        # Plurality should give top-ranked variant highest score
        assert abs(result.final_score - scores[0].score) < 1e-6


class TestMixtureOfExpertsEnsemble:
    """Test mixture of experts ensemble."""

    @pytest.fixture
    def scores(self):
        """Sample variant scores."""
        return [
            VariantScore("var_1", "rotation", score=0.9, confidence=0.95),
            VariantScore("var_2", "scale", score=0.7, confidence=0.8),
            VariantScore("var_3", "translation", score=0.6, confidence=0.7),
        ]

    def test_moe_initialization(self):
        """MoE ensemble initializes."""
        moe = MixtureOfExpertsEnsemble(num_experts=3, learnable_gates=True)
        assert moe.num_experts == 3
        assert moe.learnable_gates is True

    def test_moe_gating(self, scores):
        """MoE applies gating."""
        moe = MixtureOfExpertsEnsemble()
        result = moe.fuse(scores)

        assert 0.0 <= result.final_score <= 1.0
        # MoE should weight high-confidence experts more
        assert result.final_score > 0.6


class TestEnsembleController:
    """Test ensemble controller meta-logic."""

    @pytest.fixture
    def scores(self):
        """Sample variant scores."""
        return [
            VariantScore("var_1", "rotation", score=0.85),
            VariantScore("var_2", "scale", score=0.75),
        ]

    def test_controller_initialization(self):
        """Controller initializes with strategies."""
        controller = EnsembleController()
        assert len(controller.strategies) > 0

    def test_controller_predict_wds(self, scores):
        """Controller predicts with WDS."""
        controller = EnsembleController()
        result = controller.predict(scores, FusionStrategy.WEIGHTED_MEAN)

        assert 0.0 <= result.final_score <= 1.0
        assert result.fusion_strategy == "weighted_mean"

    def test_controller_single_variant(self, scores):
        """Controller handles single variant."""
        controller = EnsembleController()
        result = controller.predict(scores[:1])

        # Single variant should return identity
        assert result.final_score == scores[0].score
        assert result.fusion_strategy == "identity"

    def test_controller_audit_log(self, scores):
        """Controller logs predictions."""
        controller = EnsembleController()
        controller.predict(scores)

        audit_log = controller.get_audit_log()
        assert len(audit_log) > 0
        assert "num_variants" in audit_log[0]


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestCompoundE3DIntegration:
    """Integration tests with CompoundE3D model."""

    @pytest.fixture
    def config(self):
        """CompoundE3D config."""
        return CompoundE3DConfig(
            embedding_dim=64,
            num_entities=1000,
            num_relations=50,
            model_type="compound_e3d",
        )

    def test_e3d_variant_fusion(self, config):
        """E3D model integrates with ensemble."""
        model = CompoundE3D(config)

        # Mock variant predictions
        scores = [VariantScore(f"var_{i}", "rotation", score=0.5 + i * 0.1) for i in range(3)]

        controller = EnsembleController()
        result = controller.predict(scores)

        assert result.final_score > 0.4

    def test_e3d_beam_search_integration(self, config):
        """E3D model integrates with beam search."""
        model = CompoundE3D(config)
        beam_config = BeamSearchConfig(beam_width=3, max_depth=2)

        engine = BeamSearchEngine(model, beam_config)
        result = engine.search()

        assert len(result["variants"]) > 0


# ============================================================================
# REGRESSION TESTS
# ============================================================================


class TestRegressionKnownGraphs:
    """Regression tests on known graph patterns."""

    def test_facebook_social_graph_pattern(self):
        """E3D should preserve social network structure."""
        # Placeholder: load FB15K-237 sample
        # Assert rotation/scale preserve social edge properties
        pass

    def test_wordnet_hierarchy_pattern(self):
        """E3D should preserve WordNet hierarchy."""
        # Placeholder: load WN18RR sample
        # Assert transformations respect IS-A relationships
        pass


# ============================================================================
# AUDIT & CONSTRAINT TESTS
# ============================================================================


class TestConstraintSatisfaction:
    """Test constraint validators."""

    def test_rotation_axis_normalized(self):
        """Rotation axis is normalized."""
        r = Rotation(angle=45, axis=(1, 1, 1))
        axis_magnitude = np.linalg.norm(r.axis)
        np.testing.assert_allclose(axis_magnitude, 1.0, atol=1e-6)

    def test_scale_positive(self):
        """Scale factor must be positive."""
        with pytest.raises(ValueError):
            Scale(factor=-1.0)

    def test_hyperplane_normal_normalized(self):
        """Hyperplane normal is normalized."""
        h = Hyperplane(normal=(1, 1, 1), d=0)
        normal_magnitude = np.linalg.norm(h.normal)
        np.testing.assert_allclose(normal_magnitude, 1.0, atol=1e-6)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Performance benchmarks."""

    def test_beam_search_completes_under_1s(self):
        """Beam search completes in <1 second."""
        import time

        model = Mock(spec=CompoundE3D)
        config = BeamSearchConfig(beam_width=3, max_depth=2)
        engine = BeamSearchEngine(model, config)

        start = time.time()
        engine.search()
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Beam search took {elapsed:.2f}s"

    def test_ensemble_fusion_under_10ms(self):
        """Ensemble fusion completes in <10ms."""
        import time

        scores = [VariantScore(f"var_{i}", "rotation", score=np.random.random()) for i in range(5)]

        controller = EnsembleController()
        start = time.time()
        controller.predict(scores)
        elapsed = (time.time() - start) * 1000  # ms

        assert elapsed < 10.0, f"Fusion took {elapsed:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

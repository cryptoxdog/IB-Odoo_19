"""Pure-Python regression tests for Linda's local Haversine-curve estimator."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).parents[1] / "plasticos_logistics" / "services"
PACKAGE_NAME = "linda_test_services"


def _load_service(name: str):
    spec = importlib.util.spec_from_file_location(f"{PACKAGE_NAME}.{name}", SERVICES_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package_spec = importlib.util.spec_from_loader(PACKAGE_NAME, loader=None)
package = importlib.util.module_from_spec(package_spec)
package.__path__ = [str(SERVICES_DIR)]
sys.modules[PACKAGE_NAME] = package
freight_geometry = _load_service("freight_geometry")
freight_estimation = _load_service("freight_estimation")

NOW = datetime(2026, 9, 19, tzinfo=UTC)


def _evidence(identifier: int, amount: float, *, age_days: int = 1, origin=(0.0, 0.0), destination=(0.0, 1.0)):
    return freight_estimation.FreightEvidence(
        source_load_id=identifier,
        carrier_id=identifier,
        amount=amount,
        currency_id=1,
        origin_latitude=origin[0],
        origin_longitude=origin[1],
        destination_latitude=destination[0],
        destination_longitude=destination[1],
        occurred_at=NOW - timedelta(days=age_days),
        evidence_kind="executed_actual",
    )


def _estimate(evidence):
    return freight_estimation.estimate_haversine_curve(
        origin_latitude=0.0,
        origin_longitude=0.0,
        destination_latitude=0.0,
        destination_longitude=1.0,
        currency_id=1,
        evidence=evidence,
        now=NOW,
    )


def test_exact_lane_observation_produces_nonbinding_observed_distribution():
    proposal = _estimate([_evidence(1, 1200.0)])
    assert proposal.status == "succeeded"
    assert proposal.method == "exact_lane"
    assert proposal.haversine_miles == pytest.approx(69.093419, abs=0.0001)
    assert proposal.estimate_floor == proposal.estimate_target == proposal.estimate_ceiling == 1200.0
    assert proposal.pricing_assumption == proposal.estimate_target
    assert proposal.evidence_summary["exact_lane_executed_count"] == 1


def test_haversine_similarity_and_recency_weight_the_target_without_fixed_rate_per_mile():
    proposal = _estimate(
        [
            _evidence(1, 1000.0, age_days=1),
            _evidence(2, 2000.0, age_days=400, origin=(30.0, 30.0), destination=(30.0, 31.0)),
        ]
    )
    assert proposal.status == "succeeded"
    assert 1000.0 < proposal.estimate_target < 2000.0
    assert proposal.estimate_target < 1100.0
    assert proposal.reasoning_summary["formula"] == "inverse_haversine_lane_distance_times_exponential_recency"


def test_currency_is_not_silently_mixed_or_converted():
    foreign = _evidence(1, 1200.0)
    foreign = freight_estimation.FreightEvidence(**{**foreign.__dict__, "currency_id": 2})
    proposal = _estimate([foreign])
    assert proposal.status == "insufficient_evidence"
    assert proposal.failure_code == "insufficient_matching_currency_evidence"
    assert proposal.currency_id is None


def test_identical_input_and_evidence_have_stable_request_fingerprint():
    first = _estimate([_evidence(1, 1200.0)])
    second = _estimate([_evidence(1, 1200.0)])
    assert first.request_fingerprint == second.request_fingerprint


def test_invalid_requested_coordinates_are_rejected_not_coerced():
    with pytest.raises(freight_geometry.FreightCoordinateError):
        freight_estimation.estimate_haversine_curve(
            origin_latitude=None,
            origin_longitude=0,
            destination_latitude=0,
            destination_longitude=1,
            currency_id=1,
            evidence=[],
            now=NOW,
        )

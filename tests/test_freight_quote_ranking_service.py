"""Pure-Python regression tests for Linda's recommendation-only quote ranking."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SERVICE_PATH = Path(__file__).parents[1] / "plasticos_logistics" / "services" / "freight_quote_ranking.py"
SPEC = importlib.util.spec_from_file_location("freight_quote_ranking_service", SERVICE_PATH)
ranking_service = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = ranking_service
SPEC.loader.exec_module(ranking_service)

NOW = datetime(2026, 9, 19, tzinfo=UTC)


def _quote(identifier: int, amount: float | None, **overrides):
    values = {
        "quote_id": identifier,
        "carrier_id": identifier,
        "amount": amount,
        "currency_id": 1,
        "response_kind": "quote",
        "lifecycle_state": "active",
        "valid_until": NOW + timedelta(days=1),
        "responded_at": NOW - timedelta(hours=1),
        "timeliness": "in_window",
        "context_current": True,
        "carrier_active": True,
        "carrier_blocked": False,
    }
    values.update(overrides)
    return ranking_service.QuoteCandidate(**values)


def _history(carrier_id=1, amount=100.0):
    return ranking_service.LaneOutcome(
        carrier_id=carrier_id,
        amount=amount,
        currency_id=1,
        occurred_at=NOW - timedelta(days=1),
    )


def test_lower_current_price_with_comparable_history_is_recommended_first():
    rankings = ranking_service.rank_quotes(
        quotes=[_quote(1, 100.0), _quote(2, 125.0)], lane_outcomes=[_history()], required_currency_id=1, now=NOW
    )
    assert [item.quote_id for item in rankings] == [1, 2]
    assert rankings[0].eligible
    assert rankings[0].score > rankings[1].score
    assert rankings[0].reasons[-1] == "policy=linda-quote-rank-v1"


def test_invalid_or_stale_quote_is_excluded_from_recommendation_not_repaired():
    rankings = ranking_service.rank_quotes(
        quotes=[
            _quote(1, 100.0),
            _quote(2, None, response_kind="no_capacity"),
            _quote(3, 95.0, context_current=False),
            _quote(4, 90.0, valid_until=NOW - timedelta(seconds=1)),
        ],
        lane_outcomes=[_history()],
        required_currency_id=1,
        now=NOW,
    )
    assert rankings[0].quote_id == 1
    by_id = {item.quote_id: item for item in rankings}
    assert by_id[2].reasons == ["response_is_not_a_quote", "quote_price_or_currency_missing"]
    assert "request_context_is_stale" in by_id[3].reasons
    assert "quote_is_expired" in by_id[4].reasons


def test_currency_mismatch_is_ineligible_without_silent_conversion():
    rankings = ranking_service.rank_quotes(
        quotes=[_quote(1, 100.0), _quote(2, 1.0, currency_id=2)],
        lane_outcomes=[_history()],
        required_currency_id=1,
        now=NOW,
    )
    by_id = {item.quote_id: item for item in rankings}
    assert by_id[1].price_score == 1.0
    assert by_id[2].eligible is False
    assert by_id[2].reasons == ["quote_currency_mismatch"]


def test_ranking_never_changes_the_selected_or_award_state():
    ranking = ranking_service.rank_quotes(
        quotes=[_quote(1, 100.0)], lane_outcomes=[_history()], required_currency_id=1, now=NOW
    )[0]
    assert set(ranking.as_dict()) == {
        "quote_id",
        "eligible",
        "score",
        "price_score",
        "lane_history_score",
        "carrier_history_score",
        "recency_score",
        "timeliness_score",
        "reasons",
    }

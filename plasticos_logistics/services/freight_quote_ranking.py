"""Transparent recommendation-only ranking for eligible Linda freight quotes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import exp

RANKING_POLICY_VERSION = "linda-quote-rank-v1"
RECENCY_HALF_LIFE_DAYS = 30.0


@dataclass(frozen=True)
class QuoteCandidate:
    quote_id: int
    carrier_id: int
    amount: float | None
    currency_id: int | None
    response_kind: str
    lifecycle_state: str
    valid_until: datetime | None
    responded_at: datetime
    timeliness: str
    context_current: bool
    carrier_active: bool
    carrier_blocked: bool


@dataclass(frozen=True)
class LaneOutcome:
    carrier_id: int | None
    amount: float
    currency_id: int
    occurred_at: datetime


@dataclass(frozen=True)
class QuoteRanking:
    quote_id: int
    eligible: bool
    score: float | None
    price_score: float | None
    lane_history_score: float | None
    carrier_history_score: float | None
    recency_score: float | None
    timeliness_score: float | None
    reasons: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def rank_quotes(
    *,
    quotes: Iterable[QuoteCandidate],
    lane_outcomes: Iterable[LaneOutcome],
    required_currency_id: int,
    now: datetime | None = None,
) -> list[QuoteRanking]:
    """Rank only valid, current-context quote evidence; never select or award it."""
    now = _utc(now or datetime.now(UTC))
    candidates = list(quotes)
    outcomes = list(lane_outcomes)
    eligible = [quote for quote in candidates if not _ineligibility_reasons(quote, now, required_currency_id)]
    eligible_amounts_by_currency = _amounts_by_currency(eligible)
    result = []
    for quote in candidates:
        reasons = _ineligibility_reasons(quote, now, required_currency_id)
        if reasons:
            result.append(QuoteRanking(quote.quote_id, False, None, None, None, None, None, None, reasons))
            continue
        if quote.currency_id is None or quote.amount is None:
            raise ValueError("Eligible quote is missing a required currency or amount.")
        same_currency = eligible_amounts_by_currency[quote.currency_id]
        price_score = _price_score(quote.amount, same_currency)
        lane_history_score = _lane_history_score(quote, outcomes, now)
        carrier_history_score = _carrier_history_score(quote, outcomes, now)
        recency_score = exp(
            -max(0.0, (now - _utc(quote.responded_at)).total_seconds() / 86400.0) / RECENCY_HALF_LIFE_DAYS
        )
        timeliness_score = {"in_window": 1.0, "unknown": 0.6, "late": 0.2}[quote.timeliness]
        score = round(
            0.55 * price_score
            + 0.20 * lane_history_score
            + 0.15 * carrier_history_score
            + 0.05 * recency_score
            + 0.05 * timeliness_score,
            6,
        )
        result.append(
            QuoteRanking(
                quote.quote_id,
                True,
                score,
                round(price_score, 6),
                round(lane_history_score, 6),
                round(carrier_history_score, 6),
                round(recency_score, 6),
                round(timeliness_score, 6),
                ["eligible_current_context", f"policy={RANKING_POLICY_VERSION}"],
            )
        )
    return sorted(
        result,
        key=lambda ranking: (
            not ranking.eligible,
            -(ranking.score or 0.0),
            ranking.quote_id,
        ),
    )


def _ineligibility_reasons(quote: QuoteCandidate, now: datetime, required_currency_id: int) -> list[str]:
    reasons = []
    if quote.response_kind != "quote":
        reasons.append("response_is_not_a_quote")
    if quote.lifecycle_state != "active":
        reasons.append("quote_is_not_active")
    if quote.amount is None or quote.amount <= 0 or quote.currency_id is None:
        reasons.append("quote_price_or_currency_missing")
    elif quote.currency_id != required_currency_id:
        reasons.append("quote_currency_mismatch")
    if not quote.context_current:
        reasons.append("request_context_is_stale")
    if quote.valid_until and _utc(quote.valid_until) < now:
        reasons.append("quote_is_expired")
    if not quote.carrier_active:
        reasons.append("carrier_is_inactive")
    if quote.carrier_blocked:
        reasons.append("carrier_is_blocked")
    return reasons


def _amounts_by_currency(quotes: list[QuoteCandidate]) -> dict[int, list[float]]:
    output: dict[int, list[float]] = {}
    for quote in quotes:
        if quote.currency_id is None or quote.amount is None:
            continue
        output.setdefault(quote.currency_id, []).append(quote.amount)
    return output


def _price_score(amount: float, values: list[float]) -> float:
    lower, upper = min(values), max(values)
    return 1.0 if lower == upper else 1.0 - ((amount - lower) / (upper - lower))


def _lane_history_score(quote: QuoteCandidate, outcomes: list[LaneOutcome], now: datetime) -> float:
    if quote.amount is None:
        return 0.0
    relevant = [outcome for outcome in outcomes if outcome.currency_id == quote.currency_id]
    if not relevant:
        return 0.5
    weighted_amount = _recency_weighted_average(relevant, now)
    difference = abs(quote.amount - weighted_amount) / max(weighted_amount, 1.0)
    return max(0.0, 1.0 - difference)


def _carrier_history_score(quote: QuoteCandidate, outcomes: list[LaneOutcome], now: datetime) -> float:
    if quote.amount is None:
        return 0.0
    carrier_outcomes = [outcome for outcome in outcomes if outcome.carrier_id == quote.carrier_id]
    if not carrier_outcomes:
        return 0.5
    max_support = 5
    support = min(1.0, len(carrier_outcomes) / max_support)
    weighted_amount = _recency_weighted_average(carrier_outcomes, now)
    difference = abs(quote.amount - weighted_amount) / max(weighted_amount, 1.0)
    return 0.5 * support + 0.5 * max(0.0, 1.0 - difference)


def _recency_weighted_average(outcomes: list[LaneOutcome], now: datetime) -> float:
    weighted = []
    for outcome in outcomes:
        age_days = max(0.0, (now - _utc(outcome.occurred_at)).total_seconds() / 86400.0)
        weighted.append((outcome.amount, exp(-age_days / RECENCY_HALF_LIFE_DAYS)))
    return sum(amount * weight for amount, weight in weighted) / sum(weight for _, weight in weighted)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

"""Shared durable-retry backoff policy for Gate-routed work.

One schedule serves both the Graph projection outbox and the enrichment
scheduler so a single operator-visible policy governs every durable retry:
1 min, 5 min, 15 min, 1 hour, 6 hours, 6 hours, then terminal failure.

Retries live here — around a durable operation record — never inside the
transport. ``plasticos_gate.services.gate_client`` stays single-shot on
purpose: layering HTTP retries under scheduler retries multiplies load
against a Gate that is already failing.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

#: Delay before attempt N+1, indexed by the number of attempts already made.
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (60, 300, 900, 3600, 21600, 21600)

#: Attempts allowed before an operation is terminally failed.
MAX_ATTEMPTS: int = len(RETRY_BACKOFF_SECONDS)

#: Fraction of the base delay used as symmetric jitter (+/-), to stop a batch
#: of operations failed by one outage from retrying in lockstep.
JITTER_RATIO: float = 0.2


def _jitter_seconds(base_seconds: int, jitter_ratio: float) -> float:
    """Return a symmetric jitter offset in seconds for ``base_seconds``.

    Uses ``secrets`` rather than ``random`` so no non-cryptographic RNG is
    introduced into the addon surface; the choice is about lint/security
    hygiene, not about cryptographic need.
    """
    span_ms = int(abs(base_seconds) * jitter_ratio * 1000)
    if span_ms <= 0:
        return 0.0
    return (secrets.randbelow(2 * span_ms + 1) - span_ms) / 1000.0


def next_retry_delay_seconds(
    attempt_count: int,
    *,
    jitter_ratio: float = JITTER_RATIO,
    apply_jitter: bool = True,
) -> float | None:
    """Return the delay before the next attempt, or ``None`` when exhausted.

    ``attempt_count`` is the number of attempts already made. ``None`` means the
    operation has spent its budget and must be marked terminally failed rather
    than retried forever.
    """
    if attempt_count < 0:
        attempt_count = 0
    if attempt_count >= MAX_ATTEMPTS:
        return None
    base = RETRY_BACKOFF_SECONDS[attempt_count]
    if not apply_jitter:
        return float(base)
    return max(1.0, base + _jitter_seconds(base, jitter_ratio))


def next_attempt_at(
    attempt_count: int,
    *,
    now: datetime,
    jitter_ratio: float = JITTER_RATIO,
    apply_jitter: bool = True,
) -> datetime | None:
    """Return the absolute next-attempt timestamp, or ``None`` when exhausted."""
    delay = next_retry_delay_seconds(attempt_count, jitter_ratio=jitter_ratio, apply_jitter=apply_jitter)
    if delay is None:
        return None
    return now + timedelta(seconds=delay)


def attempts_exhausted(attempt_count: int) -> bool:
    """Return True when ``attempt_count`` attempts have spent the retry budget."""
    return attempt_count >= MAX_ATTEMPTS

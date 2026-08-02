# Matching Degraded Mode (Mothball M3 / TASK-048)

## Purpose

When Gate matching is unavailable or transport fails, Odoo **must not** substitute local Neo4j/scoring results. Operators see an auditable `plasticos.match.run` in `retryable`, `failed`, or `degraded` state and may retry Gate explicitly.

## Failure classes

| Class | Run state | Operator action |
|---|---|---|
| `retryable` | `retryable` | Fix transient issue (timeout/network) → **Retry Gate Match** |
| `permanent` | `failed` | Fix ICP (`plasticos.gate.url`, matching enabled, SDK install) |
| `unknown` | `degraded` | Investigate; do **not** treat as empty success |

Availability statuses from `classify_gate_availability` (e.g. `missing_url`, `sdk_missing`, `matching_disabled`) are stored on `availability_status`.

## Hard rules

1. No silent fallback to `plasticos.buyer.matcher` / `_find_matches_local`.
2. No returning empty “success” without a match-run audit row.
3. Retries create a **new** run with `retry_of_id`; duplicate pending retries for the same parent are suppressed.
4. Bounded policy only — no background auto-retry loops in this phase.

## Operator steps

1. Open **Match Runs** or use intake **Open latest match run**.
2. Read `failure_class`, `availability_status`, and `error_message`.
3. Correct Gate/ICP if permanent; otherwise click **Retry Gate Match**.
4. Confirm new run reaches `ok` or a new classified failure (still audited).

## Validation

- `pytest -q tests/test_matching_degraded_mode.py tests/test_match_retry_idempotency.py`
- Module wiring / circular-deps checks still required before push.

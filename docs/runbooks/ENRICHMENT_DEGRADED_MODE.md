# Enrichment Degraded Mode (Mothball M4 / TASK-049)

## Purpose

Partner enrichment runs exclusively through Gate converge (`plasticos_gate`). Local crawl, extract, and inference execution paths are retired. Gate failures are classified onto `plasticos.enrichment.run` (`retryable` / `failed` / `degraded`) — never substituted with local AI/crawl results.

## Operator steps

1. Ensure Gate URL + enrichment ICP are configured (`plasticos.gate.enrichment_enabled`).
2. Execute enrichment on a run → success lands as `injected` or `review` (if auto-writeback off).
3. On failure, open the run, read `failure_class` / `availability_status` / `validation_issues`.
4. Click **Retry Gate Enrichment** after fixing transient or config issues.

## Hard rules

- No silent local fallback after Gate errors.
- Crons that previously ran local enrichment/inference are **inactive**.
- `plasticos_inference_engine` is not a dependency of `plasticos_enrichment`.

## Validation

`pytest -q tests/test_enrichment_degraded_mode.py tests/test_enrichment_gate_writeback.py`

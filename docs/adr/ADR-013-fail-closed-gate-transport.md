# ADR-013: Fail-Closed Gate Transport (No Silent Local Intelligence)

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** Odoo behavior when Gate or workers are unavailable or error
**Supersedes (documentation):** Pre-mothball “always fall back to local matcher/enrichment” language in track_b handoffs, READMEs, and agent guidance
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md) §2 (authority already superseded by ADR-003-single),
[ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md),
[ADR-015-persistence-shells-matching-enrichment.md](ADR-015-persistence-shells-matching-enrichment.md)

## Context

ADR-002 originally allowed in-Odoo engines as fallback. ADR-003-single removed that as **architectural authority**; M7 deleted local engine modules; M8 blocks reintroduction. Stale docs still told agents that Gate failure “silently” uses local engines — contradicting runtime and CI.

## Decision

### 1. Fail closed

When Gate matching/enrichment is disabled, unavailable, times out, or returns an unusable result:

1. Classify failure (`retryable` / `permanent` / `unknown` → operator-visible run state including `degraded` where applicable).
2. Persist audit fields on `plasticos.match.run` or `plasticos.enrichment.run`.
3. Raise `UserError` (or equivalent) to the operator — **do not** substitute empty success.
4. **Do not** invoke retired local matcher/enrichment scoring as authority.

### 2. Documentation supersession

The following claims are **false** under this ADR and must be treated as stale wherever found:

- “Odoo always falls back to a local engine if Gate is down.”
- “Until Track B exists, Odoo silently uses local matching/enrichment.”
- Acceptance criteria that require local fallback on Gate error (post-M7).

Authoritative replacements: ADR-003-single + this ADR + `ci/check_no_local_intelligence.py`.

### 3. ICP off is permanent-class failure

`plasticos.gate.matching_enabled=0` or `enrichment_enabled=0` → fail closed with clear reasons; not a cue to run local intelligence.

## Consequences

### Positive

- Operator sees honest degradation; no fake match/enrich success.
- Aligns docs, runtime, and M8 drift guards.

### Negative / constraints

- Gate outages block intelligence actions until retry — by design.
- Remaining stale doc sentences need cleanup under ADR-019.

### Implementation rules (agents)

1. Never reintroduce local Neo4j/YAML intelligence paths as fallback.
2. When editing track_b or ARCHITECTURE, delete silent-fallback language.
3. Preserve failure classification + retry UX on match/enrichment runs.

## References

- `plasticos_matching/models/match_orchestrator.py`
- `plasticos_enrichment/models/enrichment_run.py` (`action_execute`)
- `ci/check_no_local_intelligence.py`

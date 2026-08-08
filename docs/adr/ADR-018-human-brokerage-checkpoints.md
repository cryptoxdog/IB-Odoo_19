# ADR-018: Human Brokerage Checkpoints (Intake → Match → Offer)

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** Igor Beylin  
**Scope:** Phase-1 human-in-the-loop gates that automation must not skip  
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md),
[GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md),
[ADR-016-web-lead-triage-boundary.md](ADR-016-web-lead-triage-boundary.md)

## Context

Gate matching and enrichment increase autonomy risk. ADR-002 phased autonomy requires humans at brokerage control points until later phases graduate. Agents occasionally propose auto-send offers or skip match-line review.

## Decision

### 1. Phase 1 binding checkpoints

| Checkpoint | Required human action | Must not automate away in Phase 1 |
|------------|----------------------|-----------------------------------|
| HOT web lead | Review before/at intake handoff | Auto-create partners / skip review |
| Match lines | Review/select buyers after Gate match | Auto-send commercial offers from raw matches |
| Send Offer | Explicit `action_send_offers` (or successor) | Silent mass-send from Gate results |

Pipeline (Phase 1):

```
Web lead (local triage) → Human (HOT) → Intake
  → Match to Buyers (Odoo→Gate→CEG) → Human review match lines
  → Offer draft → Human Send Offer
```

### 2. Phase graduation

Moving to Phase 2 (smarter defaults) or Phase 3 (higher autonomy / Gate triage) requires roadmap criteria in `GATE_AUTONOMY_ROADMAP.md` and an ADR amendment — not feature flags hidden in modules.

### 3. Gate does not replace commercial consent

Successful Gate `match` or `converge` never implies permission to bind the company commercially without the Send Offer (or equivalent) human action in Phase 1–2.

## Consequences

### Positive

- Preserves brokerage control while intelligence is externalized.
- Clear agent non-goals for offer automation.

### Negative / constraints

- More operator clicks until phases graduate.

### Implementation rules (agents)

1. Do not auto-call send-offer from match persistence.
2. Do not remove match-line review UX without a phase ADR.
3. Partner deferral on HOT leads remains intentional (web-lead guard).

## References

- ADR-002 §3 phased autonomy
- `docs/GATE_AUTONOMY_ROADMAP.md`
- Intake match / offer module actions

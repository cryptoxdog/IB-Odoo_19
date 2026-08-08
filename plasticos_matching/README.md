---
component_id: "plasticos_matching"
component_name: "Plasticos Matching"
module_version: "19.0.3.0.1"
layer: "capability"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Gate match orchestrator and result store"
summary: "Triggers Gate action=match; persists runs/results for human review — scoring authority is CEG"
---

# Plasticos Matching

## Purpose

Gate **orchestrator + result store** for intake→buyer matching (ADR-015).  
Does **not** score buyers locally — Cognitive.Engine.Graphs (CEG) scores via Constellation Gate (`action=match`).

## Summary

- Odoo decides when to call Gate (ADR-010)
- `plasticos.match.orchestrator` builds/sends match packets (`plasticos_gate`)
- Persists `plasticos.match.run` / `plasticos.match.result` / exclusions for operator UX
- Fail-closed when Gate is unavailable (ADR-013) — no silent local matcher

## Structure
```
README.md
README.rst
__init__.py
__manifest__.py
migrations/
models/
security/
views/
```

## Dependencies

`base`, `mail`, `plasticos_base`, `plasticos_intake`, `plasticos_facility_profile`, `plasticos_gate`

## Models

`plasticos.match.result`, `plasticos.match.run`, `plasticos.match.exclusion` (+ abstract orchestrator)

## Related ADRs

- [ADR-011](../docs/adr/ADR-011-intelligence-action-topology.md) — `match` → CEG
- [ADR-013](../docs/adr/ADR-013-fail-closed-gate-transport.md) — no local fallback
- [ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md) — shell role
- [ADR-018](../docs/adr/ADR-018-human-brokerage-checkpoints.md) — human match-line review

## Related Documentation

- `ARCHITECTURE.md` — External Intelligence Boundary (Gate)
- `docs/track_b/02_cognitive_engine_graphs.md` — CEG worker contract

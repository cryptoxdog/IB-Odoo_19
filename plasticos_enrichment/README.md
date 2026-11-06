---
component_id: "plasticos_enrichment"
component_name: "Plasticos Enrichment"
module_version: "19.0.2.5.7"
layer: "capability"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Gate converge orchestrator and CRM writeback shell"
summary: "Triggers Gate action=converge; persists runs/provenance; allowlisted partner writeback — ranking is CEG health"
---

# Plasticos Enrichment

## Purpose

Gate **orchestrator + CRM writeback shell** for partner enrichment (ADR-015).
Intelligence executes in Enrichment.Inference.Engine (EIE) via Gate (`action=converge`).
**Which entities to enrich and in what order is not this module** — that ranking lives in CEG `engine/health/` (ADR-009).

## Summary

- Odoo decides when to call Gate (per-run execute/retry — ADR-010)
- Daily/inference crons are `active=False` and no-op (M4); not the product ranking design
- Allowlisted merge-not-overwrite writeback + provenance (ADR-012)
- Fail-closed when Gate is unavailable (ADR-013) — local crawl/inference retired (M7)

## Structure
```
README.md
__init__.py
__manifest__.py
data/
knowledge_base/
models/
security/
tests/
views/
```

## Dependencies

`plasticos_base`, `plasticos_gate`, `base`, `mail`, `contacts`, `plasticos_material_profile`
(Do **not** depend on retired `plasticos_inference_engine`.)

## Install

`auto_install` is `True`. Odoo installs this module once every dependency is present: `plasticos_base`, `plasticos_gate`, `base`, `mail`, `contacts`, and `plasticos_material_profile`. No production addon depends on it. The test pack names it, and that pack is `installable: False`. The flag is what puts the converge shell on a database that already has Gate and material profiles when the installer does not name this module. `plasticos_matching` uses the same flag for the match shell. The Docker roster also lists enrichment explicitly, at position 17 in `default_install_order` (`config/odoo_module_order.yaml`), so the smoke install names it as well as relying on the flag.

## Models

`plasticos.enrichment.run`, `plasticos.enrichment.source`, `plasticos.enrichment.provenance`, `plasticos.enrichment.extraction`, `plasticos.enrichment.service`

## Related ADRs

- [ADR-009](../docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md) — ranking not in this repo
- [ADR-012](../docs/adr/ADR-012-crm-writeback-allowlist-provenance.md) — writeback rules
- [ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md) — shell role
- [ADR-017](../docs/adr/ADR-017-constellation-enrichment-feedback-channel.md) — CEG health → EIE channel

## Related Documentation

- `ARCHITECTURE.md` — External Intelligence Boundary (Gate)
- `docs/track_b/03_enrichment_inference_engine.md` — EIE worker contract

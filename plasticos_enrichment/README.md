---
auto_generated: false
authority: derived-index
component_id: plasticos_enrichment
component_name: PlastOS Buyer CRM Enrichment Engine
module_version: 19.0.2.5.7
layer: 2
installable: true
auto_install: true
application: false
depends:
  - plasticos_base
  - plasticos_gate
  - base
  - mail
  - contacts
  - plasticos_material_profile
models_owned:
  - plasticos.enrichment.run
  - plasticos.enrichment.source
  - plasticos.enrichment.provenance
  - plasticos.enrichment.extraction
  - plasticos.enrichment.service
models_extended:
  - res.partner
crons:
  - cron_enrichment_daily
  - cron_inference_standalone
---

# PlastOS Buyer CRM Enrichment Engine

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

The Odoo shell for partner enrichment. Odoo decides when to ask, sends a converge request through Gate, stores the run and its provenance, and writes back only allowlisted partner fields without overwriting existing values. Enrichment itself runs outside Odoo. Which entities to enrich, and in what order, is not decided here ([ADR-009](../docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md)).

## How it works

- **Run.** `plasticos.enrichment.run` (`models/enrichment_run.py`) is one enrichment attempt for a partner. States: `draft`, `crawling`, `extracting`, `validated`, `review`, `injected`, `retryable`, `degraded`, `failed`.
- **Execute.** `action_execute()` classifies Gate availability for the enrichment capability, builds a converge request with `plasticos_gate.services.gate_builders.build_converge_request`, and calls `plasticos_gate.services.gate_client.send_converge_action`. A Gate failure is recorded on the run as `retryable`, `failed`, or `degraded` and raised as a user error. There is no local fallback.
- **Proposal.** By default a usable response leaves the run in `review` with the proposed partner fields stored in `gate_proposal`. Only when both `plasticos.gate.auto_writeback` and `plasticos.gate.auto_writeback_operator_approved` are set (both seeded `0`) are the allowlisted fields written at once and the run marked `injected`.
- **Retry.** `action_retry_enrichment()` accepts a `retryable`, `failed`, or `degraded` run, advances `gate_attempt` so Gate sees a new operation identity, and calls `action_execute()` again.
- **Inject.** `action_inject()` is the allowlisted writeback. For a Gate run in `review` it applies only the stored proposal. `_apply_converge_writeback` drops any field outside the partner allowlist, fills only empty values, and records a `plasticos.enrichment.provenance` row ([ADR-012](../docs/adr/ADR-012-crm-writeback-allowlist-provenance.md)).
- **Retired local paths.** `action_run_inference()` raises a user error. The crawl, extract, and inference methods on `plasticos.enrichment.service` raise. `action_cron_enrich_pending()` and `action_cron_inference_only()` log and return.
- **Install hook.** `post_init_hook` in `hooks.py` adds the enrichment manager group to `plasticos_base.user_system_cron`.

`knowledge_base/` holds YAML material knowledge files shipped with the module.

## Models

| Model                             | Kind            | File                              |
| --------------------------------- | --------------- | --------------------------------- |
| `plasticos.enrichment.run`        | owned           | `models/enrichment_run.py`        |
| `plasticos.enrichment.source`     | owned           | `models/enrichment_source.py`     |
| `plasticos.enrichment.provenance` | owned           | `models/enrichment_provenance.py` |
| `plasticos.enrichment.extraction` | owned           | `models/enrichment_extraction.py` |
| `plasticos.enrichment.service`    | owned, abstract | `models/enrichment_service.py`    |
| `res.partner`                     | extended        | `models/res_partner.py`           |

## Runtime

- Crons in `data/cron.xml`: `cron_enrichment_daily` and `cron_inference_standalone`, both `active` false. Their methods log and return.
- `auto_install` is true. Odoo installs it once `plasticos_base`, `plasticos_gate`, `base`, `mail`, `contacts`, and `plasticos_material_profile` are installed.
- Gate configuration lives in `plasticos_gate`. `plasticos.gate.enrichment_enabled` (seeded `1`) turns Gate enrichment off when set to `0`.

## Boundaries

- No local crawl, extraction, or inference runs in this module.
- No ranking or selection of which partners to enrich ([ADR-009](../docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md)).
- No direct call to an enrichment engine. Every request goes through `plasticos_gate` ([ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md)).
- The CEG health → Gate → EIE feedback channel is defined in [ADR-017](../docs/adr/ADR-017-constellation-enrichment-feedback-channel.md), not in this module.

## Read next

- [`models/enrichment_run.py`](models/enrichment_run.py)
- [`../plasticos_gate/README.md`](../plasticos_gate/README.md)
- [ADR-009](../docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md), [ADR-012](../docs/adr/ADR-012-crm-writeback-allowlist-provenance.md), [ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md), [ADR-017](../docs/adr/ADR-017-constellation-enrichment-feedback-channel.md)

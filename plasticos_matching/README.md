---
auto_generated: false
authority: derived-index
component_id: plasticos_matching
component_name: PlasticOS Matching
module_version: 19.0.3.1.5
layer: 2
installable: true
auto_install: true
application: false
depends:
  - base
  - mail
  - plasticos_base
  - plasticos_intake
  - plasticos_facility_profile
  - plasticos_gate
models_owned:
  - plasticos.match.run
  - plasticos.match.result
  - plasticos.match.result.writer
  - plasticos.match.exclusion
  - plasticos.match.orchestrator
models_extended:
  - plasticos.intake
  - plasticos.match.result
crons:
  - ir_cron_expire_exclusions
---

# PlasticOS Matching

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Runs buyer matching for a supplier's material through Constellation Gate and keeps an auditable record of every run and every result. Odoo decides when to ask ([ADR-010](../docs/adr/ADR-010-odoo-consumer-trigger-ownership.md)). Scoring happens outside Odoo. This module stores what Gate returns.

## How it works

- **Orchestrator.** `plasticos.match.orchestrator` (`models/match_orchestrator.py`) is Gate-only. There is no local scoring, no Neo4j candidate search, and no silent fallback to a local `buyer.matcher` ([ADR-013](../docs/adr/ADR-013-fail-closed-gate-transport.md)).
- **Two entry points, one execution.**
  - `run_match_for_intake(intake, ...)` is called by the `plasticos.intake` override of `action_match_to_buyers()` (`models/intake_extension.py`).
  - `run_match_for_lot(...)` is called by the CRM Opportunity path in `plasticos_crm_bridge` with a frozen lot snapshot.
  - Both go through `_run_gate_match`, which classifies Gate availability, sends the request with `plasticos_gate.services.gate_client.send_match_action`, and records a `plasticos.match.run`.
- **Failure receipt.** On a Gate failure the request transaction is rolled back, and the failed run is written on an owned, committed cursor (`_rollback_then_persist_failed_run_durable`). The run survives the rollback that the raised user error triggers. Its state is `retryable`, `failed`, or `degraded`. `retry_match_run` and `action_retry_match` build a new run from it.
- **Exclusions.** After a successful response, buyers listed in `plasticos.match.exclusion` for that supplier are dropped. Exclusions record QC disputes, legal holds, and declined quality, with an optional expiry.
- **Results.** `persist_review_results` asks `plasticos.match.result.writer` to create `plasticos.match.result` rows (state `pending`, then `accepted`, `rejected`, or `expired` on review) and, when there is an intake, the `plasticos.intake.match` display lines. The writer never discovers, scores, or ranks a buyer.
- **Lineage.** `models/match_result_link.py` adds `match_run_id` (`ondelete="restrict"`) to `plasticos.match.result`, so a run cannot be deleted under its results.
- **Digest.** `canonical_digest.py` computes the deterministic receipt digest. It does not import Odoo.

Run states: `pending`, `ok`, `retryable`, `failed`, `degraded`.

## Models

| Model                           | Kind            | File                            |
| ------------------------------- | --------------- | ------------------------------- |
| `plasticos.match.orchestrator`  | owned, abstract | `models/match_orchestrator.py`  |
| `plasticos.match.run`           | owned           | `models/match_run.py`           |
| `plasticos.match.result`        | owned           | `models/match_result.py`        |
| `plasticos.match.result.writer` | owned, abstract | `models/match_result_writer.py` |
| `plasticos.match.exclusion`     | owned           | `models/match_exclusion.py`     |
| `plasticos.intake`              | extended        | `models/intake_extension.py`    |
| `plasticos.match.result`        | extended        | `models/match_result_link.py`   |

## Runtime

- Cron: `ir_cron_expire_exclusions`, daily, `active` false. It is declared in `views/match_exclusion_views.xml`, not under `data/`, and calls `_cron_expire_temporary_exclusions()`.
- Gate configuration lives in `plasticos_gate`. `action_match_to_buyers` refuses in the UI when Gate is unavailable.
- `auto_install` is true.

## Boundaries

- This module stores and audits match runs ([ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md)). It is not the matching authority.
- It talks only to `plasticos_gate`. It opens no HTTP connection of its own.
- It does not create offers. Reviewed results become draft offers through `plasticos_crm_bridge`.
- `plasticos_matching` does not depend on `plasticos_crm_bridge`.

## Read next

- [`models/match_orchestrator.py`](models/match_orchestrator.py)
- [`../plasticos_gate/README.md`](../plasticos_gate/README.md)
- [`../plasticos_crm_bridge/README.md`](../plasticos_crm_bridge/README.md)
- [ADR-010](../docs/adr/ADR-010-odoo-consumer-trigger-ownership.md), [ADR-013](../docs/adr/ADR-013-fail-closed-gate-transport.md), [ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md)

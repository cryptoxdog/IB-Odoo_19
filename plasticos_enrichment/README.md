---
auto_generated: false
authority: derived-index
component_id: plasticos_enrichment
component_name: PlastOS Buyer CRM Enrichment Engine
module_version: 19.0.2.7.2
layer: 2
installable: true
auto_install: true
application: false
depends:
  - plasticos_base
  - plasticos_gate
  - base
  - base_setup
  - mail
  - contacts
  - plasticos_material_profile
  - plasticos_facility_profile
models_owned:
  - plasticos.enrichment.run
  - plasticos.enrichment.source
  - plasticos.enrichment.provenance
  - plasticos.enrichment.extraction
  - plasticos.enrichment.service
  - plasticos.enrichment.sweep
models_extended:
  - res.partner
  - plasticos.facility.profile
  - res.config.settings
crons:
  - cron_enrichment_daily
  - cron_inference_standalone
  - cron_enrichment_sweep_send
  - cron_enrichment_sweep_results
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
- **Converge v2 targets.** When `plasticos.gate.converge_contract=v2`, a run targets its partner or one of its facility profiles (`facility_profile_id`). The run partner is the profile's partner. A material profile cannot start a v2 run: the cartridge's `material` subject is a facility's capability (ADR-012 amendment 2026-11-13 (d)). The **Enrich** button on the facility profile form creates the run. A facility profile with no partner cannot be enriched.
  - **Request.** The run asks for the mapped fields that are empty on the target. The partner uses the `plasticos_gate` `CONVERGE_V2_TARGETS` table. The facility profile is open by model definition: the run passes the model's field definitions (`_v2_field_defs`) and `plasticos_gate` derives the eligible fields (ADR-012 amendment 2026-11-13 (b)).
  - **Review.** The validated reply goes to `review` in `gate_proposal`. v2 never writes automatically.
  - **Approval.** `action_inject()` validates the stored reply again. It then writes only admitted `inferred` and `external_claim` values, with typed coercion. A number is written only in its governing unit, and only when the field accepts that unit. The governing unit is the value's stated unit, or else the cartridge's declared unit. A converted number's provenance keeps the original value and unit. A code is resolved to an existing master record, matched case-insensitively. A field that already has a value is not overwritten.
  - **Provenance.** Every considered field gets a provenance row with `target_model`, `target_res_id` and a status. The status is `written`, `skipped_immutable`, `skipped_unknown`, `skipped_conflicting`, `skipped_unit`, `skipped_unresolved_code`, `skipped_not_admitted` or `unmapped`.
  - **Failure.** A v1-shaped, malformed, or other-revision reply writes nothing; the run is `degraded` with the reason. A profile run under v1 never reaches Gate. ([ADR-012 amendment 2026-11-13](../docs/adr/ADR-012-crm-writeback-allowlist-provenance.md))
- **Scheduled sweep (off by default).** `plasticos.enrichment.sweep` (`models/enrichment_sweep.py`) is the Odoo side of the EIE buyer sweep. Contract: EIE `docs/contracts/enrichment-sweep.md` at `a606791`; ADR-012 amendment 2026-11-15.
  - **Send.** The nightly cron `_cron_send_sweep` reads the `plasticos.gate.sweep_*` settings, validated by `services/sweep_policy.py`. It selects buyer facility profiles (`customer_rank > 0` on the site or its company) that match the operator's filters. It drops profiles in review, inside the cooldown or pending in an open sweep, and puts the oldest enrichment first. It sends one `enrichment-sweep` with the profiles' current values. It needs converge v2 with a cartridge id, version and sha256 pin, and records that pin on the sweep.
  - **Collect.** The hourly cron `_cron_collect_results` pages `enrichment-sweep-results`; the first page sends no cursor. Each result goes through `plasticos.enrichment.run._v2_review_sweep_reply`, which ends in the same review step as an interactive run. It becomes one run in `review`, or `degraded` with the reason. Nothing is written before a human approves the run; approval re-validates the stored reply.
  - **Recorded per candidate.** EIE's skip reasons, send rejections and `stats` stay on the sweep.
  - **Refusals.** `sweep_not_found` marks the sweep `expired`. `disabled` and `sweep_store_unavailable` keep it open. Other refusals fail it.
  - **Idempotent.** A sweep_id and entity_id never create a second run.
  - **Where.** Settings: **Settings → PlasticOS Enrichment**. Switching it on: ADR-012 amendment 2026-11-15, item 9.
- **Bales are packaging.** For extracted materials, `normalize_material` maps `bale`, `bales` and `baled` to the Bales packaging type (`plasticos.packaging.type` code `bales`) with provenance, not to a form. Inject then gives that profile no form and never the `OTHER` fallback, the end state of `plasticos_material_profile` 19.0.5.11.14 (operator decision 2026-11-12). Merge still fills only empty fields.
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
| `plasticos.enrichment.sweep`      | owned           | `models/enrichment_sweep.py`      |
| `res.config.settings`             | extended        | `models/res_config_settings.py`   |
| `res.partner`                     | extended        | `models/res_partner.py`           |
| `plasticos.facility.profile`      | extended        | `models/profile_enrichment.py`    |

## Runtime

- Crons in `data/cron.xml`: `cron_enrichment_daily` and `cron_inference_standalone`, both `active` false. Their methods log and return.
- Crons in `data/sweep_data.xml`: `cron_enrichment_sweep_send` (daily) and `cron_enrichment_sweep_results` (hourly), both `active` false and also gated on `plasticos.gate.sweep_enabled` (seeded `0`). The same file seeds the sweep defaults: budget `5.0` USD, 50 buyers, 30-day cooldown.
- `auto_install` is true. Odoo installs it once `plasticos_base`, `plasticos_gate`, `base`, `mail`, `contacts`, `plasticos_material_profile` and `plasticos_facility_profile` are installed.
- Gate configuration lives in `plasticos_gate`. `plasticos.gate.enrichment_enabled` (seeded `1`) turns Gate enrichment off when set to `0`.

## Boundaries

- No local crawl, extraction, or inference runs in this module.
- No ranking of which partners to enrich ([ADR-009](../docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md)). The one exception is the scheduled sweep: operator filters choose which buyers are offered to EIE, ordered only by enrichment age (ADR-012 amendment 2026-11-15, item 7).
- No direct call to an enrichment engine. Every request goes through `plasticos_gate` ([ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md)).
- The CEG health → Gate → EIE feedback channel is defined in [ADR-017](../docs/adr/ADR-017-constellation-enrichment-feedback-channel.md), not in this module.

## Read next

- [`models/enrichment_run.py`](models/enrichment_run.py)
- [`../plasticos_gate/README.md`](../plasticos_gate/README.md)
- [ADR-009](../docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md), [ADR-012](../docs/adr/ADR-012-crm-writeback-allowlist-provenance.md), [ADR-015](../docs/adr/ADR-015-persistence-shells-matching-enrichment.md), [ADR-017](../docs/adr/ADR-017-constellation-enrichment-feedback-channel.md)

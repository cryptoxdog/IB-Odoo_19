# web_lead_context.md

## Purpose

This companion doc is pinned to `plasticos_web_leads/models/web_lead.py` and exists to keep agents from making well-intentioned but incorrect rewrites in one of the most workflow-sensitive files in IB-Odoo_19.

The file implements the inbound web lead pipeline for PlasticOS. It is not just a model with a form and a few helpers. It is a multi-stage orchestration layer that receives lead payloads, normalizes them with AI, optionally analyzes images, classifies leads as HOT or COLD, creates downstream intake records for HOT leads, preserves audit history, and protects processed records from mutation.

## Pipeline Architecture

`plasticos.web.lead` has two entry paths and one core processing pipeline.

### Entry point 1: `create_from_cognito(raw_payload)`

This is the primary ingestion path for raw Cognito submissions. It:
- derives or constructs a stable `lead_id`
- enforces idempotency by checking for an existing lead
- extracts raw company/contact/material fields from the payload
- extracts image URLs
- creates the `plasticos.web.lead` record in `received` state
- invokes `_run_triage_pipeline()`

This path is the high-complexity path. It is where AI normalization, vision analysis, deterministic classification, and HOT-lead intake creation happen.

### Entry point 2: `create_from_agent(payload)`

This is the legacy/pre-processed path. It accepts a payload that already contains decision and AI-derived structure. It:
- creates the lead from pre-normalized data
- uses `decision` from the payload
- sends HOT leads through `_process_hot_lead_simple()`
- marks COLD leads as `skipped`

This path is intentionally simpler. Do not try to “unify” it with the Cognito path unless you have explicit instruction and regression coverage.

## Core Triage Flow

The high-level flow in `_run_triage_pipeline()` is:

1. Load config from `plasticos.web.lead.config`
2. Run AI text normalization if enabled and keyed
3. Run image analysis if enabled, keyed, and images are present
4. Merge AI + vision signals via `_merge_ai_and_vision()`
5. Run deterministic classification via `classify_lead()` from `classification_engine.py`
6. Persist classification fields and audit payloads
7. If HOT, create intake and notify admin; if COLD, archive as `skipped`
8. Fetch and attach submitted images
9. Persist triage log and error state if anything fails

## What `config` Holds

`config = self.env["plasticos.web.lead.config"].sudo().get_config()` is not incidental. It controls runtime behavior.

Agents should assume this config object is the source of truth for at least:
- `ai_enabled`
- `vision_enabled`
- `openai_api_key`
- `openai_model`
- `openai_vision_model`
- `hot_min_lbs`
- `cold_max_lbs`
- `default_source_type`
- possible reviewer routing such as `intake_reviewer_id`
- helper methods such as `get_reject_materials()` and `get_reject_sources()`

Do not hardcode these values into `web_lead.py`. If behavior depends on thresholds, model names, rejects, or reviewer assignment, check config first.

## Classification Boundaries

`web_lead.py` does not own all classification logic. That boundary matters.

- `classify_lead()` lives in `classification_engine.py`
- text normalization lives in sibling module `ai_normalizer`
- image analysis lives in sibling module `image_analyzer`

If classification behavior is wrong, do not immediately rewrite `web_lead.py`. First identify whether the defect lives in payload extraction, merge logic, configuration, or the classification engine itself.

## Partner-Deferral Decision

The current design intentionally defers partner creation.

For HOT leads, the triage path creates an intake first and notifies admin for review. The code comment in `_process_hot_lead_triage()` is explicit:
- intake is created without partner
- company name is stored as `pending_company_name` on intake
- partner/material profile creation is deferred until buyer-matching workflow

This is not unfinished work. It is a deliberate architectural decision to avoid premature partner creation from noisy inbound leads.

### Practical rule

Do **not** reintroduce automatic partner creation into `create_from_cognito()`, `_run_triage_pipeline()`, `_process_hot_lead_triage()`, or `_process_hot_lead_simple()` unless the user explicitly asks for that behavior and regression tests are updated.

## `_find_or_create_partner()` Status

`_find_or_create_partner()` is explicitly marked:
- `DEPRECATED (2026-02-23)`
- not called by main flows
- retained for manual/utility use

Agents must not “wire it back in” just because it exists. Presence does not imply active ownership in the current workflow.

## Processed-Lead Guards

The `write()` and `unlink()` guards are core integrity protections.

### `write()` guard

If `state` is not being changed and the lead is already in `intake_created`, writes are blocked with a `UserError`. This preserves the handoff boundary between the lead record and downstream intake workflow.

### `unlink()` guard

Processed leads cannot be deleted once an intake exists. This preserves auditability.

Do not weaken these guards casually. They are business workflow protections, not incidental UX behavior.

## The Two Agent Trap Zones

### Trap 1: partner-deferral block

Agents often see HOT lead processing and assume a partner should be created immediately. That is wrong for the current architecture.

### Trap 2: `self.intake_id` double-write

In both `_create_intake_triage()` and `_create_intake_simple()`, the code links `self.intake_id = intake.id` after `Intake.create(...)`. Later, caller methods also write `{"intake_id": intake.id, "state": "intake_created"}`.

This looks redundant. Agents will want to “clean it up.” Do not do that blindly.

The inner assignment guarantees linkage at creation boundary. The outer write ties intake linkage to explicit state transition and outer flow completion. Any cleanup here must be tested against audit flow, mail activity behavior, retry actions, and any onchange or write-path assumptions elsewhere.

## Test References

Before changing this file, inspect and run the repo tests that target web lead behavior. The repo uses flat test files under `tests/`, not a `tests/plasticos_web_leads/` subdirectory on Production.

Primary targets:
- `tests/test_web_lead_*.py`
- any related intake or classification tests touched by web lead regressions

Do not invent new fixtures until you have reviewed the existing ones.

## Safe Editing Rules for Agents

1. Read `web_lead.py`, `classification_engine.py`, `ai_normalizer.py`, and `image_analyzer.py` before changing behavior.
2. Check `plasticos.web.lead.config` before hardcoding any threshold or model setting.
3. Preserve partner deferral unless explicitly instructed otherwise.
4. Do not rewire `_find_or_create_partner()` into active flow.
5. Treat the write/unlink guards as high-risk regression zones.
6. Treat `_merge_ai_and_vision()` as a classification hotspot.
7. Run web lead tests before and after changes.
8. If a “cleanup” changes state transitions, classify it as behavioral, not cosmetic.

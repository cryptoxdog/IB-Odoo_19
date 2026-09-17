# CRM Adapter Roadmap — extension contract for future CRM sources

> Status: guidance only (odoo-intent-1 ingestion milestone). **VanillaSoft is the
> only implemented CRM source.** No vendor is selected here, and no stub,
> directory, class or placeholder mapping exists for any future source — adding
> one is an explicit, reviewed change.

## Where the boundary lives

`plasticos_crm_sync` is the single CRM integration module:

| Layer | File | Responsibility |
|---|---|---|
| Adapter protocol + canonical DTOs | `adapters/base.py` | `CrmAdapter` interface; `CanonicalLead` / `CanonicalCall` / `CanonicalTableRow` |
| Provider adapter | `adapters/vanillasoft/` | VanillaSoft-only transport, pagination, retries, source-specific interpretation |
| Registry | `adapters/registry.py` | single fail-closed admission point (`LIVE_PROVIDERS`, unknown provider raises) |
| Shared pipeline | `services/orchestrator.py` | canonical validation, mapping, entity resolution, dedup, upsert/import, reconciliation, observability |
| Identity authority | `models/crm_external_ref.py` | `plasticos.crm.external.ref` unique `(provider, external_id, res_model)` |
| Run audit + classification | `models/crm_sync_run.py` | seen/created/updated/unchanged/duplicate_rejected/failed counters |

The shared pipeline contains **no provider-specific strings, field names or
logic** — everything source-specific stays inside the adapter.

## Adapter contract a new source must satisfy

1. **Authentication / access** — provider credentials are read from
   `ir.config_parameter` (never env files, never logged); HTTPS enforced except
   loopback test endpoints.
2. **Retrieval** — contacts, call history and custom tables through the
   `CrmAdapter` protocol; bounded page sizes; deterministic cursors.
3. **Pagination** — fail closed: refuse inferred cursors; a non-advancing full
   page halts the window instead of looping (mirrors the VanillaSoft I5/I15
   invariants).
4. **Retries / rate limits** — bounded retries with backoff on
   `429/5xx`; auth errors fail immediately; every failure is surfaced, never
   silently clamped.
5. **Source-specific interpretation** — statuses, booleans, dates and
   identity fields are normalized **inside the adapter** into the canonical
   DTOs; strict parsing (unknown value = reported anomaly, never a default).
6. **Source identity** — a stable source-native id on every record, carried as
   `external_id` and persisted through `plasticos.crm.external.ref`.
7. **Incremental markers** — forward-only watermarks with explicit floors; the
   full-import census rule (a `partial` verdict when the historical floor
   cannot be proven) applies to any new source.
8. **Inactive / deleted semantics** — provider deletion semantics map onto the
   provenance-gated archive/reactivate lifecycle (`vanillasoft_sync_archived`
   pattern, provider-scoped).
9. **Malformed records** — never silent loss: every record is classified
   created | updated | unchanged | duplicate_rejected | failed and every
   failure carries a per-record error entry.
10. **Source errors** — typed `CrmAdapterError` with a single durable audit
    row per run and an error excerpt on the connection.

## Onboarding checklist for a new provider

1. Adapter + client under `adapters/<provider>/` implementing the protocol.
2. Registry: add the selection entry and extend `LIVE_PROVIDERS` — one commit,
   reviewed, no stubs before the adapter is complete.
3. Canonical record contract: prove the adapter's DTO output against the
   shared mapping table in this repo's runbook style (every field
   VERIFIED / UNMAPPED_INTENTIONALLY with a reason — no silent discards).
4. Validation: pure-python tier (client + adapter + mapping), Odoo
   TransactionCases (lifecycle + upsert), and a real-runtime gate following
   `tests/runtime_gates/run_f1_f3_full_import.py` (first import, repeat run,
   changed record, failure recovery).
5. Testing requirements: pagination fail-closed, retry/auth boundaries,
   malformed payloads, duplicate source data, partial batch failure,
   unavailable source, and the canonical command's preflight + nonzero exit.

## Out of scope until a vendor is selected

No adapter directories, no connection options, no mapping files, no test
fixtures for unnamed vendors. This document is the only future-CRM artifact.

## Recovered v2 schema set — disposition (non-blocking, recorded)

The ten recovered candidate schemas (canonical-snapshot, evidence-record,
temporal-episode, semantic-document, structural-projection,
opportunity-protocol, transaction-candidate, packet, match-execution-packet,
improvement-packet) exist only as verbatim evidence copies outside any git
repository (the PACK_029 recovery trees), already assessed by the prior
recovery lineage (authority matrix + defect register). Nothing in this
repository depends on them and the import milestone does not. Disposition:
preserved as evidence; the repository's own `contracts/schemas/draft/` tree
(supply-opportunity / buyer-demand per ADR-125, canonical-projection /
sync-projection / outcome-feedback per ADR-128) remains the authoritative
payload-schema home; any later contract-convergence work is a separate,
non-import milestone.

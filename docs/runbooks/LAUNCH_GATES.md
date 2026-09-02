# Launch gates — VanillaSoft → Odoo → Gate → EIE

Architecture of record for launch:

```
VanillaSoft API → Odoo CRM sync → Odoo CRM records
                                    → existing enrichment invocation
                                    → Gate → EIE (Sonar/Perplexity) → Gate
                                    → Odoo allowlisted merge-only writeback
```

Graph is not on the synchronous canonical Odoo enrichment path. Source
synchronization and enrichment stay separate workflows; the hourly CRM cron
remains the only scheduler.

## Locked invariants

| # | Invariant | Where it lives | Automated proof |
|---|-----------|----------------|-----------------|
| I1 | No source watermark acknowledges data that was not interpreted and persisted | `adapters/vanillasoft/adapter.py`, `services/orchestrator.py` | `tests/test_launch_invariants_crm_enrichment.py`, `plasticos_crm_sync/tests/test_watermark_acknowledgement.py` |
| I2 | A failure/audit record survives rollback of the operation it describes | `orchestrator._create_sync_run_durable` / `_persist_sync_failure_durable`, `enrichment_run._persist_operator_state_durable` | structural (AST) only — see **Unverified** |
| I3 | Transaction B never updates a row transaction A still holds | `run_connection`, `enrichment_run._rollback_then_persist_operator_state` | structural (AST) only — see **Unverified** |
| I4 | CRM sync is idempotent by stable external reference | `orchestrator._upsert_lead` / `_upsert_calls` | `test_watermark_acknowledgement.py` replay tests |
| I5 | Session advisory lock excludes concurrent sync across page commits | `run_connection` | structural only — see **Unverified** |
| I6 | Cross-service identity is `entity.id = "res.partner:N"` | `gate_builders.build_converge_request` | `test_launch_invariants_crm_enrichment.py` |
| I7 | Gate is mandatory and fail-closed | `gate_config.classify_gate_availability` | pre-existing `tests/test_gate_single_egress.py` |
| I14 | Writeback is allowlisted and merge-not-overwrite | `enrichment_run._apply_converge_writeback` | pre-existing `tests/test_enrichment_gate_writeback.py` |
| I15 | Optional data may degrade; required data is never silently skipped | `adapter.CUSTOM_TABLES_REQUIRED` | `test_launch_invariants_crm_enrichment.py` |
| I16 | Credential-bearing production endpoints use TLS | `client.require_secure_endpoint`, `gate_config._gate_url_usable` | `test_launch_invariants_crm_enrichment.py` |
| I17 | A row an independently owned transaction references is durable before that transaction opens | `orchestrator._ensure_caller_state_durable` (`run_connection`, `run_full_import`) | `tests/runtime_gates/run_s1_s3_pristine_seams.py` (S1) + `tests/test_pristine_runtime_seams.py` |
| I18 | No write names a model field that the installed registry does not have | `legacy_erp_import_service._partner_mobile_field` | `tests/runtime_gates/run_s1_s3_pristine_seams.py` (S3) + `tests/test_pristine_runtime_seams.py` |

### Pagination fails closed, and that can stop a sync

Both paginators end normally only when end-of-collection is *proven*:

| Source | Safe termination | Anything else |
|---|---|---|
| Contacts | `partial_fulfillment` is false | partial with no API `batch_end`, or a `batch_end` that does not advance → raise |
| Calls | page shorter than the limit | full page with no usable timestamp, or a timestamp that does not advance → raise |

This matters because `_sync_calls` advances the **entire** window watermark once
`iter_calls` returns normally — "ran out of things to yield" and "the window was
fully consumed" are the same signal to the caller. A full page that cannot be
paginated past must therefore raise, never break.

No epsilon is added to a call cursor: calls share timestamps, so nudging it
forward would skip every other call at that instant. A contact continuation
cursor is never inferred from `modified_date_time_utc` — that field is not
documented as a lossless cursor, and this repository has no evidence that it is.

**Operational consequence:** more than one page-limit of calls sharing a single
timestamp, or an API that reports partial fulfilment without a cursor, will halt
that window and hold the watermark. That is the locked trade-off — visible
stoppage over silent permanent omission — and the failure names the cursor and
row count so an operator can widen the window or raise the page limit.

I8–I13 (EIE provider deadline, retry ownership, SDK `max_retries=0`, blocking
provider I/O, zero Graph calls on the canonical path) are **not implemented in
this repository** — EIE and its Perplexity client live in the external
intelligence service. Odoo's side of that contract is already in place: the
Gate caller budget is 30 s (`plasticos.gate.timeout_seconds`, default `"30"`),
`map_converge_response` reads canonical `state`/`fields`, and there is no Graph
or Neo4j call anywhere in `plasticos_gate`, `plasticos_enrichment`, or
`plasticos_matching`.

## Real-runtime deployment gates — executed

These depend on separate PostgreSQL sessions, row locks, real commits and
rollbacks, and advisory-lock lifetime. Odoo's `TransactionCase` runs in test
mode, where `cr.commit()` is neutered and `registry.cursor()` hands back the
same test cursor — a green result there proves nothing. The collected tests in
this repo assert the *ordering contract* over the AST (rollback precedes the
second cursor; no flush in between), which is what silently regresses when a
failure handler is refactored; they are a guard, not the proof.

**These gates have now been run against a real Odoo 19 + PostgreSQL 16.** That
was not ceremony: C2 failed on its first execution and exposed a REPEATABLE
READ defect — the sync-run row is created on a second cursor after the ambient
snapshot is fixed, so every write to it from the first transaction was an
`UPDATE` matching zero rows, silently. No collected test could see it. Re-run
the gates on any change to a failure handler, a commit point, or the advisory
lock, and re-run them before enabling a connection in a new environment.

Gate labels are **stable identifiers**, not an ordering. `C6` previously named
two different things — an HTTPS configuration check here and replay/checkpoint
integrity in the execution brief. They are separate concerns with separate
failure modes, so they now have separate labels: **T1** for transport
configuration, **C6** for replay. Do not reuse a retired label.

### Runtime gates (real Odoo + PostgreSQL)

| Gate | Assertion | Rollback trigger if it fails | Status |
|------|-----------|------------------------------|--------|
| C1 | Healthcheck fails before any sync → sync-run row is visible from an independent DB transaction with `status=failed` | failure records disappear after RPC rollback | **PASS** |
| C2 | Page 1 commits, page 2 fails → page-1 records, watermark **and committed counter** survive; page 2 absent; failure state durable | watermark advances across rejected source data | **PASS** |
| C3 | Failure after the ambient transaction dirtied and flushed the run row → state persists, RPC returns promptly, no row-lock wait | sync/enrichment RPC hangs on failure | **PASS** |
| C4 | Two concurrent `run_connection` calls in separate sessions → the second raises `CrmSyncLockedError` and does no work | concurrent connection runs overlap | **PASS** |
| C5 | Advisory lock still held after a page `commit()` | concurrency exclusion lost mid-run | **PASS** |
| C6 | Replay after a partial failure resumes from the last durable watermark, adds no duplicates, processes the previously failed portion, advances the watermark forward only, and reports only its own committed work | replay loses or duplicates source data | **PASS** |
| C7 | Gate **disabled** → failure/degraded operator state and `availability_status` survive the outer RPC rollback; partner business fields unchanged; no second-cursor lock wait | operator loses the reason enrichment did not run | **PASS** |
| C8 | Gate **transport failure** → same durability assertions, and the call returns inside the configured caller budget | a stalled Gate blocks an RPC worker past its budget | **PASS** |

### Pristine operator-seam gates (real Odoo + PostgreSQL)

Added after three P1 defects reached a pristine database while every collected
test stayed green. Script: `tests/runtime_gates/run_s1_s3_pristine_seams.py`.
Each gate drives the entrypoint an operator actually touches, and each was
observed to FAIL against the unpatched sources before it was accepted.

| Gate | Assertion | Rollback trigger if it fails | Status |
|------|-----------|------------------------------|--------|
| S1 | On a database with no CRM connection, the Settings "Run VanillaSoft sync" button creates the connection and completes a sync: the audit row created on the orchestrator's own cursor resolves its foreign key, and a second press reuses the connection instead of duplicating it | the operator's first sync dies on `plasticos_crm_sync_run_connection_id_fkey` | **PASS** |
| S2 | Over real HTTP through Odoo's dispatcher: an unauthenticated or wrongly-tokened POST is 401, a tokenless-contact POST is 400, and an authenticated POST reaches the orchestrator through a valid elevated `Environment`, returns 200, lands exactly one lead, and lands no second lead on replay | the webhook 500s on every authenticated call | **PASS** |
| S3 | A LegacyErp contact carrying both `PhoneBusiness` and `PhoneMobile` imports against the installed registry: the business phone is preserved, the mobile number is retained rather than dropped or written over the business phone, and no value names a field `res.partner` does not have | the first historical import aborts, or silently discards mobile numbers | **PASS** |

**Why the collected suite could not see any of the three.** S1's settings test
patches `action_sync_now`, so no second cursor is ever opened — and under
`TransactionCase` it could not fail even unpatched, because `registry.cursor()`
returns the test cursor. S2 had no test at all. S3's contract tests parse the
importer with `ast` and never build a registry, and `_upsert` routes an existing
record to `write()`, where `_differs` drops an unknown field silently — so only
a *create*, on a *pristine* database, against a registry without
`res.partner.mobile`, raises.

`tests/test_pristine_runtime_seams.py` is the CI-tier half: it cannot prove the
seams work, but it fails when the specific construction behind each defect
returns. That is the same split already used for I2/I3.

### Full-import gates (real Odoo + PostgreSQL)

Added with the manual `run_full_import` bootstrap. Script:
`tests/runtime_gates/run_f1_f3_full_import.py`. Procedure:
[`CRM_SYNC_FULL_IMPORT_E2E.md`](CRM_SYNC_FULL_IMPORT_E2E.md).

| Gate | Assertion | Rollback trigger if it fails | Status |
|------|-----------|------------------------------|--------|
| F1 | Full import asks for the operator's floor unclamped, lands a contact older than the rolling window and historical calls from the explicit floor, and hands watermarks to `run_connection` — whose immediate replay adds no duplicate lead, ref or call, and never rewinds the watermark | full import duplicates identities, or its replay re-consumes history | **NOT RUN** — needs a live runtime |
| F2 | An unproven contact census is recorded `partial` with the reason durable on the run row and the connection; a proven one is `success`; an unusable floor raises before any run row exists and holds no advisory lock | a full import reports `success` over a silently clamped window | **NOT RUN** |
| F3 | Provider deletion archives with provenance, restore reactivates and clears it, a user's archive is never reopened, and the archived lead is matched rather than duplicated | sync reopens leads an Odoo user archived | **NOT RUN** |

C1–C8 still apply to the full import unchanged: it shares `_sync_contacts`,
`_sync_calls`, `_upsert_lead` and the advisory lock with `run_connection`.

### Transport / configuration gates (no runtime required)

| Gate | Assertion | Rollback trigger if it fails | Status |
|------|-----------|------------------------------|--------|
| T1 | Configured VanillaSoft and Gate endpoints are both `https://` | production service URL is plaintext HTTP | operator check at deploy |

C1–C8 are executable without Docker; see `C1_C6_LOCAL_RUNTIME.md` for the
harness and `tests/runtime_gates/` for the scripts. Any lock
wait, disappearing failure record, or incorrect watermark is NO-GO.

**A fixture caveat that cost a false failure.** `_sync_contacts` clamps
`modified_after` to the source API's 31-day maximum (`now - 30d`). A replay
fixture whose watermarks predate that floor tests the clamp, not the
checkpoint: the adapter is handed the floor and the resume assertion fails for
the wrong reason. Keep C6 watermarks inside the window.

## Canary order

1. Gate A — the five patch areas landed, no architecture expansion.
2. Gate B — CI green (`ruff`, static checks, pure-python tests, audit baseline).
3. Gate C — C1–C8 above on real Odoo/PostgreSQL, plus T1 at deploy.
4. Gate D — EIE bounds (owned by the EIE repo, not this one).
5. Gate E — manual VanillaSoft canary with the cron **off**; run twice and require
   no duplicates, no lost records, no watermark regression. Then enable the cron.
6. Gate F — enrichment with `plasticos.gate.auto_writeback=0`: identity survives as
   `res.partner:N`, partner business fields untouched.
7. Gate G — `auto_writeback=1` against a canary partner: blank allowlisted field may
   populate, populated allowlisted field unchanged, non-allowlisted field never written.

## Rollback triggers

Disable the affected connection or the `plasticos.gate.auto_writeback` flag —
do not redesign under incident pressure. Triggers: watermark advances across
rejected source data · duplicate external refs · overlapping connection runs ·
RPC hangs on failure · EIE exceeds the caller budget · Graph appears on the
canonical Odoo path · existing CRM values overwritten · non-allowlisted fields
written · plaintext production URL · failure records lost after RPC rollback.

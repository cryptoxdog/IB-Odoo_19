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

I8–I13 (EIE provider deadline, retry ownership, SDK `max_retries=0`, blocking
provider I/O, zero Graph calls on the canonical path) are **not implemented in
this repository** — EIE and its Perplexity client live in the external
intelligence service. Odoo's side of that contract is already in place: the
Gate caller budget is 30 s (`plasticos.gate.timeout_seconds`, default `"30"`),
`map_converge_response` reads canonical `state`/`fields`, and there is no Graph
or Neo4j call anywhere in `plasticos_gate`, `plasticos_enrichment`, or
`plasticos_matching`.

## Unverified — real-runtime deployment gates

These depend on separate PostgreSQL sessions, row locks, real commits and
rollbacks, and advisory-lock lifetime. Odoo's `TransactionCase` runs in test
mode, where `cr.commit()` is neutered and `registry.cursor()` hands back the
same test cursor — a green result there would prove nothing. The tests in this
repo assert the *ordering contract* over the AST (rollback precedes the second
cursor; no flush in between), which is what silently regresses when the failure
handler is refactored. **Actual behavior must be exercised against a disposable
real Odoo + PostgreSQL before enabling the connection:**

| Gate | Assertion | Rollback trigger if it fails |
|------|-----------|------------------------------|
| C1 | Healthcheck fails before any sync → sync-run row is visible from an independent DB transaction with `status=failed` | failure records disappear after RPC rollback |
| C2 | Page 1 commits, page 2 fails → page-1 records and watermark survive; page 2 absent; failure state durable | watermark advances across rejected source data |
| C3 | Enrichment fails after the run row was mutated → `retryable`/`degraded`/`failed` persists, RPC returns promptly, no row-lock wait | sync/enrichment RPC hangs on failure |
| C4 | Two concurrent `run_connection` calls in separate sessions → the second raises `CrmSyncLockedError` and does no work | concurrent connection runs overlap |
| C5 | Advisory lock still held after a page `commit()` | concurrency exclusion lost mid-run |
| C6 | Configured VanillaSoft and Gate endpoints are both `https://` | production service URL is plaintext HTTP |

Run C1–C5 with `make test-odoo` against a disposable database, or on an Odoo.sh
dev branch. Any lock wait, disappearing failure record, or incorrect watermark
is NO-GO.

## Canary order

1. Gate A — the five patch areas landed, no architecture expansion.
2. Gate B — CI green (`ruff`, static checks, pure-python tests, audit baseline).
3. Gate C — C1–C5 above on real Odoo/PostgreSQL.
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

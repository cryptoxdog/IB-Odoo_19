# Runbook — End-to-end test: VanillaSoft → Odoo manual full import

Proves that an operator can populate a fresh Odoo database from VanillaSoft with
one command, immediately replay the ordinary incremental sync, and have evidence
that the result is complete for the defined scope, correctly mapped, free of
duplicate contact/call identities, and safe to rerun.

Companion documents — this one is the **procedure**; those are the contracts:

| Document | What it owns |
|---|---|
| [`CRM_SYNC_VANILLASOFT.md`](CRM_SYNC_VANILLASOFT.md) | Operator commands, credentials, the `partial` census verdict |
| [`LAUNCH_GATES.md`](LAUNCH_GATES.md) | Invariants I1–I16 and gates C1–C8 / T1 |
| [`C1_C6_LOCAL_RUNTIME.md`](C1_C6_LOCAL_RUNTIME.md) | Getting a real Odoo + PostgreSQL without Docker |

## Why four tiers and not one

Each tier can prove something the tier below it cannot, and each has been the
one that caught a real defect in this module:

| Tier | Runs where | Proves | Cannot prove |
|---|---|---|---|
| **T0** static + pure-Python | anywhere | algorithm, identity, floors, watermark arithmetic, census classification | that a commit is real |
| **T1** Odoo runtime tests | Docker or local harness | ORM semantics — `active_test`, the archive filter, ACLs, the new column | cross-session durability (`TransactionCase` neuters `cr.commit()`) |
| **T2** real-runtime gates | live Odoo 19 + PostgreSQL 16 | commits, REPEATABLE READ snapshots, unique constraints, advisory-lock lifetime | that VanillaSoft behaves as modelled |
| **T3** live canary | staging + real API key | provider pagination, payload shapes, the census verdict against real data | nothing beyond it — this is the last gate |

T1 green with T2 skipped is the failure mode that already happened once here:
gate C2 passed under `TransactionCase` and failed on first contact with a real
PostgreSQL, exposing a REPEATABLE READ defect that no collected test could see.
**Do not treat T0+T1 as sufficient.**

---

## T0 — static and pure-Python (no runtime, ~30 s)

```bash
cd ~/dev/IB-Odoo_19            # or wherever the clone lives

ruff check . && ruff format --check .
python3 -m pytest tests/ -q
python3 scripts/check_module_wiring.py
python3 ci/check_circular_deps.py
python3 ci/check_orphan_model_refs.py
python3 ci/check_odoo19_xml.py
python3 tools/cron_invariant_check.py
bash scripts/check_odoo_patterns.sh
make audit-baseline
```

Targeted subset while iterating on this change:

```bash
python3 -m pytest \
  tests/test_crm_sync_full_import.py \
  tests/test_crm_sync_vanillasoft_client.py \
  tests/test_launch_invariants_crm_enrichment.py \
  tests/test_committed_sync_metrics.py -q
```

**Expected:** all green. `tests/` is 597 passed / 10 skipped at the time of
writing; the skips are pre-existing and unrelated. `make audit-baseline` must
print `No new … findings vs baseline` for both scanners.

**If `ruff` refuses to run** — `Required version ==0.16.0 does not match` —
that is `pyproject.toml`'s `required-version` gate working as designed. Use the
pinned binary (`make venv`, or `pip install ruff==0.16.0`), do not relax the pin.

### What T0 covers

| Area | File |
|---|---|
| Full-import algorithm, floors, boundary/overlap, replay, watermark handoff, census verdict | `tests/test_crm_sync_full_import.py` |
| Strict provider booleans, custom-row identity | `tests/test_crm_sync_vanillasoft_client.py` |
| I1–I6/I15/I16 + the full import's own I2/I3/I5 envelope ordering (AST) | `tests/test_launch_invariants_crm_enrichment.py` |
| Committed-vs-attempted counters | `tests/test_committed_sync_metrics.py` |

---

## T1 — Odoo runtime tests

Docker:

```bash
docker compose up -d
make test-module m=plasticos_crm_sync
```

No Docker — use the harness in [`C1_C6_LOCAL_RUNTIME.md`](C1_C6_LOCAL_RUNTIME.md),
then:

```bash
/opt/odoo-venv/bin/odoo -d c1c6_test \
  --db_host=/tmp --db_port=5433 --db_user=odoo \
  --addons-path="$ADDONS,$PWD" \
  -u plasticos_crm_sync --test-enable --stop-after-init --log-level=test
```

**Expected:** `0 failed, 0 error(s)`. The module's collected cases are
`test_orchestrator_upsert`, `test_watermark_acknowledgement`,
`test_settings_import_action` and `test_lead_lifecycle`.

**Schema check — do this before anything else in T1.** The provenance column is
new, so a database upgraded from an older build will not have it and every
lifecycle assertion will fail for the wrong reason:

```bash
docker compose exec -T db psql -U odoo odoo_test -c \
  "\d crm_lead" | grep vanillasoft
```

Expect both `vanillasoft_id` and `vanillasoft_sync_archived`. If the second is
missing the module did not upgrade — `make update m=plasticos_crm_sync` and
confirm the manifest version moved (`19.0.1.6.0` or later).

---

## T2 — real-runtime gates (live Odoo 19 + PostgreSQL 16)

`TransactionCase` runs one cursor with `cr.commit()` neutered, so it cannot
prove any of this. Set up per [`C1_C6_LOCAL_RUNTIME.md`](C1_C6_LOCAL_RUNTIME.md),
then run the pre-existing gates and the full-import gate:

```bash
export F1_ADDONS_PATH="/opt/odoo-src/odoo-19.0*/odoo/addons,$PWD"
for f in tests/runtime_gates/run_*.py; do
  /opt/odoo-venv/bin/python "$f" || echo "FAILED: $f"
done
```

Each script prints a PASS/FAIL table and exits non-zero on any failure.
`run_f1_f3_full_import.py` is the one specific to this change; it accepts
`F1_DB`, `F1_PG_HOST`, `F1_PG_PORT`, `F1_PG_USER`, `F1_ADDONS_PATH` and
namespaces its external ids per execution, so it is safely re-runnable.

| Gate | Assertion | Rollback trigger if it fails |
|---|---|---|
| **F1** | Full import asks for the operator's floor unclamped; a contact older than the rolling window lands; historical calls start at the explicit floor; the catch-up pass imports a contact the bootstrap never saw; watermarks hand off to `run_connection`; the immediate replay adds no duplicate lead, external ref or call event, and never rewinds the watermark | duplicate identities, or a replay that re-consumes history |
| **F2** | An unproven census is recorded `partial` with the reason durable on both the run row and the connection; a proven census is `success`; an unusable floor raises before any sync-run row exists and leaves no advisory lock held | a full import reporting `success` over a clamped window |
| **F3** | Provider deletion archives with provenance; restore reactivates and clears the flag; a lead an Odoo user archived is never reopened; the archived lead is matched rather than duplicated | sync reopening leads a user archived |

C1–C8 still apply unchanged and must be re-run: the full import shares
`_sync_contacts`, `_sync_calls`, `_upsert_lead` and the advisory lock with
`run_connection`. **Any lock wait, disappearing failure record, or incorrect
watermark is NO-GO.**

---

## T3 — live VanillaSoft canary

Run against a **scratch or staging database**, never production, with the cron
**off**. This is the only tier that exercises real provider pagination and
payload shapes.

### Setup

1. Settings → PlasticOS CRM Sync: API key, root endpoint, project id (`139705`).
2. CRM → CRM Sync → Connections → **Test Connection**. VerifyKey must succeed.
3. Confirm the cron `PlasticOS CRM Sync (VanillaSoft)` is **inactive**.
4. Snapshot the database — `make backup` — so the run is reversible.

### Run

```bash
docker compose run --rm odoo shell -d <scratch_db>
```

```python
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

connection = env["plasticos.crm.connection"].search([("provider", "=", "vanillasoft")], limit=1)

run = SyncOrchestrator(env).run_full_import(
    connection,
    call_history_floor="2019-01-01T00:00:00Z",
    contact_modified_floor="2019-01-01T00:00:00Z",
)
print(run.status, run.contacts_upserted, run.calls_upserted, run.error_excerpt)
env.cr.commit()

replay = SyncOrchestrator(env).run_connection(connection)
print(replay.status, replay.contacts_upserted, replay.calls_upserted)
env.cr.commit()
```

Start with a **narrow floor** (say 90 days) on the first canary to keep the run
short, then widen once the shape is confirmed. A multi-year `call_history_floor`
issues roughly one request per day of history, because `_sync_calls` slices its
window into 1-day chunks — that is the existing bounded-window behaviour, reused
deliberately, and it makes a full backfill slow rather than wrong.

### Verify — from an independent psql session

Read from a session Odoo does not own; reading through the shell under test can
return uncommitted values.

```bash
docker compose exec -T db psql -U odoo <scratch_db>
```

```sql
-- 1. No duplicate contact identity. Both must return zero rows.
SELECT vanillasoft_id, count(*) FROM crm_lead
 WHERE vanillasoft_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1;

SELECT provider, external_id, res_model, count(*) FROM plasticos_crm_external_ref
 GROUP BY 1,2,3 HAVING count(*) > 1;

-- 2. No duplicate call identity. Zero rows.
SELECT provider, external_id, count(*) FROM plasticos_crm_call_event
 GROUP BY 1,2 HAVING count(*) > 1;

-- 3. Watermarks are forward and usable by the next incremental run.
SELECT name, contact_watermark_utc, call_watermark_utc, last_error
  FROM plasticos_crm_connection;

-- 4. The two runs, newest first. Read status and error_excerpt together.
SELECT id, status, contacts_upserted, calls_upserted, orphans_resolved,
       left(coalesce(error_excerpt,''), 200) AS excerpt
  FROM plasticos_crm_sync_run ORDER BY id DESC LIMIT 5;

-- 5. The replay must not have inflated the population.
SELECT count(*) AS leads, count(DISTINCT vanillasoft_id) AS distinct_ids
  FROM crm_lead WHERE vanillasoft_id IS NOT NULL;

-- 6. Unresolved orphans — calls whose contact never arrived.
SELECT kind, count(*) FROM plasticos_crm_sync_orphan
 WHERE resolved = false GROUP BY 1;

-- 7. Archive provenance. Only sync-caused archives carry the flag.
SELECT active, vanillasoft_sync_archived, count(*)
  FROM crm_lead WHERE vanillasoft_id IS NOT NULL GROUP BY 1,2;

-- 8. Custom-table rows never share a key across contacts.
SELECT provider, table_id, external_row_id, count(DISTINCT contact_external_id)
  FROM plasticos_crm_external_table_row GROUP BY 1,2,3 HAVING count(DISTINCT contact_external_id) > 1;
```

### Acceptance

| # | Check | Pass |
|---|---|---|
| 1 | Duplicate contact identities | 0 rows from both queries in §1 |
| 2 | Duplicate call identities | 0 rows |
| 3 | Both watermarks populated, call watermark within minutes of the run | yes |
| 4 | Full-import run is `success` or `partial` — never `failed` | yes |
| 5 | Replay run is `success` and did **not** grow `leads` | `leads == distinct_ids`, unchanged by the replay |
| 6 | Unresolved orphans | expected to be small and shrinking; a large or growing count means contacts are missing |
| 7 | `vanillasoft_sync_archived = true` only where `active = false` | yes |
| 8 | Custom-row key collisions | 0 rows |
| 9 | Lead count reconciles against VanillaSoft's own project contact count | see below |

### If run 1 reported `partial`

That is the census verdict, not a crash — the run completed and its data is
durable. It means the requested `contact_modified_floor` was older than the
31-day Contacts lookback and **no returned contact was modified before that
horizon**, so nothing proves the provider honoured the floor rather than
silently clamping it. `run.error_excerpt` names the horizon and the oldest
contact seen.

Two readings, and only one query separates them:

* the dataset genuinely holds no contact untouched for 31+ days — the import
  **is** complete;
* the provider clamped the floor — contacts untouched since the horizon are
  **missing**, and re-running the command will not surface them.

Resolve it in VanillaSoft: compare check 5's `distinct_ids` against the project
contact count in the VanillaSoft UI. Equal → complete, proceed. Short → the
list endpoint cannot reach the remainder; escalate to VanillaSoft support for a
bulk export or a documented enumeration endpoint before go-live. **Do not treat
`partial` as a pass on the strength of the run having finished.**

### Then, and only then

Run the canary a second time (Gate E in `LAUNCH_GATES.md`): no duplicates, no
lost records, no watermark regression. Then enable the cron.

---

## Failure triage

| Symptom | Most likely cause | Action |
|---|---|---|
| `CrmFullImportArgumentError` | floor absent, unparseable, or in the future | fix the argument — nothing ran, no state to clean up |
| `CrmSyncLockedError` | another sync holds the connection's advisory lock | wait, or find the other session; do not bypass the lock |
| `VanillaSoft {field}: unsupported boolean …` | the provider sent a spelling the strict parser does not accept | capture the payload, then widen `_VS_TRUE`/`_VS_FALSE` **with that evidence** — never by guessing |
| `partial contact fulfillment without a batch_end` | provider promised more rows than it returned and gave no cursor | fail-closed by design; retry, then escalate to VanillaSoft |
| `Call pagination failed to advance` | more than one page of calls share a single timestamp | raise the page limit or narrow the window; the locked trade-off is visible stoppage over silent omission |
| Run `failed`, watermark unchanged | working as designed | re-run; the replay resumes from the last durable watermark |
| Lifecycle assertions fail in T1 | `vanillasoft_sync_archived` column absent | `make update m=plasticos_crm_sync` |
| `Skipping custom-table row without a stable source id` in the log | provider row has no `data_id` | expected; the row is optional enrichment, and persisting it under an invented key would corrupt another contact |

## Rollback

Set `enabled = False` on the connection, or restore the snapshot taken in T3
setup. Do not redesign under incident pressure.

Triggers: duplicate external refs · watermark advances across rejected source
data · a `success` verdict over a clamped window · overlapping connection runs ·
a lead an Odoo user archived reappearing as active · custom-table rows sharing a
key across contacts.

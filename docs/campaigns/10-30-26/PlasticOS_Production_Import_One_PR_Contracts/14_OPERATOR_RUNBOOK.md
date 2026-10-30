# Operator runbook — first Production import (v1.2)

This runbook is for after the PR merges to `Staging`, is promoted to `Production`, and an operator authorizes the run. Merging the PR authorizes none of it. Each step names its gate. A refusal is a stop, not something to work around.

Nothing below goes into Git: not the permit files, the census, run directories, logs, SQL credentials or reports. Every path is on the execution host.

## 0. Preconditions (operator)

1. The Production database is the admitted empty-business-data target. A reset or a fresh database is a separate operator decision.
2. The Odoo.sh build runs the reviewed commit, and its checkout is clean. `release_sha` must equal `git rev-parse HEAD` of the addon checkout.
3. The current go-live ERP SQL snapshot is restored. It is read-only, reachable only from the Odoo.sh host, and stays unchanged through both ERP phases. `cieTrade_SM` from 2026-10-18 is a rehearsal source, not go-live authority.
4. The VanillaSoft incremental cron (`plasticos_crm_sync.cron_crm_sync_all`) is inactive, and outbound mail is held.
5. Export `ERP_SQL_SERVER`, `ERP_SQL_DATABASE`, `ERP_SQL_USER` and `ERP_SQL_PASSWORD` in the SSH session only.

## 1. Probe the partner phase (writes nothing)

```bash
ERP_TARGET_DB=<db> bash plasticos_partner_import/scripts/odoosh_import_erp.sh probe-partners
```

The `ERP_PRODUCTION_PROBE` line prints the observed identity (`database_name`, `database_uuid`, `odoo_stage`, `release_sha`, `release_clean`), the source fingerprint and a `permit_template`. Stop if `release_clean` is false or `release_sha` is null.

## 2. Permit and run `erp_partners`

Write the permit from the template: `phase` `erp_partners`, a fresh `permit_id`, `expires_at` no more than 24 h ahead, and `approved_by`. Then run:

```bash
ERP_TARGET_DB=<db> ERP_PRODUCTION_PERMIT=<path>/erp_partners.json \
  bash plasticos_partner_import/scripts/odoosh_import_erp.sh partners
```

Gates:

- The `consumed` audit line comes before any stage writes.
- `DATA VERDICT` reports `data_complete`.
- The `-verdict.json` and `-permit.json` sidecars are in `ERP_RUN_DIR`.

If `data_complete` is false, review the exceptions. Phase 2 then needs `accept_phase1_exceptions_digest` set to the witness `exceptions_digest`. A refusal before the `consumed` line leaves the permit unused. Once consumed, a permit never admits a second run, so a retry needs a new permit.

## 3. Probe, permit and run `erp_commercial`

```bash
ERP_TARGET_DB=<db> bash plasticos_partner_import/scripts/odoosh_import_erp.sh probe-commercial
ERP_TARGET_DB=<db> ERP_PRODUCTION_PERMIT=<path>/erp_commercial.json \
  bash plasticos_partner_import/scripts/odoosh_import_erp.sh commercial
```

The run refuses when the partner source changed since phase 1, when the phase 1 witness belongs to another database, or when phase 1 exceptions are unaccepted. Accounting stays `draft_unposted` with `accounting_acceptance: BLOCKED_ARCHITECTURE`, and no payment is created. If the run is interrupted, re-run it in full under a new permit bound to the same fingerprint. The importer is idempotent.

## 4. VanillaSoft historical cohort (`crm_history`)

1. Place the no-PII census on the host. Its columns are `vanillasoft_contact_id,decision`, with 4,876 rows split 763 / 18 / 4,095. Record its digest with `sha256sum census.csv`.
2. Write a permit with `phase` `crm_history` and `source_fingerprint` set to the census digest. The other bindings come from step 1's observed identity.
3. Run bounded sessions on durable storage outside the shell session:

```bash
VANILLASOFT_HISTORY_CENSUS=<path>/census.csv \
VANILLASOFT_HISTORY_CENSUS_SHA256=<digest> \
VANILLASOFT_HISTORY_CHECKPOINT=$HOME/data/plasticos_import/crm_history.jsonl \
VANILLASOFT_HISTORY_MAX_IDS=1000 \
VANILLASOFT_PRODUCTION_PERMIT=<path>/crm_history.json \
odoo-bin shell -d <db> --no-http < plasticos_crm_sync/scripts/import_vanillasoft_shell.py
```

The permit is consumed by the first session. Later sessions resume from the same checkpoint under a new permit.

The runner refuses in these cases:

- no committed `erp_commercial` witness;
- the cron is active, or the sync lock is held;
- the census digest or partition is wrong;
- the YES set is not exactly the packaged crosswalk plus the four omitted duplicates;
- the checkpoint belongs to another census or database.

It stops on:

- a rejected credential (exit 2);
- the consecutive-failure budget (exit 1).

Resume trusts only durable external refs. Held and failed IDs are fetched again.

Read the `HISTORY VERDICT` line:

- `HISTORICAL_SNAPSHOT_COMPLETE` means every ID has an honest disposition with a reason.
- `historical_data_complete` additionally needs no held or failed IDs and no imported IDs with error signals.
- `LIVE_DELTA_COMPLETENESS` stays `NOT_RUN` and `FULL_CURRENT_CONTACT_COVERAGE` stays `UNKNOWN`.

## 5. Current provider delta (separate)

After the snapshot, the provider delta is a separate operator run through the existing incremental path, with an explicit `VANILLASOFT_CALL_FLOOR`. It has its own summary. It does not change the historical verdict.

## 6. Acceptance

Post-import data acceptance is a separate operator review of the verdict, permit and report files. Script exit 0 is not acceptance.

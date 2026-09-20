# Runbook — LegacyErp historical import (`plasticos_transaction`, `make import-legacy-erp`)

## Purpose

Deterministic, replay-safe import of the tracked LegacyErp export
(`data/legacy_erp_sm_export/`, 2026-08-07 golden extract) into Odoo:
counterparties, addresses/locations, contacts, contact roles, transactions and
transaction lines — keyed by the source-native identifiers `CpID`, `AddressID`,
`CT_ID`, `CRA_ID`, `BuySellNo` and `DetailID` via `ir.model.data` markers
(`legacy_erp_*`). Running the same validated input twice creates no duplicates.

> **Naming note:** the vendor this export came from is **banned as an
> identifier in this repository** (`BAN001`, `ci/check_banned_identifier.py`).
> The canonical vocabulary is **LegacyErp**; the vendor name must never appear
> in tracked files, commands, or docs. `make import-legacy-erp` is the
> canonical command (the intent spec's conceptual command name used the vendor
> name — this target is that command under the repository's own vocabulary).

## Field mapping authority

- Machine-readable disposition of **every** source column:
  `plasticos_transaction/legacy_erp/mapping_status.py` (statuses
  `VERIFIED` / `NEEDS_CORRECTION` / `UNMAPPED_INTENTIONALLY` / `UNKNOWN`;
  every intentional drop carries its measured reason).
- Narrative mapping + identity contract: [`docs/legacy_erp_import_mapping.md`](../legacy_erp_import_mapping.md).
- Completeness is CI-enforced: `tests/test_legacy_erp_mapping_status.py` fails
  on any silently discarded column.

## Secrets

None. The import reads only the tracked payload and Odoo seed data.

## Prerequisites

- A nonproduction Odoo database with `plasticos_transaction` installed
  (`make update m=plasticos_transaction` on `ODOO_DB_NAME`).
- A runtime: `docker compose` (Docker Desktop running) or the no-Docker local
  harness (`scripts/setup_local_runtime.sh`, `L9_ODOO_VENV`).
- The tracked payload: `data/legacy_erp_sm_export/bulk/` (git-tracked).

## Run

```bash
make import-legacy-erp                        # full import (applied)
make import-legacy-erp LEGACY_ERP_DRY=1                  # resolve + map, persist nothing
make import-legacy-erp LEGACY_ERP_LIMIT=100              # first 100 transactions (diagnostics)
make import-legacy-erp LEGACY_ERP_PAYLOAD_ROOT=/abs/path # non-default source payload
make import-legacy-erp LEGACY_ERP_REPORT_PATH=/abs/summary.json
```

Default machine summary: `.l9/pr/import-legacy-erp-summary.json`
(shared `import-run-summary` contract; validate with
`python3 scripts/validate_import_summary.py <file>`). The command exits
nonzero on material import errors (`final_status: failed`).

## Verification

1. **Reconciliation** — summary must satisfy
   `records_seen == records_created + records_updated + records_unchanged + records_rejected`
   (zero unexplained loss) and `duplicates == 0`.
2. **Repeat run** — run the same command again; expect
   `records_created == 0`, everything `unchanged`.
3. **Changed record** — edit one `bulk/*.csv` row, re-run; expect exactly that
   record `updated`, nothing duplicated.
4. **Runtime gate** — `make runtime-gate g=run_legacy_erp_import.py` runs the
   live-DB proof with independent `psycopg2` verification (exit 77 = skipped
   when no local runtime).

## Test tiers

| Tier | Command | Proves |
|------|---------|--------|
| T0 pure | `make test` | source layer, mapping vocabularies, mapping-status completeness, summary projection (no Odoo) |
| T1 Odoo | `make test-module m=plasticos_transaction` | import service upsert + marker semantics in real ORM |
| T2 gates | `make runtime-gate g=run_legacy_erp_import.py` | live-DB first import + repeat-run + changed-record + savepoint recovery |
| T3 replay | clean checkout + fresh nonproduction DB, `make import-legacy-erp` only | one-command operation with zero manual preparation |

## Known boundaries

- `transaction_date` is reconstructed from `GPLedger.TradeDt` but **not
  persisted** (`plasticos.transaction` has no such field yet) — mapping doc §8;
  a follow-on change, not an import blocker.
- `PayablesBatch`, `UACashLedger` and `WksDocument` are tracked export
  evidence, deliberately unconsumed (reasons in `mapping_status.py`).

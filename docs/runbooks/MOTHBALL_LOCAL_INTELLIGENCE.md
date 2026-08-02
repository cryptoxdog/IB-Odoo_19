# Runbook — Mothball Local Intelligence (Backup / Uninstall Preflight / Restore)

## Scope

Rehearse **backup → uninstall preflight → restore** for retiring Odoo-local matching
and enrichment authority. Gate-only paths remain the sole intelligence egress.

**Hard locks**

- No dropping business audit records
- No uninstall without verified backup
- No automatic production uninstall
- No deleting legacy source directories in this phase

## 1. Backup (required before any destructive DB work)

```bash
# Example — adapt host/db credentials from your environment; do not commit secrets.
pg_dump "$PGDATABASE" --format=custom --file="backup-plasticos-$(date -u +%Y%m%dT%H%M%SZ).dump"
shasum -a 256 backup-plasticos-*.dump | tee backup.sha256
```

Record the dump SHA as `backup_receipt_digest` (`sha256:…`) in the controller
artifact `ledger/artifacts/wave7/TASK-050-restore-rehearsal.json`.

## 2. Dry-run inventory (safe, default)

```bash
python3 scripts/migrations/mothball_local_intelligence.py dry-run
python3 scripts/migrations/mothball_local_intelligence.py inventory
```

Confirm retained models listed in `docs/migrations/MOTHBALL_DATA_MAP.md`.

## 3. Uninstall preflight (still non-destructive)

```bash
python3 scripts/migrations/mothball_local_intelligence.py uninstall-preflight \
  --backup-receipt-digest sha256:<backup dump digest>
```

Expected: coordinator **blocks automatic uninstall** even with backup + allow flag.
Manual uninstall (if ever authorized later) follows Odoo module uninstall UI/CLI
**after** restore rehearsal succeeds on a non-production clone.

Preflight checks:

- Enrichment crons `active=False`
- Matching depends on `plasticos_gate`
- Enrichment does not depend on `plasticos_inference_engine`
- Retained audit tables untouched

## 4. Restore rehearsal

On a **non-production** clone only:

```bash
pg_restore --clean --if-exists --dbname="$PGDATABASE_CLONE" backup-plasticos-….dump
# Verify retained row counts match pre-migrate markers / inventory snapshot
```

Record restore success/failure in the TASK-050 restore-rehearsal artifact.
Do **not** claim production completion from repository tests alone.

## 5. Rollback

- Git: `git revert` of the M5 merge commit
- DB: restore from the verified dump
- Config: `plasticos.mothball.*.authority` markers may remain; they are observational

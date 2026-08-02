# Runbook: Semantic kernel backfill — one family (TASK-031)

## Scope
- **Family:** `specification` only for this wave slice (`TASK_031_LOCKED_FAMILY`).
- **Blocked automatic:** `supply`, `demand` (report status `blocked`).
- **No** Gate / CEG / EIE calls from the CLI.
- Default posture: `--dry-run` (execute adapter not enabled in this slice).

## Dry-run (required first)
```bash
python3 scripts/semantic_kernel_backfill.py \
  --dry-run \
  --family specification \
  --task-031-lock \
  --batch-size 100 \
  --report-path /tmp/sk-backfill-specification.json \
  --fixture-path path/to/rows.json   # optional offline
```

Report fields: `planned`, `created`, `reused`, `skipped`, `conflicted`, `failed`, `blocked`, `checksum`.

## Reconciliation
1. Re-run the same command; checksum of identity set must be stable when inputs unchanged.
2. Second execute-mode run (when enabled) must `reused` prior identities — no double-create.
3. Use `--after-id` / `--company-id` to resume from checkpoint cursor in the prior report.

## Rollback
1. Disable any new reads of generated specification links in Odoo (feature flag / module setting).
2. Reverse generated links for identities listed in the batch report (`odoo|…|specification|…`).
3. Retain the JSON report + checksum as audit evidence; do not delete business audit rows.
4. Prefer restore from pre-batch DB snapshot if execute mode was used against a live DB.

## Recovery owner
IB-Odoo_19 / PlasticOS semantic kernel maintainers.

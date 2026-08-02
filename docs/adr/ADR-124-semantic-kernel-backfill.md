# ADR-124: Explicit semantic kernel backfill CLI

## Status
Accepted (TASK-026)

## Decision
Backfill/reconciliation is an explicit operator command (`scripts/semantic_kernel_backfill.py`) with `--dry-run`, family scoping, batching, reports, and idempotent migration identities. No install-hook backfill. Supply/demand automatic conversion remains blocked.

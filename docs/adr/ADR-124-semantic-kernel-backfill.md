# ADR-124: Explicit semantic kernel backfill CLI

## Status
Accepted (TASK-026)

## Decision
Backfill/reconciliation is an explicit operator command (`scripts/semantic_kernel_backfill.py`) with `--dry-run`, family scoping, batching, reports, and idempotent migration identities. No install-hook backfill. Supply/demand automatic conversion remains blocked.

## Amendment (TASK-031)
Wave-8 executes **one** semantic family: `specification`.
Supply/demand remain `BLOCKED_AUTOMATIC`. Reports expose distinct `planned` vs `created` counts.
Operator runbook: `docs/runbooks/SEMANTIC_KERNEL_BACKFILL_ONE_FAMILY.md`.
CLI flag `--task-031-lock` refuses non-specification families for this slice.

# Real-runtime launch gates

Executable proofs that need a live Odoo 19 registry and a live PostgreSQL
server. They are **not** pytest modules and are deliberately not collected:
under `TransactionCase` there is one cursor and one snapshot, `cr.commit()` is
neutered, and `registry.cursor()` returns the test cursor — a green result
there would prove nothing about any of these invariants.

Setup (no Docker required): [`docs/runbooks/C1_C6_LOCAL_RUNTIME.md`](../../docs/runbooks/C1_C6_LOCAL_RUNTIME.md).
Gate definitions and status: [`docs/runbooks/LAUNCH_GATES.md`](../../docs/runbooks/LAUNCH_GATES.md).

| Script | Gates |
|---|---|
| `run_c1_c2_c4_c5.py` | C1 durable sync-run visibility · C2 committed page + counter survive a later failure · C4/C5 advisory lock across page commits · success-path regression |
| `run_c3_failure_writer_lock.py` | C3 failure writer cannot self-block (includes a hazard check proving the lock is real) |
| `run_c6_replay_checkpoint.py` | C6 replay resumes from the durable watermark, no duplicates, monotonic watermark, per-run counters |
| `run_c7_c8_enrichment_failures.py` | C7 Gate disabled · C8 Gate transport failure — durability across RPC rollback, partner untouched, caller budget honoured |
| `run_f1_f3_full_import.py` | F1 full import → incremental handoff, no duplicate identities · F2 census verdict and fail-closed floors · F3 delete/restore provenance |

```bash
for f in tests/runtime_gates/run_*.py; do
  /opt/odoo-venv/bin/python "$f" || echo "FAILED: $f"
done
```

Each script exits non-zero if any assertion fails, and prints a PASS/FAIL table.

## Rules these scripts follow

1. **Assert from a session Odoo does not own.** Every check reads through a
   plain `psycopg2` connection with `autocommit=True`. Reading through the env
   under test can return uncommitted values and prove nothing.
2. **Be re-runnable.** `run_c6` namespaces its external ids per execution;
   without that it passes once and then counts the previous run's rows.
3. **Give the assertion teeth.** `run_c3` first proves that an uncommitted,
   flushed write really does block a second cursor (3 s `statement_timeout`),
   so the subsequent "returned in 0.2 s" result means something.

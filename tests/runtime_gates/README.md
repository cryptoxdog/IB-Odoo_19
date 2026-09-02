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
| `run_s1_s3_pristine_seams.py` | S1 first-run Settings sync across the orchestrator's owned cursor · S2 authenticated webhook → elevated `Environment` → orchestrator, over real HTTP · S3 legacy contact import against the installed `res.partner` registry |

```bash
make runtime-gates                                   # all of them
make runtime-gate g=run_s1_s3_pristine_seams.py      # just one
```

`make setup-local-runtime` builds the runtime these need (Odoo 19 +
PostgreSQL 16, no Docker); `make runtime-gates` depends on the check, so it
refuses to run against a half-built one rather than failing obscurely.

A gate that exits **77** is reported SKIPPED, never passed: the environment
cannot satisfy a documented precondition. C7/C8 does this when
`plasticos_enrichment` is absent, which requires the private
`constellation_node_sdk`. Every other gate runs without it, so a real failure
cannot hide behind that skip.

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
4. **Stub only the outside world.** `run_s1_s3` serves VanillaSoft from a
   loopback `http://` stub (`client.require_secure_endpoint` permits plaintext
   for loopback precisely so a test endpoint needs no TLS). The controller, the
   environment, the cursor boundary and the registry stay real — mocking any of
   those is mocking the defect.
5. **Verify a gate fails without its fix.** Every gate in `run_s1_s3` was run
   against the unpatched sources first and observed to fail: `ForeignKeyViolation`
   for S1, HTTP 500 with `'Environment' object has no attribute 'sudo'` in the
   server log for S2, and `ValueError: Invalid field 'mobile' in 'res.partner'`
   for S3. A gate that has never failed has proven nothing.

# S6 evidence: Enterprise install, upgrade and restore proof

Contract `PLASTICOS-EXPORT-C06-S6-ENTERPRISE-INSTALL-UPGRADE-RESTORE` (sha256 `25482a31…`) and amendment C06-RECON F1–F10. The base is `0c142374` (S5B head). The Staging proof source is `08504e12`.

This folder holds no full Odoo logs and no real data. Every seeded row is a synthetic `S6-SYN-*` row. Backups and logs stay in gitignored `.l9/runtime/test-env/`.

| File | Contents |
|---|---|
| `L-MIGRATE.json` | F3 admission from clean Staging; F1/F7 seed; F2/F5/F7 upgrade with every `Running upgrade` line and counter; V13 replay and refusals |
| `F7_UPGRADE_TRANSCRIPT.txt` | The `Running upgrade` and migration-logger lines from the F7 upgrade |
| `L-RESTORE.json` | F9/V14 backup and restore checksums, coherence, and the runtime test on the restored database |
| `L-RUNTIME.json` | Runtime runs: upgraded seeded data, unseeded control, the Staging control for D3/D4, restored data, and the slice-head install-smoke and m=all on the fixture re-admitted from the clean slice head |
| `V13_V19_EVIDENCE.md` | Acceptance criterion 0 |
| `ACCEPTANCE_WITNESS_MATRIX.csv` | All 120 cases: 103 Phase 1 cases with a witness (84 cited) or NOT_RUN (19) plus a blocker; 17 Phase 2 cases out of scope |
| `S6_PRIMARY_RULE_WITNESSES.md` | Acceptance criterion 3: the 18 S6 primary rules |
| `F6_LINDA_SWEEP_CURSOR.md` | F6 measurement and verdict |
| `F10_RELEASE_NOTES.md` | Inherited residuals and release notes |
| `REPIN_RECONCILIATION.md` | Validation obligation 0 and V17 |
| `S6_FINDINGS.md` | Defects the proof found (D1–D4b, a, b, D9) and their dispositions |

The harness changes in S6 are in `scripts/test_env.sh`, with tests appended to `tests/test_test_env_safety.py`:

- F4: admitting a template is refused when the PlasticOS addon tree is dirty. The template records `srchead` and `srcdigest`, and `status` shows them.
- F8: `migrate <db> <from-rev>` moves an owned clone across two source trees.
- F9: `backup <db>` and `restore <db> <target>` use Odoo's own `odoo db dump` and `odoo db load`.

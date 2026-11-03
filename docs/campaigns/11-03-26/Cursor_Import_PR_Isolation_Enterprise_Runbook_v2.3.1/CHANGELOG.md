## v2.3.1 (2026-10-25 UTC): #303 published-evidence alignment

- Exact PR #303 source head updated to `190c497bdea1362cad87e231c713efdcd25240d4`; executable baseline remains `702ebaf77d987dc844e2758bd354b2ecef4f26cd`. GitHub comparison: one commit, **five added documentation files only**. #301 remains `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79`, independently based on `Staging`.
- Added `10_PR303_PUBLISHED_HANDOFF_ACCEPTANCE.md` with pinned links and a complete, source-grounded seven-failure plus one-error inventory, the unexpected ACL PASS, compliance/auto-posting risk and mixed-scope warnings.
- Expanded `BEHAVIOR_CATALOG.csv` with 10 PR303 diagnostics that must remain visible even when their runtime modules are excluded by the no-logistics/no-broad-product-testing authority. They are not permission for a new wide suite.
- Separated **DIAGNOSTIC_COMPLETE** from **PR303_MERGE_READY**; no false green for knowingly unresolved assertions.
- Preserved all original v2.3.0 package members and prior-history sections except narrow revisions, updated the per-file checksum manifest, fixed duplicate scope sentence in `09_SCOPE_AND_LIMITATIONS.md`.
- No code, tests, fixture, or GitHub repository changed. All runtime and Enterprise outcomes remain NOT_RUN/UNKNOWN.
- Predecessor: `Cursor_Import_PR_Isolation_Enterprise_Runbook_v2.3.0.zip` (actual predecessor digest is in MANIFEST.json).

---

# Pack revision and source provenance

## v2.3.0 - hardened diagnostic execution and operator authority

**Predecessor:** `Cursor_Import_PR_Isolation_Enterprise_Runbook_v2.2.0.zip`, SHA-256 `a10d803fb4091a99dbef7504c0f54c12c2af31f5cba75176f473d47fdcd05049` (verified on this container session). The seven predecessor instructional documents were retained and strengthened. This version supersedes earlier Cursor import packs without altering the target repository.

### Material strengthening

- Turned operator approval into an unambiguous **negative-permission contract**: all code/test/docs/fixture/config/PR/environment fixes prohibited; only reversible owned test-clone writes, isolated worktree metadata and off-repo evidence are allowed.
- Added `07_EXACT_PREFLIGHT_AND_RUN_COMMANDS.md` to bind each exact PR head to its detached worktree and existing Docker bind mounts, pre-existing Enterprise checkout, running DB, pinned ready template, stable image ID, specific guarded test receipt, owner and database retirement.
- Made the runner's hidden risks explicit: `scripts/test_env.sh status` may run service/image management; `make test-module` upgrades the **full** custom roster on a clone, not only the targeted addon. Any missing fixture or changed fingerprint is BLOCKED, never repaired.
- Added `BEHAVIOR_CATALOG.csv`, grounded in existing GitHub test names, with per-PR/behavior source and assertion witnesses. Exact method evidence is necessary; missing runtime assertions are NOT_PROVEN. The initial self-review replaced weak placeholder/structural mappings with verified existing methods, and marks uncovered ORM-specific behavior explicitly NOT_PROVEN. No synthetic tests are invented.
- Added `08_EVIDENCE_AND_APPROVAL_PACKET.md` with failure isolation, severity, independent technical versus business-fidelity verdicts, SHA-bound receipts, and the required `PENDING_OPERATOR_APPROVAL` queue.
- Added `09_SCOPE_AND_LIMITATIONS.md`, documenting known deferred source/business-policy concerns and the fundamental fact that PR #303 is **not** an import-only/test-only branch because it contains logistics and other product changes.
- Kept the final whole-system gate **locked** until all PR behaviors pass individually after authorized fixes, an operator-supplied integrated SHA exists, and the operator separately approves any applied test imports/replay. No Cursor-created merge or Community fallback.

### Source inspection and runbook lint (read-only)

- Repository `cryptoxdog/IB-Odoo_19`, base `Staging` `2a3b9cda9b127c284d12f98bf35ab0344a500d10` at review; #301 `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79`, #303 `702ebaf77d987dc844e2758bd354b2ecef4f26cd`. PR heads **must** be re-resolved at execution time. Open PR #304 was also seen, and is excluded as logistics-only. Open PR #304 was also seen, and is excluded as logistics-only. Open PR #304 was also seen, and is excluded as logistics-only.
- Relevant source: `docker-compose.yml`, `scripts/test_env.sh` (template/clone/test behavior), `config/test_env_fixture.conf`, `Makefile`, live PR descriptions/diffs and the named pure/ORM tests. The pack does not certify those PRs or run the tests.
- No fixture readiness, true local Enterprise checkout, SQL Server restore, Odoo runtime or same-database import test could be independently observed in this assistant's environment. They remain UNKNOWN until Cursor presents real receipts.

### Deliberate non-goals

No code changes, test additions, remediation PR, GitHub comment, database provisioning, fixture changes, merging, import replay override, Odoo.sh deployment or logistics test execution.

This pack is **operator-facing guidance**, not an admitted runtime/CI proof. Its ZIP checksum verifies the file package only, not the correctness or execution of future tests.

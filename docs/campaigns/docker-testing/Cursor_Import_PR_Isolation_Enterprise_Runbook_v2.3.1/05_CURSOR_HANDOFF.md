# Operator handoff, v2.4.0

This file replaces the v2.3.1 handoff. Where that handoff said to test raw PR tips and to postpone the combined tree, this file is the instruction.

Test PR #301 and PR #303 as they would operate after merge into current `Staging`, on the existing Enterprise fixture named by `config/test_env_fixture.conf`. Then test those two merges combined. Deliver the findings to `docs/reports/evidence/pr301-pr303-premerge-enterprise-<date>/` so the PRs can be remediated before anyone merges them.

1. Use the admitted Enterprise template only. Do not build a new template, switch to Community, or run `make test-env`. If `scripts/test_env.sh status` leaves the pinned template ready and the fingerprint unchanged, record any Docker image-ID movement and continue. If the template is no longer the admitted ready fixture, stop that lane.
2. Build three detached worktrees with `worktree_add_wired.sh`: M301 (Staging merged with #301), M303 (Staging merged with #303), and BOTH (those two results merged). A conflict is the finding. Do not resolve it. Do not push the local merge commits. Do not move the operator's checkout.
3. Score `BEHAVIOR_CATALOG.csv` IDs only. The old matrix letters are retired; see `02_PR_BEHAVIOR_MATRIX.md`.
4. Run the named pure tests first. Then run the module list in that same file through `make test-module` on a fresh owned clone per invocation. A behavior passes only when its method ran.
5. Write one finding per behavior and one ranked remediation queue. Every proposed code change stays `PENDING_OPERATOR_APPROVAL`. Do not edit the PRs in this run.
6. Keep logistics, claims, offer, and matching feature suites out of the module list. #303 still contains logistics code; say so. Loading it as a dependency is not a logistics result.
7. The published #303 Community report is background. Seven red tests and one setup error do not become Enterprise verdicts until those methods run on M303 or BOTH. Diagnostic notes do not make the PR merge-ready.
8. A green BOTH module run is combined-runtime evidence. It is not a restored-SQL-Server import and not a live VanillaSoft sync. Say that in the report.

Stop after the findings are saved. The operator decides which remediation to authorize.

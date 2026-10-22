# Operator card | Mack only

**One PR:** [#197](https://github.com/cryptoxdog/IB-Odoo_19/pull/197) `mack` -> `Development` (not `Staging`). One patch generator, two Codex defects, native Odoo proof and explicit merge hold.

1. Read `01_LIVE_EVIDENCE.md`. Reobserve PR #197's live head/base, review threads and status using GitHub; confirm the worktree is an exact, clean `mack` checkout. If any differ, STOP and re-audit, not a forced patch.
2. Run `python3 -m unittest discover -s <pack>/tests -v` for the offline generator; these use only synthetic repositories.
3. Run the pack's `scripts/build_repair.py` with `--repo` and an out-of-worktree `--output`. Review patch output. Apply by re-running with `--apply` when within approved scope.
4. The only intended repository edits are:
   - `plasticos_mack_workbench/models/internal_review.py` (validate the literal stored SHA-256, reject whitespace);
   - `plasticos_mack_workbench/tests/test_internal_review.py` (Odoo regression for whitespace/uppercase);
   - `tests/runtime_gates/_runtime_env.py` (the missing shared runtime import for the two existing Mack concurrency scripts, no parallel gate);
   - `plasticos_mack_workbench/__manifest__.py` (module version 19.0.1.1.0 to 19.0.1.1.1).
5. Prove *collection and execution* of both Mack model test classes on an owned disposable DB, then exercise `run_mack_review_concurrency.py` and `run_mack_chat_intent_concurrency.py` in real independent sessions. Include in-app-only notification verification and the no-external-effect contract.
6. Run the branch's observed `make pr-check` strictly as a **local quality test**, not publication. Freeze updated local diff, tests, and evidence. STOP before remote publication until its actual branch-specific authorization/command is resolved. STOP before merge unconditionally.

**Don't do:** merge, push, retarget PR, change `Development`, `Production`, `Staging`, touch unrelated addons, broaden reviewer work into chat execution/matching/CWI, edit the global CI or publication tools as a shortcut, run local module tests on an unlabeled or populated DB, accept `77` or missing-model skips as pass, claim checked-in tests proved concurrent RPC behavior.

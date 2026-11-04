# Cursor implementation contract | Mack PR #197 only

```yaml
repository_access:
  inspect:
    - repository: cryptoxdog/IB-Odoo_19
      refs: ["mack@7dcada49fd301d3b5dafb30405d0242667915fbe", "Development@3318fa646a9f33aed55b9ea8f8596316e30684da"]
      paths: ["plasticos_mack_workbench/**", "tests/runtime_gates/**", "Makefile", "AGENTS.md", "plasticos_intake/**", "plasticos_base/**", ".github/workflows/**"]
    - repository: cryptoxdog/IB-Odoo_19
      refs: ["Staging@3c24976576185c7a59b10ff7a837dd1ed93344ee"]
      paths: ["tests/runtime_gates/_runtime_env.py"]
      purpose: source reference only, no Mack retarget
  mutate:
    - repository: cryptoxdog/IB-Odoo_19
      ref: "mack@7dcada49fd301d3b5dafb30405d0242667915fbe"
      paths:
        - plasticos_mack_workbench/models/internal_review.py
        - plasticos_mack_workbench/tests/test_internal_review.py
        - plasticos_mack_workbench/__manifest__.py
        - tests/runtime_gates/_runtime_env.py
  forbidden: ["other PRs", "other modules", "Makefile", "GitHub workflows", "Staging", "Development", "Production", "push", "merge", "PR retarget", "release", "database outside approved disposable clone"]
  external_write_authority: none
```

## Objective and current findings

Complete only the two Codex review findings still open on PR #197 at the pinned HEAD:

- **M-197-F1, confirmed:** both existing independent-session concurrency scripts and `_mack_runtime.py` import `_runtime_env`, absent on `mack`. Restore the smallest runtime environment binder with the expected `DB`, `PG_HOST`, `PG_PORT`, `PG_USER`, `bind_config` API; fail closed on wrong database, host, repository or missing Odoo source. Do not copy Staging's unrelated F1 logic and do not create new concurrency tests. Existing M1/M2 and I1/I2 remain the authorities for real concurrency proof.
- **M-197-F2, confirmed:** internal review model's SHA-256 constraint uses `.strip()` only for regex comparison, but the untrimmed value is persisted, permitting padded invalid stored digests. Validate the literal persisted value without trimming, add native Odoo negative regressions for padding/uppercase, preserve exact identity on retries.
- **M-197-M1, required by repo policy:** bump `plasticos_mack_workbench` from `19.0.1.1.0` to `19.0.1.1.1` because runtime model behavior changes. Confirm version lineage after inspecting the actual installed module, no invented older upgrade result.

The pack has an exact-blob guarded candidate repair. The executor must inspect the diff and use the native code owner's actual tests before claiming closure. Optional refactors, new fields, new CWI semantics, new PR, other workstreams and broad repo cleanup are forbidden.

## Entry preconditions

- Fetch current PR #197 using the existing authenticated GitHub integration or read-only `gh api repos/cryptoxdog/IB-Odoo_19/pulls/197 --jq '{state: .state, head_sha: .head.sha, base_ref: .base.ref, base_sha: .base.sha}'`. If fields/command unsupported in the installed CLI, use current documented API; no substitution of presumed values.
- Verify exactly `OPEN`, `mack@7dcada4...` -> `Development@3318fa6...`. `git show` and blob hashes must equal the pack. When source has moved or a file was already repaired, STOP this pack and rebind; don't force a patch or declare it obsolete without checking successor code.
- Work in a dedicated clean Mack worktree. Never switch/change the user's unrelated worktree or reset existing local changes.
- Confirm the read-only comparison with `Staging` is for the missing helper API only. No checkout/merge of unrelated Staging code.

## Execution procedure

1. Run pack builder tests:
   `python3 -m unittest discover -s <pack>/tests -v`.
2. Run the bundle's source-bound generator:
   `python3 <pack>/scripts/build_repair.py --repo <absolute-mack-worktree> --output /tmp/mack-197-repair.patch`.
3. Inspect the full patch and `git apply --check` result. Check the edit list is exactly the four allowed paths. No renamed/deleted artifacts.
4. Apply with the generator's explicit `--apply` argument. This is a local repository edit, not commit/push.
5. Verify `python3 -m py_compile` on the two Python runtime files and the test/helper, perform the repository's actual Ruff/configured checks, `make pr-check`, and real Odoo module tests in a **separately verified disposable database**. Run the two multi-cursor gates as detailed in `03_RUNTIME_ACCEPTANCE.md`. A success with skipped models or exit 77 is NOT proof.
6. Review for accidental changes in access controls, email notifications, routing behavior, idempotency, state immutability and retry semantics. F1 and F2 must each have a negative test that would reject the original defect.
7. Record exact changed commit **only if** local commit authority and repository instructions allow; do not call old `make commit` interactively because its implementation offers to invoke `make push`. Commit via the approved local non-publishing mechanism, preserving existing user changes. **STOP BEFORE REMOTE PUBLICATION.** Report a separate publication routing block from the old `Development` Makefile.
8. Preserve the operator's `DO NOT MERGE` hold and the PR's exact-base topology. No inferred merge authorization even if every check passes.

## Invariants to preserve

- `plasticos.mack.internal.review`: server-owned reviewer, requester and route revision; immutable after creation; one review per `(company_id,idempotency_key)`; replay returns exact original receipt without second activity; no CWI execution or external commercial actions.
- `plasticos.mack.chat.intent.receipt`: original native source message and actor are server-resolved, one receipt per company/source message, replay after intake edit, no attachment byte copy and no message/external action emitted by receipt recording.
- Real concurrency proof exercises independent PostgreSQL transactions with the repository's existing gate runners and Odoo retry path. A mock-based test alone cannot close F1.
- The module remains a narrow Odoo-native review/receipt capability, not the Mack orchestrator, matching runtime, approval engine, CRM integration or email service.
- No brand-new architecture layer for a small missing helper; use the verified four-file delta.

## Terminal receipt

Return one table with `F1`, `F2`, `M1`, Odoo native tests, M1/M2, I1/I2, in-app-only delivery, old publisher barrier, review thread status and merge hold. Each row must identify exact tested SHA, command/evidence, outcome `PASS/FAIL/BLOCKED/UNKNOWN` and evidence URI/file. No success by assertion or prose.

> **START-HERE INVARIANTS, v2.3.1:** (1) READ/TEST/REPORT ONLY; no patches, test rewrites, staging, commits, pushes, issue/PR edits, merges, deploys, or automated remediation. (2) No logistics **test scope**; PR #303 nevertheless CONTAINS logistics code and must never be misrepresented as import-only. (3) Exact 40-character head per PR, isolated detached worktree, immutable source digest. (4) Existing pinned **Enterprise** fixture ONLY; do not build/adopt/re-stamp/repair templates or upgrade infrastructure. (5) Every behavior has a named existing test and proof; green modules alone never imply business or ORM fidelity. (6) The combined phase is DISABLED until all individual fixes are explicitly approved, retested, and an **operator-supplied integrated SHA** exists. (7) Any proposed change goes in an approval queue, never into code.

# Cursor: ERP + CRM import verification, operator-controlled

**Version:** 2.3.0 (2026-10-24). **Status:** execution instructions for testing only; not permission to alter code, source contracts, test tooling, or business processes.

## Operator instruction, overriding prior packs

> Test **each relevant pull request independently** at its exact GitHub head, using **only the existing, admitted Odoo 19 Enterprise Docker test fixture**. Test **each claimed behavior** independently in the findings ledger. Return warnings, errors, inconsistencies, and workflow misalignments with reproducible evidence. **Do not fix anything. Every change requires my separate approval.** Exclude logistics.

The operator's requirement supersedes every permissive phrase in v2.0.0, v2.1.0 and v2.2.0. **v2.3.1:** #303 is pinned to the documentation successor head `190c497...`; test execution uses that SHA, while evidence in the published briefs describes the unchanged executable baseline `702ebaf...`. No Community fallback, no fixture creation, no template rebuilding or adoption, no template re-stamping, no self-directed remediation. In particular, **do not run `make test-env`**: it calls the fixture *template* lifecycle and is not an observation-only preflight. `scripts/test_env.sh status` also ensures Docker services and calls a Docker image build; use the non-mutating checks in `01_SOURCE_AND_FIXTURE_ADMISSION.md` first. If existing infrastructure cannot be verified without changing it, record **BLOCKED: OPERATOR APPROVAL REQUIRED**.

## Approved actions versus forbidden actions

| Permitted solely to conduct these tests | Forbidden without new explicit operator approval |
|---|---|
| Inspect GitHub PR metadata, files, diff and test registration; `git fetch` PR refs | Merge/cherry-pick/rebase/stack PRs; change branches in the operator's active checkout |
| Create a new **detached** worktree at each exact PR head; inspect source | Modify any tracked or untracked source, tests, config, manifests, docs, `Dockerfile`, Compose or scripts |
| Read existing fixture identity, image/container state, Enterprise path | Create/adopt/rebuild/re-stamp templates; change PG/image/version/dependencies; install/update packages |
| Run repo's guarded existing tests on **owned fresh disposable clones** | Test Community as a substitute; skip fixture gate; use raw unsafe DB/test commands |
| Record evidence files and a decision queue outside source control | Commit, push, open/update PRs or issues, dispatch fixes to Claude/Cursor, deploy, post/pay/reconcile |
| Drop **only the cloned DB created by this exact run** using `scripts/test_env.sh drop` after preserving receipts | Delete another actor's clone or any existing fixture/business DB; modify live ERP/CRM records |

**Allowed test side effects:** using an already-running authorized local Docker service, Odoo module upgrades/test records **only inside the freshly owned clone**, writing test logs/receipts, and creating temporary Git worktrees. If the service is stopped or absent, or the image would have to be created/replaced, stop for approval. Removing the temporary worktree is not required, and never delete another person's worktree.

## Source topology at compilation, re-resolve before any run

Repository: [`cryptoxdog/IB-Odoo_19`](https://github.com/cryptoxdog/IB-Odoo_19), integration branch `Staging` at `2a3b9cda9b127c284d12f98bf35ab0344a500d10`.

| Lane | GitHub subject | Source at plan time | Role |
|---|---|---|---|
| S | `Staging` | `2a3b9cda...` | Merged ERP/CRM import baseline, independent worktree |
| 301 | [PR #301](https://github.com/cryptoxdog/IB-Odoo_19/pull/301) OPEN | `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79` | Current invoice/date/terms, PO, no-stock changes |
| 303 | [PR #303](https://github.com/cryptoxdog/IB-Odoo_19/pull/303) OPEN | `190c497bdea1362cad87e231c713efdcd25240d4` (docs-only successor to `702ebaf77d987dc844e2758bd354b2ecef4f26cd`) | Separately test import-related test discovery and code effects. Implementation frozen at `702ebaf77d987dc844e2758bd354b2ecef4f26cd`; includes out-of-scope logistics code |
| OUT | PR #302/#304; merged PR #300 | Logistics | NEVER run logistics-specific tests, harvest behavior or remediate |
| OUT | PR #296/#297 | Repo index / publication | Not import subjects, unless a newly observed crosscutting failure makes them materially relevant; report, do not auto-expand |

Merged import predecessors (#277, #284, #291, #294, #295, #298, plus prior material work) live in `Staging` and are tested as lane S. Do not reconstruct their old heads unless the operator explicitly requests historical bisection.

**No Cursor-created integration branch.** #301 and #303 are sibling heads, not one combined PR. Do not claim that testing both separately proves their eventual merge. **A final whole-system cohesion phase is now planned, but it is CONDITIONAL:** only after individually retested operator-approved fixes and an operator-supplied combined SHA/ref may Cursor test a fourth, isolated worktree. Cursor never merges/cherry-picks to create it. See `06_FINAL_COHESION_GATE.md`. PR #303 also contains other product changes; it may be read and run in its own worktree, but this campaign only evaluates CRM/ERP/import-related behavior, not logistics. If a test cannot exclude logistics behavior, mark that specific test OUT_OF_SCOPE, not PASS.

## The measurement strategy

1. Establish the **source and test instrument**: exact PR head, clean tree, Compose bind mount and existing Enterprise fixture. If any mismatch: STOP.
2. Run the **cheapest one-question pure test** for each behavior, followed by the existing **module-granular Odoo runtime test** where its ORM effect matters. The guarded test runner does not support an ad hoc method-level `--test-tags` override. A shared module run is allowed, but **each method/behavior gets a separate result, with execution evidence**.
3. Report both **technical correctness** and **historical business fidelity**. A passing importer of draft bills is not necessarily a faithful historical books mirror. No policy is changed by a test agent.
4. On failure, locate the first broken seam: source -> projection/adapter -> index/crosswalk -> mapper -> Odoo ORM -> summary -> replay. Recommend a decision, **not a patch**.
5. End each independent lane with a **one-page operator approval queue** containing only material actions; all are `PENDING_OPERATOR_APPROVAL`.
6. **LAST, AFTER FIXES ONLY:** execute Phase I from `06_FINAL_COHESION_GATE.md` at the operator-approved integration SHA. Run import-facing addon tests together, and pursue real same-database ERP -> CRM -> replay only with a separate applied-import authorization. A module-level green cannot be described as end-to-end proof.

Execution order: read `05_CURSOR_HANDOFF.md` to activate; use `07_EXACT_PREFLIGHT_AND_RUN_COMMANDS.md` for preflight and controlled commands; `01_SOURCE_AND_FIXTURE_ADMISSION.md` for source and fixture invariants; `BEHAVIOR_CATALOG.csv` with `02_PR_BEHAVIOR_MATRIX.md` to execute and classify each behavior; `03_EXECUTION_SEQUENCE.md` for test sequence; `08_EVIDENCE_AND_APPROVAL_PACKET.md` plus `04_FINDINGS_AND_APPROVAL.md` for evidence and operator decisions; `09_SCOPE_AND_LIMITATIONS.md` for known non-goals. `06_FINAL_COHESION_GATE.md` is locked until operator approval. `CHANGELOG.md` records successor changes.

## New mandatory #303 source-of-truth gate (v2.3.1)

**Before any #303 Docker run**, read the five published reports at the **current exact PR head**, initially `190c497bdea1362cad87e231c713efdcd25240d4`, under [`docs/reports/evidence/pr303-cursor-handoff/`](https://github.com/cryptoxdog/IB-Odoo_19/tree/190c497bdea1362cad87e231c713efdcd25240d4/docs/reports/evidence/pr303-cursor-handoff). Check their pinned Git object identities and verify that the transition from `702ebaf` changed only those five files (GitHub compare: ahead by 1, five additions, no production/test/manifest changes). The handoff distinguishes `OBSERVED (CE runtime)`, `OBSERVED (static)`, `HYPOTHESIS`, and `OPERATOR DECISION`. **Never label a CE observation as Enterprise proof.**

See `10_PR303_PUBLISHED_HANDOFF_ACCEPTANCE.md` for the seven named red assertions, the one accounting setup error, the unresolved ACL PASS, compliance/auto-posting risk, non-import scope, and the two verdicts that prevent a false green. **Diagnostic completion is allowed with the seven known tests red; PR merge readiness is not.**

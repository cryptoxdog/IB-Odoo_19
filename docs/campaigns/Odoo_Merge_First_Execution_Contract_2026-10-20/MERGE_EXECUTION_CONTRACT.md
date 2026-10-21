# Merge Execution Contract | IB-Odoo_19 | 2026-10-20

**Mode:** MERGE-FIRST, VALIDATE-SUFFICIENT, NO-EXTRA-AUDIT  
**Target:** `https://github.com/cryptoxdog/IB-Odoo_19`  
**Authoritative release branch:** `Staging` (not `main`, not `Production`)  
**In scope:** existing open #260, #261, #262, #263, #264, #265, #266 targeting `Staging`; separately #197 targeting `Development`  
**Out of scope:** new product scope, unrelated repositories, `Production` merges/deployments, test-framework hardening, unrelated CI redesign, speculative issues, new replacement PRs  
**Desired terminal:** merge complete. A PR may instead end `MERGE_PENDING`/`BLOCKED` only with an exact reason, while independent PRs continue.

## 1. Locked operator intent

The operator has reprioritized delivery velocity. **Working code and the repository's existing mandatory checks are sufficient.** Do not demand canonical deep-audit convergence, expanded adversarial matrices, new tests purely for perfection, or multiple runtime test ceremonies before routine PR acceptance. Existing green checks are reusable when bound to the live head and still required. Do not weaken branch protection, delete tests to obtain green, suppress real failures, or deliberately merge known broken behavior.

Preserve the established separation: **#263 = publication ceremony and install-smoke evidence; #266 = CI repair; #265 = Enterprise Documents bridge; #261 = Docker fixture; #264 = CRM/ERP approved identity; #262 = CI trigger; #260 = generated repo index.** A scope change must be necessary to correct a live integration defect, not to tidy architecture.

## 2. Bootstrap and control-plane law

1. Start one accountable orchestrating agent. Load the current `skills/l9-pr-remediation/SKILL.md` from `Quantum-L9/Cursor-Governance`; use its available validated helper CLI for fleet planning, board, CI/review ingestion, merge grant and stack-safe execution. Do not invent a second PR governor. Parallelize genuinely independent *read-only checks* where helpful; serialize merges only on actual dependency/conflict edges.
2. Freeze the exact open PR inventory and current heads at start. `PR_BINDINGS.json` is the initial evidence only. Reconcile changed heads incrementally, not by restarting a broad audit.
3. Distinguish `mergeable_state=clean`, required checks, permission for merge, and product behavior. A green check is not Odoo runtime proof; an unrequired optional red check is not automatically a merge blocker.
4. Only trust a merge authorization produced by an actual operator prompt / host receipt or valid GitHub human approval covering that exact head. If absent, report `MERGE_PENDING`; do not forge or self-transcribe authorization.
5. Follow `ops/autonomy/stack_safe_merge.py` and `merge_gate.py` with the confirmed live SHA and computed merge strategy. No `--admin`, force-push, hand-typed `gh pr merge`, hand-typed `--squash` on a stack parent, or auto-merge bypass. Do not convert a `Development` PR to a `Staging` PR without explicit separate authorization.
6. Odoo **publication** for a needed fix is via its verified existing `make pr` ceremony and base `origin/Staging` for `Staging` work. The L9 SSOT Makefile `make pr` is not Odoo's publication owner. For a no-change PR, do not invoke publication at all. Reuse existing branch/update plumbing and never use `--no-verify`.

## 3. Merge dependency map: minimum safe ordering, not a ritual queue

| Lane | PR | Action and merge dependency |
|---|---|---|
| A | #261 | Merge improved Enterprise Docker fixture first. Green head. One last exact-head board/required-check/grant check, no full fixture replay for its own sake. |
| B | #262 | Merge the already-green single-event trigger, keeping its CI-specific work in the CI lane. #266 also contains this behavior, so prevent loss/duplication when reconciling #266. |
| C | #263 | Merge publication parent **before #266**. Compare `#263 HEAD...#266 HEAD`: on the audited snapshot #266 is three commits ahead and differs by only five CI files. This is a stack parent: let stack-safe machinery choose merge strategy; never squash out the parent underneath its live child. A narrowly active install-smoke bridge assertion can finish here if genuinely required before #265. |
| D | #264 | Merge after #261. #264 diverged from an *older* #261 head. Ensure the resulting `scripts/test_env.sh` / fixture rules preserve #261's subsequent safety fixes. Do not permit older CRM branch contents to revert them. CRM approved identity must still fail closed on ambiguous mappings. Existing replay evidence may be reused; **no new full VanillaSoft API fetch or ERP replay unless a proven regression demands it**. |
| E | #265 | Merge after #263 where necessary for install-smoke ownership. **One real Enterprise Odoo 19 installation check** showing `plasticos_documents_native` auto-installed, valid view loading, and a usable document-to-transaction link is sufficient. Existing disposable DB only; no Production data. If Claude's current session cannot run Docker, use an already-governed remote Docker host or Odoo.sh test build. Block only #265 on missing proof; do not freeze independent lanes. |
| F | #266 | Merge after #263 and reconcile #262 and #265 overlap. The diff *beyond #263* is only five CI files at the snapshot, despite a broad Staging diff. Preserve CI-only ownership, do not reintroduce overwritten publication scripts or OdooLS test-import changes. No new CI campaign or duplicate test infrastructure. |
| G | #260 | **Last**, after substantive Staging merges. Let the existing `repo-index` generator refresh its generated indexes against the final tree, then satisfy its GitHub bot/unattributed change approval gate. Do not hand-edit generated files or bypass the approval gate. |
| H | #197 | Independent `Development` lane, not part of Staging's release train. Two review threads were unresolved on the snapshot and its optional auto-merge job had failed. Resolve real concerns, distinguish optional from required checks, then merge into **Development** if authorized and safe; never silently promote Mack to Staging. |

These are **semantic dependency edges**, not permission to merge without the current fleet planner. A PR can advance as soon as its predecessors, required checks, grant, and minimum functionality gate are satisfied. Do not wait for all PRs to be simultaneously green.

## 4. Fast merge acceptance: minimum discriminating gates

**Always** for each actual head at the moment of merge:

- Correct target branch, non-draft/open, safe stack ancestry, current required checks green per live ruleset/branch protection, and no unresolved blocker threads or conflicting mandatory requirements.
- A valid independent human merge grant recognized by the existing merge gate. If an approval policy flags a bot-generated PR, request the authorized approval; no administrative bypass.
- No confirmed data-loss, security, false-success or schema/registry installation defect introduced by the integration. Fix the smallest source failure and validate its actual changed behavior once.
- Only if a merge causes conflicts or modifies load-bearing code, validate the conflict resolution with the smallest focused test or source check. Do not run a new full test suite just for ceremonial confidence; the normal remote GitHub CI runs as required.

**Special minimum smoke:** #265 must actually install under Enterprise Odoo 19 with its `auto_install=True` manifest; validate installed-state and that the Documents view/action loads. For a transaction-linked document, validate the link resolves. A mocked pure-Python test alone cannot replace this. The install-smoke safeguard belongs to #263; preserve custom-only `ODOO_ENTERPRISE_MODULES=none` and **do not** add the bridge to the explicit `-i` roster. The running smoke evidence must be source/DB-bound; no Production access.

**Known accepted CRM partiality:** Historical evidence bound 735 of 763 operator-approved contact identities and failed closed on 28 absent-person cases. The outstanding 28 are a separately tracked ERP people backlog, **not** a reason to refetch all CRM contacts or postpone unrelated merges, provided no wrong or duplicate people are created and all unapproved pairings stay unadmitted.

**Not release blockers by themselves:** previous audit `PARTIAL` convergence, reviewer suggestions already superseded by code, speculative edge cases, additional assertions requested solely for coverage strength, optional linter notices or skipped advisory jobs, OdooLS developer convenience, remaining historical data backlog with fail-closed behavior, or future product features.

## 5. Runtime execution without depending on Cursor

Preferred persistent option if the current Claude Code execution environment lacks `dockerd`: use **one governed Linux Docker host** (an existing Hetzner/VPS Docker host or a dedicated trusted runner) accessed over **SSH / Docker context `ssh://...`**, with an authorized local working tree and private licensed Odoo Enterprise checkout on that host. Execute the repository's existing Docker install/test script **on the host** where both the project and `ODOO_ENTERPRISE_PATH` exist; the CLI context alone does not magically transfer local bind-mount source paths to a remote daemon. Confirm daemon access, authorized paths and read-only Enterprise mount first.

Do not expose an unauthenticated Docker TCP socket, mount `/var/run/docker.sock` into an untrusted shared agent, copy licensed Enterprise source into Git, or introduce a second production-like Compose/DB system. Docker access is powerful enough to control the host: use a trusted host and constrained credentials. If a remote Docker host is unavailable, use a trusted Odoo.sh test build for the single #265 proof. **Setting up a Docker fleet is not a prerequisite for merging the other PRs.**

## 6. Converge and execute

1. Ingest all current PRs through the existing fleet tool once; print current heads, required-check identity, stack edges, `merge_now`, grant state and known blockers. Use the bound source for the merger. Verify `Staging` protection lists these required checks at snapshot: `Ruff Lint & Format`, `Static Analysis`, `Pure Python Tests`, `CI Gate Result`. Re-query ruleset before action.
2. For each immediately eligible PR, perform one current-head `pr_board.py` / thread / grant / stack-safe probe. If eligible, execute the governed merge. Do not reopen a deep audit.
3. After each merge, refresh the inventory and stale-head checks **only for affected PRs**. Check merge effects on #264's fixture files, #265's document bridge, #266's stacked CI diff, and #260's indexes. Repair genuine conflicts in the owning PR and publish once through Odoo `make pr`, not a raw GitHub patchwork ceremony.
4. If a PR is blocked, record its exact blocker and **continue independent merge lanes**. Never pause the entire campaign for extra quality gates that aren't mandated or tied to a confirmed defect.
5. After the Staging batch, verify final `Staging` head and index currency. Handle #197 independently as a `Development` merge with its own current board/grant/review checks. No Production deployment.

## 7. Exact terminal receipt

Return one short table with columns: PR, original head, final head, base, merged (`yes/no`), merge commit if any, required CI state, unresolved threads, and blocker if not merged. Add Staging HEAD, Development HEAD, remaining open PR count, and a one-paragraph declaration of **what actually works versus what has not been runtime-tested**. For every blocked PR, distinguish `MERGE_PENDING` (missing valid human exact-head grant), `BLOCKED_BY_CODE`, `BLOCKED_BY_GITHUB`, and `NOT_RUNTIME_PROVEN` without fabricating passes.

**Success:** all eligible in-scope PRs merged, independent blockers precisely reported, no false claims, no new review/testing empire. The mission is product delivery, not process perfection.

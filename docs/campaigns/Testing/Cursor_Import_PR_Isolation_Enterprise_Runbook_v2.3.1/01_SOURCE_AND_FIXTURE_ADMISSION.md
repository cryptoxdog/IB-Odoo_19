## v2.4.0 execution guard

Read `07_EXACT_PREFLIGHT_AND_RUN_COMMANDS.md` before any Docker command. Bind the worktree, confirm the already-running DB and the existing image, and read the pinned template comment before `scripts/test_env.sh status`. `status` and `clone` both call `ensure_odoo_image`. Continue when the pinned template is still `ready` and its fingerprint is unchanged. Record a Docker image-ID change. Stop if the template is no longer the admitted ready fixture. Do not call `make test-env` or `test_env.sh template`.

Exact caution: Odoo's guarded test runner invokes `-u` over the **entire declared PlasticOS roster** on the disposable clone, even when only one addon's test tags are selected. It does not wholly exclude a logistics dependency from installation. This pack excludes logistics **behavior/testing**, not loading installed dependencies. For #303, which includes a changed `plasticos_logistics` module, clearly disclose its presence in the source and never infer a logistics acceptance verdict. If even incidental loading/upgrading that dependency would violate a new operator restriction, mark the lane `BLOCKED_SCOPE` and ask first.

# 01. Exact PR source + existing Enterprise fixture admission

**Apply this to current `Staging`, to M301, to M303, and to BOTH.** Never check those trees out on the operator's active branch. A local detached merge is how M301 and BOTH are built. Do not push it. All commands run on the operator's machine.

## A. Fetch into isolated detached worktrees

First inspect the real repository, its origin and existing worktrees. If the correct repository or GitHub head cannot be established, stop. Do not stash, reset, switch or clean the user's worktree.

```bash
# In the existing cryptoxdog/IB-Odoo_19 checkout. Do not switch its branch.
git fetch --no-tags origin refs/pull/301/head
PR301_SHA="$(git rev-parse FETCH_HEAD)"
git fetch --no-tags origin refs/pull/303/head
PR303_SHA="$(git rev-parse FETCH_HEAD)"
git fetch --no-tags origin Staging
STAGING_SHA="$(git rev-parse FETCH_HEAD)"

# Clean merges only. A conflict stops that lane; do not edit the result.
M301_TREE="$(git merge-tree --write-tree "$STAGING_SHA" "$PR301_SHA")"
M303_TREE="$(git merge-tree --write-tree "$STAGING_SHA" "$PR303_SHA")"
M301_COMMIT="$(git commit-tree "$M301_TREE" -p "$STAGING_SHA" -p "$PR301_SHA" -m "local-test-only: Staging+301")"
# If M303_TREE equals PR303^{tree}, the PR head is already the merge.
M303_COMMIT="$PR303_SHA"
BOTH_TREE="$(git merge-tree --write-tree "$M301_COMMIT" "$M303_COMMIT")"
BOTH_COMMIT="$(git commit-tree "$BOTH_TREE" -p "$M301_COMMIT" -p "$M303_COMMIT" -m "local-test-only: Staging+301+303")"

WIRE="$HOME/.cursor-governance/ops/scripts/worktree_add_wired.sh"
bash "$WIRE" --detach ../wt-premerge-301 "$M301_COMMIT"
bash "$WIRE" --detach ../wt-premerge-303 "$M303_COMMIT"
bash "$WIRE" --detach ../wt-premerge-both "$BOTH_COMMIT"
```

If a target directory already exists, stop. Do not overwrite it. Re-resolve the GitHub heads immediately before the fetch. A later push to the PR does not change the SHA already tested; record `STALE_HEAD` and start a new run. If a PR has already merged, test that merge commit on `Staging` and say so. The `commit-tree` objects stay local. Do not push them. After `worktree_add_wired.sh`, `git restore` any file the wire step edited, and require `git status --porcelain` to be empty before tests.

For **each** worktree:

```bash
cd ../IB-Odoo_19_verify_pr301   # change target per lane
pwd
git rev-parse --show-toplevel
git rev-parse HEAD
git status --porcelain
git diff --exit-code
git worktree list
```

A nonempty `status --porcelain` or wrong SHA is `BLOCKED: SOURCE_NOT_ATTESTED`. Do not clean or modify the tree. All later commands must execute with CWD equal to that *same worktree*; `docker-compose.yml` mounts `.` into `/mnt/extra-addons`. Worktrees share a Git common directory, which is specifically supported by `scripts/test_env.sh`'s DB-container identity guard.

## B. Verify Docker mount and fixture without mutating the environment

The canonical fixture name is taken **only** from `config/test_env_fixture.conf` (at plan time, `odoo_test_tpl_ee_c9e8a81f52f23680`). The sole acceptable parity is Enterprise. The local, already-existing Enterprise checkout must be passed as an **absolute** `ODOO_ENTERPRISE_PATH`; do not download or create one. Docker Compose maps `/mnt/enterprise` read-only, `/mnt/extra-addons` to the current worktree, and Odoo core to the existing image. These must all be verified, never assumed.

Read-only checks, within each selected worktree:

```bash
# Validate locally installed tooling and the existing daemon; no provisioning.
docker info >/dev/null

# Print only the resolved addon mount, not the Compose config (may include secrets).
docker compose -f docker-compose.yml -p odoo19 config --format json | python3 -c '
import json,os,sys
c=json.load(sys.stdin); s=c["services"]["odoo"]
v=[m.get("source") for m in s.get("volumes",[]) if m.get("target")=="/mnt/extra-addons"]
assert len(v)==1 and os.path.realpath(v[0])==os.path.realpath(os.getcwd()), "WRONG PR SOURCE MOUNT"
print("PR source bind mount verified:", os.path.realpath(v[0]))'

# This must name an already running DB service, not create one.
docker compose -f docker-compose.yml -p odoo19 ps -q db

grep '^TEMPLATE=' config/test_env_fixture.conf
# Confirm the EXISTING Enterprise checkout (set its path per process, not in .env).
test -f "${ODOO_ENTERPRISE_PATH:?must point to existing checkout}/web_enterprise/__manifest__.py"
```

Confirm the DB service is healthy, in this repository's authorized Compose project, on the correct existing volume. Inspect the image/service identity with `docker image inspect`, `docker ps`/`docker inspect` (do not dump unredacted configurations). If the DB is absent, unhealthy, on another daemon/project, or was started by a different unrelated repo, mark BLOCKED and request approval. If any Docker image is absent or must be rebuilt, mark BLOCKED. No Dockerfile edits, image pulls, dependency installs, Compose project renames or upgrades.

**Critical nuance of the repository code:** `scripts/test_env.sh status` invokes `ensure_db_service` and `ensure_odoo_image` before computing fingerprint. It is **not** a side-effect-free read command. Only after confirming an already-running authorized DB and an existing reusable image may Cursor invoke it. The first sign of unexpected provisioning or an altered image ID is a STOP and an environment-drift report, not a reason to repair the image.

Then execute the existing guard's admission check:

```bash
bash scripts/test_env.sh status
```

Require all of the following (record exact outputs and safe digests):

- `parity: ee`; never set `TEST_ENV_PARITY=community`.
- The **exact pinned** `TEMPLATE` is shown as **`(ready)`**, not absent, unproven or incompatible.
- Template's fingerprint and the actual current inputs agree. Enterprise checkout, Odoo image, PostgreSQL major, module roster and configuration are the admitted ones.
- The main `db` and Enterprise mount are the previously verified ones.
- No code or config changes occurred; `git status --porcelain` stays empty.

**Never run:** `make test-env`, `scripts/test_env.sh template`, `make rebuild`, `make install-smoke` by default, `TEST_ENV_ALLOW_NEW_TEMPLATE=...`, `TEST_ENV_SAFETY_HARNESS=1`, `TEST_ENV_PARITY=community`, direct `dropdb` or a new PG/Enterprise template. The normal clone command can otherwise fall back to the template lifecycle on an unready fixture; **do not call clone unless the existing fixture just proved `ready`**. If the script attempts adoption/re-stamping/rebuilding or its inputs changed, stop without proceeding.

## C. Authorized test runner (once B is PASS)

```bash
# A module-level Odoo test run; runner creates a FRESH owned clone first.
make test-module m=plasticos_transaction ODOO_TEST_DB=odoo_test_pr301_tx

# Evidence written by the repo, not by a new harness:
# .l9/runtime/test-env/odoo_test_pr301_tx.test.log
# .l9/runtime/test-env/odoo_test_pr301_tx.test-receipt.json

# When and only when this run owns the clone and its evidence is copied:
bash scripts/test_env.sh drop odoo_test_pr301_tx
```

Choose a unique `odoo_test_...` name per **worktree + relevant module run** (examples in `03_EXECUTION_SEQUENCE.md`). The runner upgrades the installed PlasticOS roster **on that clone** and selects tests for `m=...`; it does not write to the source worktree or canonical template. Its receipt includes test count, scope, SHA, source digest, dirty flag, failures and errors. Test receipt only proves the module invocation; require independently visible evidence of the specific test method for a behavior PASS.

Odoo may install/upgrade existing logistics modules as necessary **dependencies** because the roster includes them. This is not authorization to test or modify logistics. `--test-tags` must remain guarded to the selected non-logistics addon. Any unavoidable failure during module installation must be categorized as `DEPENDENCY_ENVIRONMENT` and not diagnosed as a Linda issue without operator approval.

## D. After-run identity/immutability checks

- Recheck `git rev-parse HEAD` and `git status --porcelain` in the same worktree. Never accept `dirty:true` as a clean code-verification PASS.
- Confirm the fixture name, fingerprint, image ID and admission status are unchanged from preflight. If the test runner unexpectedly changed the fixture or image, STOP and report.
- Copy the test log and receipt into `docs/reports/evidence/pr301-pr303-premerge-enterprise-<date>/` after the run. Preserve exit codes and method names. Redact secrets.
- Retire only the clone for which this test's ownership stamp verifies. If drop fails, report it immediately, do not force-drop.
- No auto worktree deletion, commits, pushes, issue creation, tag changes, deployments, repair branches or autonomous follow-up.

**Admission states:** `READY_ENTERPRISE`, `BLOCKED_FIXTURE`, `BLOCKED_IMAGE_OR_DB`, `BLOCKED_PR_IDENTITY`, `BLOCKED_SOURCE_DIRTY`, `BLOCKED_LOGISTICS_SCOPE`. No Community fallback; missing proof is BLOCKED, never PASS.

## E. Admission of the final combined revision (future Phase I only)

Only **after** each in-scope PR's final approved code passes its independent behavior tests, accept an operator-supplied 40-hex integration SHA/ref. An authorized external workflow may have merged the PRs into `Staging` or published an explicitly approved import-only integration candidate. Cursor is not permitted to create, cherry-pick, merge or repair that revision. See `06_FINAL_COHESION_GATE.md` for proof that all accepted fixes are present and unapproved logistics changes are not introduced as test scope.

Create a **fourth detached worktree** for this *existing* ref, repeating sections A-D without deleting/reusing the original worktrees, source receipts or clones. Do not silently choose the latest `Staging`, assume a PR's ancestry across squash merges, or replace one approved revision with another. The same canonical Enterprise fixture and unchanged config/PG/image identity are mandatory. Stop if a new integrated head alters the fixture inputs or would trigger a template lifecycle.

A valid integrated worktree proves only its own exact SHA. Run combined methods in one guarded scoped module invocation as specified in document 06; that does **not** authorize applied restored-SQL-Server or live-VanillaSoft imports. Those require an additional operator decision.

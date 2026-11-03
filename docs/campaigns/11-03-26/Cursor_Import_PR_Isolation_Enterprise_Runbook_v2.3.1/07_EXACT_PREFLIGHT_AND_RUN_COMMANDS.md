# 07. Exact, safe Cursor preflight and execution commands

**Purpose:** Prevent the two worst false positives: (i) testing `Staging` when the PR head was intended, and (ii) a green module result from the wrong/modified fixture or a module that never executed the targeted method. This document is executable guidance, not approval to change source or infrastructure.

## Gate A: identify immutable subject, protect operator work

In the existing `cryptoxdog/IB-Odoo_19` repository, *without changing the active checkout*, inspect origin and open PRs:

```bash
pwd
git rev-parse --show-toplevel
git remote get-url origin
git worktree list --porcelain
gh api repos/cryptoxdog/IB-Odoo_19/pulls/301 --jq '{state: .state, base: .base.ref, head: .head.sha}'
gh api repos/cryptoxdog/IB-Odoo_19/pulls/303 --jq '{state: .state, base: .base.ref, head: .head.sha}'
```

Verify the origin really is `cryptoxdog/IB-Odoo_19` and the PR is relevant and still open. If `gh` is not available/authenticated, **record PR state as unverified and stop that PR lane**. Do not improvise an alternative repository or use a guessed SHA. Do not stash/reset/clean/switch the active worktree.

Fetch each PR **sequentially**, verify the exact head reported by GitHub, and add a separate detached worktree in a previously absent directory. Illustrative #301:

```bash
git fetch --no-tags origin refs/pull/301/head
PR_SHA="$(git rev-parse FETCH_HEAD)"
REMOTE_SHA="$(gh api repos/cryptoxdog/IB-Odoo_19/pulls/301 --jq .head.sha)"
test "$PR_SHA" = "$REMOTE_SHA" || { echo 'STOP: PR head changed'; exit 2; }
test ! -e ../IB-Odoo_19_verify_pr301 || { echo 'STOP: worktree path exists'; exit 2; }
git worktree add --detach ../IB-Odoo_19_verify_pr301 "$PR_SHA"
cd ../IB-Odoo_19_verify_pr301
test "$(git rev-parse HEAD)" = "$PR_SHA" || exit 2
test -z "$(git status --porcelain)" || { echo 'STOP: dirty worktree'; exit 2; }
```

Do **not** execute this file wholesale as a script; commands are examples for deliberate sequential use. Repeat separately for #303 and for the `Staging` baseline using `git fetch origin Staging` and verifying the branch's SHA from GitHub. **Never combine #301 and #303**, even temporarily. Recheck each PR head after its run; if advanced, keep the receipt attached to the tested SHA, mark it STALE_HEAD, and request a fresh authorized run rather than silently retesting.

## Gate B: static bind-mount and existing Enterprise verification (no provisioning)

Execute in **each selected worktree**. The Enterprise checkout path must already exist. If `.env` sets a different path, resolve the conflict *without editing `.env`* or stop. Never print raw `.env` or Docker Compose configuration; those may include secrets.

```bash
# Requires the existing Odoo Enterprise checkout; only inspect, do not create it.
test -n "${ODOO_ENTERPRISE_PATH:-}" || { echo 'BLOCKED: Enterprise path unset'; exit 2; }
# The path must be ABSOLUTE and exported so Compose and Python inspect the same source.
case "$ODOO_ENTERPRISE_PATH" in /*) ;; *) echo 'BLOCKED: Enterprise path must be absolute'; exit 2;; esac
export ODOO_ENTERPRISE_PATH
test -f "$ODOO_ENTERPRISE_PATH/web_enterprise/__manifest__.py" || exit 2
# Do not change the Compose project or .env to force compatibility.
docker info >/dev/null || exit 2
docker compose -f docker-compose.yml -p odoo19 config --format json | python3 -c '
import json,os,sys
s=json.load(sys.stdin)["services"]["odoo"]
v=s.get("volumes",[])
for target, expected in (("/mnt/extra-addons",os.getcwd()), ("/mnt/enterprise",os.environ["ODOO_ENTERPRISE_PATH"])):
    hits=[x for x in v if x.get("target")==target]
    assert len(hits)==1 and hits[0].get("type")=="bind", f"MISSING_BIND:{target}"
    assert os.path.realpath(hits[0]["source"])==os.path.realpath(expected), f"WRONG_BIND:{target}"
print("VERIFIED: exact PR worktree and Enterprise addon binds")'
```

Read `config/test_env_fixture.conf` and require the exact pinned fixture, at compilation `odoo_test_tpl_ee_c9e8a81f52f23680`. **Never hardcode a replacement name**. Read-only DB inspection, using the existing running Compose DB service:

```bash
DB_CID="$(docker compose -f docker-compose.yml -p odoo19 ps -q db)"
test -n "$DB_CID" || { echo 'BLOCKED: DB service not already running'; exit 2; }
test "$(docker inspect --format '{{.State.Status}}' "$DB_CID")" = running || { echo 'BLOCKED: DB container is not running'; exit 2; }
test "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$DB_CID")" = healthy || { echo 'BLOCKED: DB container is not healthy'; exit 2; }
docker inspect "$DB_CID" | python3 -c '
import json,sys
x=json.load(sys.stdin)[0]; labels=x["Config"].get("Labels") or {}
assert labels.get("com.docker.compose.project")=="odoo19", "WRONG_COMPOSE_PROJECT"
assert labels.get("com.docker.compose.service")=="db", "WRONG_COMPOSE_SERVICE"
vol={m.get("Name") for m in x.get("Mounts",[]) if m.get("Destination")=="/var/lib/postgresql/data"}
assert vol=={"odoo19_odoo_pgdata"}, f"WRONG_DATABASE_VOLUME:{vol}"
print("VERIFIED: existing DB container and data volume")'
TEMPLATE="$(sed -n 's/^TEMPLATE=//p' config/test_env_fixture.conf)"
test -n "$TEMPLATE" || { echo 'BLOCKED: pinned template missing'; exit 2; }
TEMPLATE_COMMENT_BEFORE="$(docker exec "$DB_CID" psql -X -U "${POSTGRES_USER:-odoo}" -d postgres -qtA -v ON_ERROR_STOP=1 -c "SELECT coalesce(shobj_description(oid,'pg_database'),'') FROM pg_database WHERE datname='$TEMPLATE';")"
printf 'template comment: %s\n' "$TEMPLATE_COMMENT_BEFORE"
for field in 'plasticos-test-env/2' 'role=template' 'state=ready' 'parity=ee' 'fp='; do
  case "$TEMPLATE_COMMENT_BEFORE" in *"$field"*) ;; *) echo "BLOCKED: missing $field in fixture comment"; exit 2;; esac
done
```

The DB container must be RUNNING and healthy and belong to `odoo19` `db` with the expected `odoo19_odoo_pgdata` volume and same Git repository common directory. Require a **pre-existing** PostgreSQL comment beginning with `plasticos-test-env/2` and including `role=template state=ready parity=ee fp=...`. Never grant `TEST_ENV_ALLOW_NEW_TEMPLATE`, `TEST_ENV_SAFETY_HARNESS`, Community parity, alternate fixture, or a different Docker daemon/project. Any missing or mismatching information is BLOCKED and escalated.

## Gate C: strict fixture fingerprint, image stability and absence of template mutation

The repository's `scripts/test_env.sh status` is **NOT** intrinsically read-only: it starts/checks the DB service and executes `docker compose build --quiet odoo` before computing its fingerprint. **Invoke it only after Gate B passed and a reusable `odoo19-odoo` image already exists.** If an image does not exist, or if any `.env`/runtime override could change the effective paths or fixture, STOP. Snapshot its image ID and pinned template comment before invoking status.

```bash
IMAGE_BEFORE="$(docker image inspect --format '{{.Id}}' odoo19-odoo)" || exit 2
# After the static tests above, the guarded fingerprint read may run.
bash scripts/test_env.sh status
IMAGE_AFTER="$(docker image inspect --format '{{.Id}}' odoo19-odoo)" || exit 2
test "$IMAGE_BEFORE" = "$IMAGE_AFTER" || { echo 'STOP: Docker image changed'; exit 2; }
TEMPLATE_COMMENT_AFTER="$(docker exec "$DB_CID" psql -X -U "${POSTGRES_USER:-odoo}" -d postgres -qtA -v ON_ERROR_STOP=1 -c "SELECT coalesce(shobj_description(oid,'pg_database'),'') FROM pg_database WHERE datname='$TEMPLATE';")"
test "$TEMPLATE_COMMENT_BEFORE" = "$TEMPLATE_COMMENT_AFTER" || { echo 'STOP: Enterprise fixture comment was modified'; exit 2; }
```

Require `parity: ee`, the exact pinned template **ready** for the current inputs, an identical configured module roster and Enterprise path, and no template comment change. If status claims absent/stale/unproven, never invoke `clone`, `make test-env`, `test_env.sh template`, `install-smoke`, or any alternative image/template command. The guarded runner's `clone` can enter `build_template` on stale inputs, including a metadata re-stamp; the ready-proof is a mandatory guard, not a convenience. A no-op image build by the existing script is the only tolerable build invocation. If this cannot be guaranteed, request operator approval for a different test execution path rather than patching scripts.

## Gate D0: pure tests, one catalog assertion at a time

From a clean verified worktree, select the exact existing node in `BEHAVIOR_CATALOG.csv`. Example ERP contact identity on the `Staging` baseline (node is a GitHub-verified test on that revision):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  'tests/test_erp_import_contract.py::test_mixed_alias_group_imports_only_the_active_ct_id'
```

Record the exit status and selected test IDs. A pytest return code 5 means **NO_TEST_COLLECTED**, never PASS. This assertion proves the source-level contract **only**, not ORM persistence or historical source reality. Run each meaningful pure node separately, as needed to diagnose the first wrong layer. Do not edit tests or monkeypatch the application to make them pass. Avoid `--cache-clear` and other destructive cleanup flags.

## Gate D: single scoped module test, unique owned clone and execution evidence

No source changes, no test modifications. Example **PR #301** module test (replace DB suffix for every run; confirm name is absent first):

```bash
# Read-only absence check, before any script that can clone/replace an owned DB.
DB="odoo_test_pr301_tx_$(date -u +%m%d%H%M%S)"
EXISTING="$(docker exec "$DB_CID" psql -X -U "${POSTGRES_USER:-odoo}" -d postgres -qtA -v ON_ERROR_STOP=1 -c "SELECT datname FROM pg_database WHERE datname='$DB';")"
test -z "$EXISTING" || { echo 'STOP: database already exists'; exit 2; }
make test-module m=plasticos_transaction ODOO_TEST_DB="$DB"
```

Do not overwrite a prior clone. If a command fails, preserve its actual exit code and logs (some guarded receipts may be absent after early refusal). Copy existing `.l9/runtime/test-env/${DB}.test.log` and `.test-receipt.json` **outside the Git worktree**, maintaining exact file bytes. Then verify the receipt's `head`, `dirty:false`, `source` digest, `template`, `fingerprint`, `scope`, `tests>0`, `failed`, `errors`, `exit`, and the pre/post-image/template identity. A source digest matching the host code plus the resolved Compose bind is required. Explicit test-method logs must show the claimed assertion actually ran. An aggregate Odoo summary without method-level evidence is only `MODULE_PASS / BEHAVIOR_NOT_PROVEN`.

Illustrative immutable evidence copy (outside the checkout; use your previously authorized output directory, never a repo path):

```bash
EVIDENCE_ROOT="$(dirname "$(git rev-parse --show-toplevel)")/cursor_import_evidence"
mkdir -p "$EVIDENCE_ROOT/pr301/$PR_SHA/$DB"
for ext in test.log test-receipt.json; do
  src=".l9/runtime/test-env/${DB}.${ext}"
  if [ -f "$src" ]; then cp "$src" "$EVIDENCE_ROOT/pr301/$PR_SHA/$DB/"; fi
done
# Hash the COPIES and preserve the original result/exit information.
shasum -a 256 "$EVIDENCE_ROOT/pr301/$PR_SHA/$DB/"* 2>/dev/null || true
```

Only after verifying `bash scripts/test_env.sh assert-clone "$DB"` and preserving evidence, retire that exact owned clone through `bash scripts/test_env.sh drop "$DB"`. Record clone retirement; never drop the template, shared DB or another worker's clone. If retired clone ownership cannot be proven or drop fails, STOP and report. Do not attempt manual SQL/filestore cleanup.

## Gate E: immutable after-action attestation

- `git rev-parse HEAD` is unchanged; `git status --porcelain` is clean. If the runner wrote unignored evidence under `.l9/`, mark this as a **workspace side-effect**, preserve it for the operator, and do **not** delete/reset it yourself.
- The pinned template's PostgreSQL comment, Enterprise source revision, Odoo image ID and PostgreSQL major match preflight, with no re-stamp, upgrade or replacement.
- Source and test receipts match this PR's exact head and mounted worktree; no other PR or `Staging` receipt is accepted by substitution.
- Report `PASS / FAIL / BLOCKED / NOT_PROVEN / DECISION_REQUIRED` **per behavior**, and `PENDING_OPERATOR_APPROVAL` for any suggested change.
- Running `python3 -m pytest` may create local `.pytest_cache` files; use the repository's configured ignore rules and never change tracked source or create a new test. If evidence would dirty the source checkout, report it rather than `git clean`.

**Stop:** one objective run for each authorized PR and behavior; report. Cursor is not authorized to correct code, fixture, test registration or environment and rerun on its own.

## v2.3.1 PR #303 exact-source dual binding

The live PR head to test is `190c497bdea1362cad87e231c713efdcd25240d4` (verify GitHub again). Its **implementation evidence baseline** is `702ebaf77d987dc844e2758bd354b2ecef4f26cd`. The one intervening documentation commit has five additions **only** in `docs/reports/evidence/pr303-cursor-handoff/`. Do not checkout `702ebaf` for the current head test. Read the five new docs before using the repo's controlled Enterprise test runner. The additional published Markdown must not be mistaken for a change in Odoo ORM behavior.

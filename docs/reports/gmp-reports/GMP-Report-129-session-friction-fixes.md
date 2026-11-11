# GMP-129 — session friction fixes

**Task:** `/l9-plan-build` of the three highest-value fixes from the agent session-friction analysis: a runtime lane that does not depend on the agent's own container, the `AGENTS.md` conflict marker (operator chose marker removal only, no body rewrite), and automatic README `module_version` sync.
**Plan:** `.cursor/plans/session_friction_fixes_5f1c2a90.plan.md` (local; section receipt PASS, kernel receipt PASS)
**Branch:** `claude/ib-odoo-session-friction-analysis-xw4cjv`
**Base:** `Staging` `a1f93f3f`
**Tier:** RUNTIME. Developer tooling and documentation only. No addon code, no Docker file, no CI workflow.

## Operator decisions (2026-11-10)

| Question | Answer |
|---|---|
| Where the Enterprise runtime runs | A private repository copy of the Enterprise source, reached by cloud sessions. Not a self-hosted runner, not a GitHub secret. |
| `AGENTS.md` | Remove the conflict marker only. The body rewrite is not in this change. |
| PR shape | One PR on the designated branch. |

This cloud session has a Docker daemon (29.9.2) and reaches Docker Hub. The only missing input for the Enterprise runtime is the Enterprise source itself.

## Todos

| Todo | Result | Commit |
|---|---|---|
| T1 `scripts/runtime_bootstrap.sh` | Resolves Enterprise from `ODOO_ENTERPRISE_PATH`, `./odoo-enterprise`, a sibling `../odoo-enterprise` (linked), or a shallow clone of `ODOO_ENTERPRISE_REPO` at `ODOO_ENTERPRISE_REF` (default: the repository's default branch, such as `main`; the Odoo series is checked as 19.0 separately). Refuses a foreign path, a wrong series, or an unreachable Docker daemon. Reads `scripts/test_env.sh status`: ready is reused, absent runs `scripts/test_env.sh rebuild`, not admitted stops and names `make test-env-rebuild`. Never sets `TEST_ENV_ALLOW_NEW_TEMPLATE`. Runs no tests. | `d9c61511` |
| T2 `Makefile`, `docs/LOCAL_DEV_SETUP.md` | `make runtime-bootstrap` (additive). "Cloud agent sessions" section with the operator's one-time private-repository push. | `af202b19` |
| T3 `tests/test_runtime_bootstrap.py` | 14 tests running the real script in a throwaway repository with stub `docker` and `test_env.sh`. | `d9c61511` |
| T4 `AGENTS.md`, `.pre-commit-config.yaml` | Line 788 `=======` replaced by a blank line. `check-merge-conflict` gains `--assume-in-merge`. | `88743813` |
| T5 `scripts/sync_readme_module_version.py`, `.pre-commit-config.yaml` | Commit-stage hook `readme-module-version` on `^plasticos_[^/]+/__manifest__\.py$`. | `03cfd081` |
| T6 `tests/test_readme_module_version_sync.py` | 11 tests, including one that checks every tracked README matches its manifest today. | `03cfd081` |
| T7 `AGENTS.md`, this report | One dated, additive correction. | this commit |

## Validation

| Check | Command | Result |
|---|---|---|
| Baseline before edits | `pytest tests/test_module_readme_batch_pipeline.py tests/test_runtime_test_ownership.py tests/test_module_readme_index.py` | 180 passed |
| V1 | `pytest tests/test_runtime_bootstrap.py` | 14 passed |
| V1 live | `make runtime-bootstrap` in this session | exit 2: "no Odoo Enterprise checkout", with the three options and the setup pointer. Nothing linked or created. |
| V2 | `pre-commit run check-merge-conflict --all-files` | Passed. The same hook flags a scratch file holding `=======`. |
| V3 | `pytest tests/test_readme_module_version_sync.py` | 11 passed |
| V3 live | Bumped `plasticos_transaction/__manifest__.py`, ran the hook, restored both files | README rewritten to the bumped version; "files were modified by this hook" |
| V4 | `pytest` on the README, runtime-ownership, publication, pre-push and real-push suites plus V1 and V3 | 330 passed |
| V5 | `pre-commit run --files` on every changed file | Passed (ruff-format reformatted two new files on the first pass; second pass clean) |
| Root files | `validate_root_file_protection.py --base origin/Staging --head HEAD` | OK: `AGENTS.md` +1 −1 justified by `ALLOW-ROOT-DELETION`; `Makefile` and `.pre-commit-config.yaml` additive |
| Shell | `bash -n`, `shellcheck scripts/runtime_bootstrap.sh` | Pass |

## Not established by this GMP

- **An Enterprise fixture admission in a cloud session.** No Enterprise source is reachable here. The bootstrap is proven with stubs and by its live refusal only. The first real run needs the operator's private repository (U1 in the plan).
- **Docker bind mounts from this sandbox.** Whether this session's Docker daemon mounts host paths for `docker compose` was not exercised.
- No Odoo runtime test ran. No addon file changed.

## Deviations

- **GMP finalize was applied by hand.** `workflows/gmp_executor.py --mode finalize` writes a root `reports/gmp/` report, which this repository forbids (`AGENTS.md`, 2026-10-21), and then publishes on its own. `--mode start` ran (scope lock, L4 begin). Publication goes through `make pr`. Same handling as GMP-358.
- **Report name.** The plan named `GMP-Report-442-…`; the executor assigned `GMP-129`, so the report follows the executor id, like the other `GMP-129` reports here.
- **Plan renderer defect (Cursor-Governance).** `render_plan_pe_autonomy.py` writes todo text into double-quoted YAML without escaping backslashes, so a regex in a todo made the frontmatter unparseable. The plan text was rewritten without backslashes. A plan title containing `: ` also failed the frontmatter parse.
- **Series check.** Odoo Enterprise manifests may carry a series-relative version (`1.0`). The bootstrap checks a series-qualified version, else the checked-out branch, else notes that the fixture install refuses incompatible modules.

## Operator actions

1. Create a private GitHub repository for the Enterprise source (name `odoo-enterprise` for automatic discovery) and push the existing 19.0 checkout as branch `19.0` (`docs/LOCAL_DEV_SETUP.md`, "Cloud agent sessions").
2. Make it reachable from cloud sessions: add it to the cloud environment's repositories, or set `ODOO_ENTERPRISE_REPO`.
3. In the next cloud session, run `make runtime-bootstrap` and record the first fixture admission. Then publish with `PR_SMOKE=1 make pr`: since Staging #444, a cloud session skips the install-smoke unless `PR_SMOKE=1` is set.

## Follow-up (2026-11-11): first cloud admission

The operator pushed the Enterprise 19.0 source to the private `Quantum-L9/odoo-enterprise` (`main`, 757 modules) and attached it to the session as the sibling `../odoo-enterprise`.

| Step | Result |
|---|---|
| First `make runtime-bootstrap` | The project image build failed: `pip` could not clone `Gate_SDK` ("server certificate verification failed"). Build containers do not trust the session HTTPS proxy CA. |
| Fix | `scripts/runtime_bootstrap.sh` gains `trust_proxy_ca`: when `/root/.ccr/ca-bundle.crt` (or `RUNTIME_BOOTSTRAP_PROXY_CA`) exists, it rebuilds the `Dockerfile` base image (`odoo:19`) locally with the CA trusted, under the same tag, labelled with the CA digest. A matching label is reused. No CA file: no change. `Dockerfile` and `docker-compose.yml` are untouched. |
| `tests/test_runtime_bootstrap.py` | 5 new tests (no CA, rebuild, reuse, failed rebuild, unreadable `FROM`); every test pins `RUNTIME_BOOTSTRAP_PROXY_CA` so a real cloud CA file never leaks in. 47 passed with `tests/test_runtime_test_ownership.py`. |
| Live, base reset to the registry `odoo:19` | The script rebuilt the base. The fixture from the earlier hand-made shim then read "not admitted", correctly, and `make test-env-rebuild` re-admitted it: 69 modules, `installed=172`, `plasticos_accounts=58/58`, fingerprint `07ed95a3be40f364`. |
| Live rerun | 2 s: "base image odoo:19 already trusts the session proxy CA", fixture reused. |

The "Not established" item about an Enterprise fixture admission in a cloud session is now established. Docker bind mounts work in this sandbox; the admission ran through them.

## Rollback

Revert the PR. The bootstrap, the Makefile target, the hook and the docs are additive. The `AGENTS.md` change is one line.

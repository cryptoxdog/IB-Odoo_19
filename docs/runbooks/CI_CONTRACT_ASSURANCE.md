# CI contract assurance

## Purpose and boundaries

The portable adversarial tier protects safety decisions, not just happy paths.
It runs once inside the existing Pure Python Tests job. The existing CI Gate
Result aggregates it; there is no additional workflow, runner, or Docker install.

`install_smoke.sh` remains the real installer and evidence owner. Test code does
not belong inside it. Portable tests exercise the real shell entry points with
small synthetic files, real Git repositories and real process locks. Docker is
an explicit command-boundary fake. These tests do not establish that Enterprise
modules actually install. The normal authorized Enterprise smoke supplies that
separate evidence.

`scripts/odoo_load_surface.py` is the single owner of the Odoo install load
surface (manifests, non-test Python, manifest-declared data, `i18n/`, `static/`,
plus the installer inputs). Install-smoke evidence (v4) is keyed to it, and
`scripts/pr_check_run.sh` uses the same owner to select the local gates by change
class (`scope=full` / `scope=docs_only`, receipt `.cache/pr-check/scope.json`).
The Odoo install itself is not a local publication gate: the "Odoo Install
Smoke" workflow (`.github/workflows/odoo-install-smoke.yml`) runs the real
`scripts/install_smoke.sh` on every pull request with Enterprise checked out from
`odoo/enterprise` (`secrets.ODOO_ENTERPRISE_TOKEN`). `make pr` and `make pr-check`
never invoke the installer; `tests/test_make_pr_publication.py` and
`tests/test_pr_check_scope.py` pin that.
The Odoo-supplied base is installed once into the `odoo_install_smoke_base`
template and cloned for every smoke install, which then installs only the
PlasticOS list. The fake Docker models several databases for that contract.

## Ownership

CI-owned (this runbook's scope):

| File | Responsibility |
| --- | --- |
| `tests/test_ci_event_triggers.py` | Workflow event contract, failure masking, required-test reachability |
| `tests/conftest.py` | Mandatory portable marker semantics; existing Odoo collection policy |
| `ci/check_github_actions_kernel.sh` | Existing workflow structure and full test invocation enforcement |
| `.github/workflows/ci.yml` | One execution, metadata and JUnit artifact upload |

Publication-owned (implemented with the publisher and installer, PR #263; CI only
runs them in the one pure-Python invocation):

| File | Responsibility |
| --- | --- |
| `tests/test_make_pr_publication.py` | Publication, L4, pre-push hook enforcement, origin, push and PR behavior |
| `tests/test_install_smoke_db_guard.py` | Refusal of business/system/remote database targets |
| `tests/test_install_smoke_evidence.py` | Real installer evidence equivalence, invalidation and shared locking |

## Adding a contract

Add a normal pytest test under the existing owner. Mark portable, mandatory
safety tests with `@pytest.mark.adversarial_contract`. Keep ordinary platform-
specific or Odoo-only tests in their provisioned runtime tier.

1. Establish a valid passing control using the real implementation.
2. Change one material input without changing unrelated variables.
3. Assert the expected refusal, missing evidence, or absence of side effects.
4. Include a diagnostic identifying the contract and observed mismatch.
5. Demonstrate that the same test fails on the known-bad implementation and
   passes on the corrected implementation. A bootstrap error is not detection.

Do not duplicate hashing, authorization or cache decisions in the fixture.
Fixtures control external inputs and observe effects; production code decides.
Use event/barrier synchronization for concurrency, not a guessed startup sleep.
Do not place failure-injection switches in production code.

For reference (installer behavior owned by PR #263, not this CI change): the
installer safety guard additionally checks the active Docker context endpoint
(not only `DOCKER_HOST`) before destructive work and pins the effective
`COMPOSE_FILE` to this repository's `docker-compose.yml` to prevent an
implicit `docker-compose.override.yml` from changing the database identity.
These checks refuse unverified remote endpoints and altered Compose inputs.
They are portable negative contracts, not a live Docker isolation attestation.

The CI Gate aggregator validator interprets a deliberately restricted
executable shell shape, rather than accepting target strings in comments,
quotes or unreachable branches. Three independent altered-workflow tests
verify that the pre-repair kernel accepted such false-green gates.

The `adversarial_contract` marker makes skip, xfail and xpass non-passing.
`PLASTICOS_CONTRACT_CI=1`, set only in the full required CI test job, also rejects
selection flags, donor overrides, zero collected contracts and incomplete
contract execution. Focused local pytest selection remains supported.

This is a candidate-owned suite, not an independent security boundary against a
PR that deliberately changes both tests and enforcement. Critical CI/test-owner
changes still require source-bound review. Conversation resolution is a separate
GitHub ruleset setting and must be enabled by a repository administrator.

## Calibration

`PLASTICOS_SMOKE_SOURCE` is a test-only path override for offline calibration of
an immutable installer donor. Production code never reads it; the mandatory CI
tier refuses it. Use a disposable test invocation with the same selected cases
against the known-bad source and the candidate. Keep donor blob hashes, tests,
return codes and JUnit output together. Do not run a whole mutation platform on
every PR and do not copy old source into the production tree.

PR #263 at `d208724ac4e74d1f0f36a9e02709309b68afa63f` is the initial donor. Its
installer blob is `c224fba943344c692d6bb08d9c16ff23474e0709`. The acceptance cases
live in PR #263's installer suite and cover the mounted Enterprise checkout,
metadata-preserving byte edits, untracked bytes, actual image identity, effective
configuration, exact module inventory, stale success after failure,
cross-worktree serialization, and the shared smoke database's instance identity.

## Diagnosing a failed PR

Open the failing required job before changing code. The artifact named
`pure-python-<run_id>-<run_attempt>` contains:

- `revision.json`: source HEAD, base SHA, actual tested checkout SHA, event and
  run identity. A pull-request merge checkout is not its source HEAD.
- `pure-python.xml`: actual pytest cases, outcomes and failure diagnostics.

Use the failing node ID for a focused local reproduction. Repair the actual
owner, retain the adverse case, then let the normal full tier validate the
candidate once. Do not delete a test, broaden a suppression, change a baseline,
or turn a mandatory dependency into a skip merely to obtain green CI.

A skipped optional real-gitleaks integration test is not proof of real scanner
execution. The production publisher still refuses a missing scanner; the
separate Secret Detection job remains mandatory.

## Runtime evidence and cost

Installer evidence (PR #263) is local, disposable and versioned. It binds byte content,
effective Compose service configuration, actual installed image identity, exact
custom/Enterprise inventories and live installed states. Old, malformed,
incomplete or changed evidence is not a cache hit. Do not publish this local
record: effective input digests may cover private configuration.

The resource lock is shared by worktrees of the same operating-system account
using the same local Docker daemon/project/database. Multiple accounts or hosts
sharing one daemon require a separately admitted locking arrangement; they are
not certified by this local lock. Missing lock capability refuses the operation.

Contract tests add portable test runtime, not Enterprise installation runs.
Measure any effect on publication time on the actual developer machine. Passing
portable contracts, passing runtime smoke and merge authorization remain three
different claims.

# CI contract assurance

## Purpose and boundaries

The portable adversarial tier protects safety decisions, not just happy paths.
It runs inside the existing Pure Python Tests job as the PR-fast mandatory
marker lane (`PLASTICOS_CI_TIER=pr_fast`). A second invocation may add structurally
selected non-marker modules. Unknown scope fails that job. The unfiltered
Odoo-free `pytest tests/` suite runs only from `.github/workflows/nightly-full-python.yml`
on Staging. That nightly suite is not the Odoo ORM runtime. CI Gate Result
aggregates the PR jobs. There is no Docker install in either pure-Python lane.

`install_smoke.sh` remains the real installer and evidence owner. Test code does
not belong inside it. Portable tests exercise the real shell entry points with
small synthetic files, real Git repositories and real process locks. Docker is
an explicit command-boundary fake. These tests do not establish that Enterprise
modules actually install. The normal authorized Enterprise smoke supplies that
separate evidence.

## Ownership

CI-owned (this runbook's scope):

| File | Responsibility |
| --- | --- |
| `tests/test_ci_event_triggers.py` | Workflow event contract, failure masking, required-test reachability |
| `tests/conftest.py` | Mandatory portable marker semantics; existing Odoo collection policy |
| `ci/check_github_actions_kernel.sh` | Workflow structure, PR-fast argv, and nightly full-suite enforcement |
| `ci/pr_fast_scope.py` | Structural PR scope receipt; unknown scope is a blocker |
| `ci/run_pr_fast_tests.py` | PR-fast mandatory marker run and non-overlapping scoped run |
| `ci/nightly_full_run.py` | Staging-only unfiltered Odoo-free suite |
| `.github/workflows/ci.yml` | PR-fast execution, metadata and JUnit artifact upload |
| `.github/workflows/nightly-full-python.yml` | Daily Staging schedule and manual Staging dispatch |

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
`PLASTICOS_CONTRACT_CI=1` is set on the PR-fast job and the Staging nightly job.
`PLASTICOS_CI_TIER=pr_fast` admits only `-m adversarial_contract` over `tests/`
or `-m 'not adversarial_contract'` over explicit test modules. `nightly_full`
rejects every selector. A missing tier, `PYTEST_ADDOPTS`, donor overrides, zero
collected contracts, and incomplete contract execution fail. Focused local
pytest selection remains supported when `PLASTICOS_CONTRACT_CI` is unset.

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
- `pr-fast-contracts.xml`: mandatory adversarial cases, outcomes and failure diagnostics.
- `pr-fast-receipt.json`: base, head, selector, selected modules, and unknown paths.
- `pr-fast-scoped.xml`: present when a non-marker module was selected.

Use the failing node ID for a focused local reproduction. Repair the actual
owner, retain the adverse case, then let the PR-fast lane validate the
candidate. The Staging nightly suite is the unfiltered Odoo-free rerun; it is
not evidence that the pull request itself executed `pytest tests/`. Do not
delete a test, broaden a suppression, change a baseline, or turn a mandatory
dependency into a skip merely to obtain green CI.

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

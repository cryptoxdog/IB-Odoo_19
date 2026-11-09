# ADR-011: Runtime dependencies use exact proven SDK revisions

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Gate_SDK defines the transport contract shared by Odoo, Gate, and EIE. If those
services silently install materially different SDK revisions, they can produce
and reject each other's packets while every repository's own CI is green.

## Options Considered

### Option A: Exact commit pins, upgraded on evidence (chosen)
- Pros: reproducible; an upgrade is a reviewable event with a diff and a test
  run; the release set can be reasoned about.
- Cons: upgrades are manual and can lag.

### Option B: Track `main` / a floating branch
- Pros: always current; no upgrade toil.
- Cons: the wire contract changes without any repository changing; a Gate_SDK
  merge can break production Odoo with no Odoo commit. **Rejected.**

### Option C: Version range (`>=x,<y`)
- Pros: allows patch uptake.
- Cons: for a git-sourced transport contract this is a floating pin with extra
  steps; two services can still resolve different commits.

## Decision

Production dependencies must use exact, reproducible Gate_SDK
versions/revisions. Do not depend on `main`, `latest`, a floating git branch,
or an unbounded development revision for coordinated production behavior.

Before changing the pinned Gate_SDK revision: inspect the exact diff; run the
SDK tests; prove dependency resolution; prove installed-package behavior; prove
cross-repository packet compatibility.

## Consequences

- **Release-set rule:** Odoo, Gate, and EIE must not be assumed compatible
  merely because each installs *some* version of Gate_SDK. Compatibility must
  be executable.
- The pin's transitive constraints are part of the contract: the SDK's own
  dependency floors (for example its `cryptography` window) can crash the host
  runtime and must be resolved in the consumer's dependency set, not worked
  around at import time.

## Amendment 2026-11-08 — consumers declare the `v1` channel (supersedes exact-SHA pins)

**Status:** Accepted. Operator decision 2026-11-08: "float on @v1".

The Decision section's rule that a production dependency names an exact commit
is superseded for Gate_SDK. Gate_SDK now owns release identity
(`contracts/RELEASE_IDENTITY_LEDGER.json`, schema
`l9.gate_sdk.release_identity_ledger.v2`). Its `consumer_contract` is the
moving major tag `v1` and forbids `branch`, `commit_sha` and `fork` refs.
Gate, EIE and CEG already declare `@v1`. A PlasticOS exact SHA was the one
identity in the constellation outside that contract. Its two pins (`92279da`,
then `7ec6cdf`) each lagged the channel, and the first predated
`GateClient.execute()`.

- **Declaration.** `requirements.txt` declares
  `constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@v1`.
  Odoo.sh, the Dockerfile and the CI `gate-sdk-tests` job all install that line.
- **Enforcement.** `scripts/validate_sdk_pin.py` fails on a commit sha, an exact
  release tag, `main`/`master`, the `cryptoxdog` fork, a non-git requirement, or a
  second declaration. It also scans other requirements files, Dockerfiles and
  workflows for a Gate_SDK ref. `tests/test_validate_sdk_pin.py` runs it on the
  tree in the `pure-python-tests` CI job. The script's old `92279da` check was
  invoked nowhere.
- **Option B is still rejected.** `main` and floating branches stay forbidden.
  The `v1` tag moves only when Gate_SDK publishes a compatible `1.x` release
  under its PR-only delivery policy. That is the compatibility promise the
  exact pin was standing in for.
- **What replaces "upgraded on evidence".** Every PR runs the `gate-sdk-tests` job
  against whatever `v1` resolves to. A Gate_SDK release that breaks the bridge
  turns that job red on the next PR. It does not stay hidden behind a stale pin.
  Odoo.sh has no hash lockfile, so the object installed for a build shows only in
  that build's install log. A reproducible-lock requirement would need a separate
  decision.
- **Evidence for this change** (from `7ec6cdf`, v1.2.0, to `bc1c74c`, v1.3.2, which
  `v1` resolves to on 2026-11-08):
  - The diff is additive: `src/constellation_node_sdk/trace_context.py` plus a
    dispatch hook, 304 lines added and none removed.
  - `pyproject.toml` changes only its version, so the dependency window, including
    `cryptography`, is unchanged.
  - The `gate-sdk-tests` bridge suite passes against the installed `v1`
    (`tests/test_gate_sdk_invocation.py`, `tests/test_gate_single_egress.py`,
    `tests/test_gate_canonical_contract.py`): 111 passed, none skipped.

The Consequences section's release-set rule still holds. Compatibility must be
executable, and the bridge tests are where it is executed.

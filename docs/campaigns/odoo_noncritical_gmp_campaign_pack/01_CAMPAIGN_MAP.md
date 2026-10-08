# Campaign Map

## Objective

Convert the non-critical register from a noisy collection of heuristics into a truthful engineering register with one owner per concern.

## Root causes

| Root cause | Current symptom | Authoritative fix |
|---|---|---|
| Test-quality authority fragmentation | Large Moderate weak-test / no-test-coverage noise | One weak-test owner; remove pseudo-coverage claims |
| Privilege escalation ownership drift | `UNJUSTIFIED_SUDO` Moderates | Domain-owned elevation boundaries + scanner aligned to repo law |
| Duplicate state-transition auditing | `STATE_BYPASS` Moderates | `ci/check_state_guard_bypass.py` is sole owner |
| Query intent not represented | `UNBOUNDED_SEARCH` Moderates | Classify query purpose before changing ORM realization |
| XPath checker/policy contradiction | 16 Medium XPath findings | Named-anchor topology first; checker follows canonical rule |

## Dependency graph

```text
GMP-NC-A  Test Assurance Authority
    |
    +--> refresh Moderate census

GMP-NC-B  Privilege Boundary ---------+
GMP-NC-C  State Audit Ownership -------+--> GMP-NC-F Final Reconciliation
Prior High performance scanner --------> GMP-NC-D Query Boundedness --+
GMP-NC-E  XPath Topology -------------+
```

`GMP-NC-D` consumes the completed High performance-scanner remediation from the earlier production-debt campaign. It must not create a competing scanner architecture.

## Branching rule

- If a predecessor has merged, branch from current `origin/Staging`.
- If a stage materially consumes an unmerged predecessor, stack from the exact predecessor HEAD.
- Do not wait for unrelated PRs to merge.
- Record branch base and predecessor in the GMP evidence report.

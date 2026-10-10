# Campaign Map

## Objective

Convert the non-critical register from a noisy collection of heuristics into a truthful engineering register with one owner per concern. Adjacent checks that do not nest stay separate. A justified elevation and a business-complete search may remain.

## Root causes

| Root cause | Current symptom | Authoritative fix |
|---|---|---|
| Test-quality authority fragmentation | Large Moderate weak-test / no-test-coverage noise | One weak-test owner covering every tree the extended audit walks; remove pseudo-coverage claims |
| Privilege escalation ownership drift | `UNJUSTIFIED_SUDO` Moderates | Scanner stops treating a nearby comment as authorization; retain a justified elevation |
| Adjacent state-audit questions | `STATE_BYPASS` Moderates beside the CI guard check | One owner only where one finding set contains the other |
| Query intent not represented | `UNBOUNDED_SEARCH` Moderates | Classify intent inside `check_unbounded_searches`; leave the N+1 method untouched |
| XPath checker/policy contradiction | 16 Medium XPath findings | Named-anchor topology first; checker guidance and positional safe-patterns follow that law |

## Dependency graph

```text
GMP-NC-A  Test Assurance Authority
    |
    +--> refresh Moderate census

GMP-NC-B  Privilege Boundary ---------+
GMP-NC-C  State Audit Containment -----+--> GMP-NC-F Final Reconciliation
GMP-NC-D  Query Boundedness -----------+
GMP-NC-E  XPath Topology --------------+
```

`GMP-NC-D` shares `scripts/audit/performance_audit.py` with the High N+1 scanner slice. Isolate that method: do not edit `check_n_plus_one_queries`. If an unmerged High slice already modifies the file, stack on that HEAD or wait. Do not fork a second scanner.

## Branching rule

- If a predecessor has merged, branch from current `origin/Staging`.
- If a stage materially consumes an unmerged predecessor, stack from the exact predecessor HEAD.
- Do not wait for unrelated PRs to merge.
- Record branch base and predecessor in the GMP evidence report.

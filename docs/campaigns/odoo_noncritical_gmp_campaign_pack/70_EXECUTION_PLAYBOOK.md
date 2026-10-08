# Execution Playbook

## Recommended order

### 1. GMP-NC-A — Test assurance authority
Run first because it is likely responsible for the largest numerical distortion in the Moderate register.

After completion, regenerate the Moderate census. Do **not** use the historical ~980 number for sizing later stages.

### 2. GMP-NC-B — Privilege boundaries
Run from the then-current `Staging` or stack only if consuming an unmerged predecessor.

### 3. GMP-NC-C — State audit ownership
Tooling-only by default. If it uncovers a real runtime state defect, stop and split that defect into its own remediation.

### 4. GMP-NC-D — Query boundedness
Do not start until the prior High performance-scanner hardening is present in the execution base or exact predecessor.

### 5. GMP-NC-E — XPath topology
Independent of query work. Can run in parallel with B/C if operationally convenient, but should remain its own PR/GMP.

### 6. GMP-NC-F — Final reconciliation
Run only after the stages you intend to count as completed are actually present in the final subject.

## Per-stage operator rhythm

```text
bind current target
    -> census
    -> root-cause decision
    -> modification lock
    -> smallest realization
    -> focused validation
    -> before/after comparison
    -> evidence report
    -> verify publication SSOT
    -> publish once
    -> stop
```

## Modification lock

Before Phase 3 of every GMP, the executor must state the exact files it intends to modify.

If a newly required file falls outside that list:

1. classify why it is required;
2. prove no existing in-scope owner can satisfy the obligation;
3. otherwise do not add it;
4. if it changes architecture/scope, stop and report rather than silently widening.

## No-reopen rule

A later stage may consume an earlier result. It may not opportunistically "improve" it.

Post-lock discoveries have only three dispositions:

- realize within current contract;
- record as separate future work;
- block on a proven contradiction.

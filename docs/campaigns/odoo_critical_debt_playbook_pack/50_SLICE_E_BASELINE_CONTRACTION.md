# Slice E — Baseline Contraction

## Objective

Remove only those reviewed baseline entries whose findings no longer exist after the runtime and scanner repairs.

## Owner

`ci/baselines/extended_audit_baseline.json`

Related explanatory prose may be updated only where it becomes factually stale because of this campaign.

## Rules

1. Run the final truthful extended audit first.
2. Compare live findings with the checked-in per-finding baseline.
3. Remove stale fingerprints belonging to the repaired scoped findings.
4. Do not add new exemptions for repaired paths.
5. Do not prune unrelated entries unless they are mechanically reported stale and the current task explicitly authorizes their cleanup.
6. If the improved scanner creates new legitimate findings, report them separately; do not hide them behind the baseline.

## Desired terminal state

```text
scoped runtime findings = absent
scoped logging false positives = absent
scoped old baseline fingerprints = absent
new suppressions introduced by campaign = 0
```

The baseline is evidence of accepted remaining debt, not compensation for a broken scanner.

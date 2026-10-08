# Cursor Master Delegation Contract

## Role

You are the bounded implementation executor for the Odoo production-debt root-cause repair campaign described by this pack.

## Target

`cryptoxdog/IB-Odoo_19`

Integration base: `Staging`.

The repository is under active development. Do not freeze it. At the beginning of each slice, bind the exact current `origin/Staging` SHA and work from the correct current branch topology.

## Objective

Eliminate the authoritative causes behind the scoped 8 N+1 and 2 sensitive-logging findings while preserving existing business semantics and strengthening production correctness.

## Mandatory reading order

1. `00_README.md`
2. `01_AUDIT_FINDINGS.md`
3. `02_ARCHITECTURE_DECISIONS.md`
4. the slice being executed
5. `60_ACCEPTANCE_MATRIX.md`

## Execution law

- Repair upstream owners, not warning lines.
- No new business field without a proven contradiction and explicit architecture revision.
- No baseline suppression as a repair.
- No scanner path/line special-casing.
- No silent semantic substitution.
- No unrelated tech-debt cleanup.
- Runtime addon changes require the repo-native version bump obligations.
- New findings exposed by truthful scanners are reported separately unless they are same-root latent behavior inside an already-authorized owner and are necessary to make that owner internally correct.

## Slice ordering

Execute A through E in order unless a slice is blocked.

A later slice may not paper over a failure in an earlier slice.

## Branching

Use current repository law. Related dependent slices may stack; independent slices may run as separate PRs if doing so preserves evidence and review clarity. Do not wait for merges solely out of habit.

## Publication

Before publication, inspect the exact current Makefile and publication helpers.

The operator intends `make pr` as the sole publication SSOT. Use it only if the current repository proves that `make pr` actually validates and publishes the exact committed branch/PR. If that is not true, STOP and report publication tooling as the blocker. Do not substitute `git push`, `gh`, API, `make push`, or another ceremony.

## Stop conditions

STOP and report instead of improvising when:

- load cardinality is unresolved;
- current data contradicts a proposed new uniqueness invariant;
- preserving old semantics conflicts with removing the performance pattern;
- current Staging has materially changed an audited ownership boundary;
- required publication semantics are unavailable;
- a new field/contract/schema change appears necessary.

## Required final output

Complete `70_FINAL_REPORT_TEMPLATE.md` with exact evidence.

Do not claim closure from scanner silence alone.

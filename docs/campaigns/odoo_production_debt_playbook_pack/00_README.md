# Odoo Production Debt Root-Cause Repair Pack

## Purpose

This pack is a Cursor execution playbook for a narrowly scoped pre-production hardening campaign in:

`cryptoxdog/IB-Odoo_19`

The campaign exists to eliminate the authoritative causes behind the scoped findings originally observed as:

- 8 `N_PLUS_ONE_QUERY` findings
- 2 `SENSITIVE_DATA_LOGGED` findings

It does **not** authorize a repo-wide technical-debt cleanup.

## Operating posture

The repository is actively evolving. **Do not freeze `Staging`.** At the start of each slice, bind the exact then-current `origin/Staging` HEAD and record it in the execution report. If `Staging` moves later, rebase/stack/reconcile according to the repo's current branch law without reopening the architecture unless a real contradiction is proven.

The architecture is root-cause first:

```text
business invariant / relationship semantics
                ↓
correct set-based runtime implementation
                ↓
database enforcement where required
                ↓
behavior + runtime proof
                ↓
scanner truthfulness
                ↓
baseline contraction
```

## Hard boundaries

Do not:

- patch individual warning lines merely to silence scanners;
- weaken business invariants;
- add new business fields just to optimize lookups;
- change PO transaction semantics from M2M to `origin` traversal;
- treat `load.transaction_id` as authoritative until cardinality is proven;
- rewrite harmless migration log prose to satisfy the security scanner;
- add scanner filename/line special cases;
- add new baseline suppressions for repaired paths;
- absorb unrelated findings discovered by the improved scanners;
- mix ERP SQL/import work into this campaign;
- invent publication commands.

## Execution order

1. Read `01_AUDIT_FINDINGS.md`.
2. Read `02_ARCHITECTURE_DECISIONS.md`.
3. Execute slices in order:
   - `10_SLICE_A_RUNTIME_RELATIONSHIPS.md`
   - `20_SLICE_B_UNIQUENESS.md`
   - `30_SLICE_C_SECURITY_SCANNER.md`
   - `40_SLICE_D_PERFORMANCE_SCANNER.md`
   - `50_SLICE_E_BASELINE_CONTRACTION.md`
4. Use `60_ACCEPTANCE_MATRIX.md` as the final closure gate.
5. Emit the execution report in `70_FINAL_REPORT_TEMPLATE.md` format.

## Publication rule

The operator's intended publication SSOT is `make pr`, but **do not assume the current branch implements that correctly**. At execution time Cursor must inspect the exact current Makefile/publication helpers. Only use `make pr` if it has verified publication semantics for the exact target. If it is still only a local test gate or is otherwise semantically wrong, STOP publication and report the mismatch. Do not substitute `git push`, `gh`, API publication, or another Make target.

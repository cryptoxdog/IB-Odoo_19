# Odoo Non-Critical Debt GMP Campaign Pack

Target repository: `cryptoxdog/IB-Odoo_19`
Integration branch: `Staging`
Campaign purpose: remediate the known non-Critical/non-High issue register by curing upstream causes, not patching individual findings.

## Operating law

- The repository is actively developing. Do **not** pin future execution to the audit SHA.
- At the start of every GMP, bind the then-current `origin/Staging` SHA and record it in the report.
- Preserve previously completed Critical/High remediation. Do not reopen it unless a proven contradiction blocks the current GMP.
- One GMP = one bounded root-cause campaign. Do not absorb newly discovered adjacent debt.
- No new file unless an existing owner cannot lawfully satisfy the invariant.
- No contract/schema/field widening for convenience.
- Prefer the highest authoritative owner that removes an entire failure class.
- `Unknown` is not success.
- Runtime-affecting `plasticos_*` changes require the repository's current module-version/upgrade obligations.
- Publication must use the operator-approved repo-native ceremony. At execution time, verify the exact current `Makefile` still implements `make pr` as the publication SSOT before using it. Do not substitute another publication mechanism.

## Stage map

1. `GMP-NC-A` — Test assurance authority convergence
2. `GMP-NC-B` — Privilege boundary convergence
3. `GMP-NC-C` — State audit containment
4. `GMP-NC-D` — Query boundedness semantics (`check_unbounded_searches` only)
5. `GMP-NC-E` — XPath anchor topology convergence
6. `GMP-NC-F` — Final non-critical register reconciliation

Each contract is in `contracts/` and is executable independently when its declared predecessor conditions are satisfied.

## Required report behavior

Every stage must end with:

- exact start SHA and final HEAD;
- files changed;
- before/after finding counts for the stage-owned family;
- root cause closed or not closed;
- tests/checks actually run and their outcomes;
- any `Unknown` or blocked evidence;
- explicit statement that prior completed remediation was not reopened;
- publication result, if publication was authorized and performed.

See `80_FINAL_REPORT_TEMPLATE.md`.

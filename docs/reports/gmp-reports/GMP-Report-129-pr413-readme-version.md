# GMP-129: PR #413 CI repair (plasticos_transaction README version)

**Task:** PR #413 remediation: fix the CI Gate failure where the README front matter lagged the manifest bump. Make no quantity-conversion or vendor-credit changes. Publish without Docker install-smoke.
**Tier:** RUNTIME
**Branch:** `fix/erp-historical-xmlid` (base `Staging`)
**Head before repair:** `95c91637be8ef5d512c50ef488f9e31b92c3b757`

## Evidence at the starting head

| Check | Result |
|---|---|
| CI Gate Result | failure |
| Pure Python Tests | 1 failed, 2788 passed, 49 skipped |
| Failing test | `tests/test_module_readme_batch_pipeline.py::test_front_matter_matches_manifest[plasticos_transaction]`: `assert '19.0.2.3.58' == '19.0.2.3.59'` |
| Ruff, Static Analysis, Audit Baseline, Secret Detection, Gate SDK Bridge, Governed Semgrep, GitGuardian | success |

## Diagnosis

Fixture defect introduced by this PR. Commit `95c91637` bumped `plasticos_transaction/__manifest__.py` from
`19.0.2.3.58` to `19.0.2.3.59`, but the README's derived-index front matter (`module_version`) still named the
old version. The test is correct: it holds the README index to the committed manifest. No product code was wrong.

## TODOs

- T1: `plasticos_transaction/README.md`: REPLACE `module_version: 19.0.2.3.58` with `19.0.2.3.59`

## Validation

| Gate | Result |
|---|---|
| `pytest tests/test_module_readme_batch_pipeline.py` | 101 passed (failed before the repair) |
| `pytest tests/` (full pure-Python suite, local) | see the publish commit and the CI rerun |
| Scope: `git status --porcelain` before commit | only `plasticos_transaction/README.md` and this report |

## Out of scope (unchanged)

- The XMLID classifier (`account_move_inherit.py`, `transaction.py`) and its regression test.
- Quantity conversion and vendor-credit linkage. Both stay blocked on operator decisions.
- `tests/production-rehearsal/fidelity_run.py` still uses SQL `LIKE` for the historical census.
  It predates this PR and needs a separate change.
- The Ruff tooling and `workflow_state.md` commits already on the branch. Whether they stay in this PR is an
  operator decision. Splitting them now would rewrite a published branch.

## Not established by this GMP

- Docker install-smoke and Odoo runtime tests. This was published with `PR_SMOKE_BYPASS` at the operator's request,
  so no revision-bound Docker receipt exists for this head.

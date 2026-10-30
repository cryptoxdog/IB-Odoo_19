# Campaign receipt — v1.2 implementation PR

**Branch:** `feat/production-erp-crm-bootstrap`
**Base:** `origin/Staging` `42556d2e5e7434be43f2ff7f89e66b1c8ee6c15a`
**Tested head:** `1116eab9bda8c18c06b7c6cf368eeb7d6be0b62d`. This receipt and the regenerated `SHA256SUMS.txt` are a later docs-only commit.
**Module versions:** `plasticos_partner_import` `19.0.2.10.31`, `plasticos_crm_sync` `19.0.1.9.14`

## Verdicts

| Gate | Verdict |
|---|---|
| PR_PUBLISHABLE | YES: one PR to `Staging` through `make pr` |
| MERGE_PROMOTION_READY | NOT_PROVEN: the full Enterprise suite was not run on the candidate (see below) |
| HOSTED_IMPORT_READY | NOT_RUN: no Odoo.sh probe, permit or SQL access proof was attempted |
| POST_IMPORT_DATA_ACCEPTED | NOT_RUN: no import was run |

## Evidence

| Check | Result |
|---|---|
| `ruff check .` and `ruff format --check .` | pass |
| `check_module_wiring`, `check_circular_deps`, `check_pipeline_v2_guard`, `check_no_local_intelligence`, `shellcheck` on the wrapper | pass |
| Pack `12_VALIDATE_PACKAGE.py` | structural PASS |
| New pure tests: `tests/test_erp_production_permit.py` and `tests/test_crm_history_cohort.py` | pass |
| Targeted pure tier (phantom enum, weak-test authority, CRM completeness, ERP layer, scratch-DB guard, summary schema, import contract, summary, SQL justification) | 407 passed |
| Full pure tier, last run before the final fixes | 2,005 passed and 4 failed (phantom-enum literals and two assertion-free tests). All four were fixed and pass in the targeted run. The full tier was not re-run, on operator instruction. |
| Docker `make test-module m=plasticos_partner_import,plasticos_crm_sync` on a clone of `odoo_test_tpl_ee_c9e8a81f52f23680` | 125 run, 0 failed, 0 errors, exit 0. The receipt names head `1116eab9`. It reads `dirty: true` only because of the uncommitted local `.vscode/settings.json` editor wiring. |
| Full Enterprise suite (`make test-odoo`) on the candidate | NOT_RUN |
| Base full suite at `42556d2e` | NOT_RUN in this campaign. The reference receipt from another checkout at that head is 1,103 tests, 8 failures and 2 errors in `plasticos_claims`, `plasticos_security_base`, `plasticos_commission` and `plasticos_crm_bridge`. That is not a differential. |

## What the PR does not do

- It performs no Production write, deployment, reset, merge or import.
- It adds no ORM model, field or schema.
- It imports no worksheet images or documents.
- It posts no accounting and creates no payment.
- It adds no environment-only Production switch.
- It does not touch `pipeline_v2.py`.
- `make import-vanillasoft` without a census keeps its existing semantics.

## Open items for the operator

1. Run the full Enterprise suite on the candidate and on the base. Compare the two before calling the PR merge-ready.
2. Do the hosted Odoo.sh read-only probes (runbook steps 1 and 3) and the SQL access proof before any permit is written.
3. Supply the go-live ERP SQL snapshot and the 4,876-ID census as external runtime inputs (D3).

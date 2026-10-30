# GMP-129 — OdooLS 66 contracts

**Task:** Execute contracts C00 through C05. Do not publish.
**Branch:** `feat/odools-66-ownership`
**Base:** `Staging` `7798abedc076f63fbd8b3bbebbfb61227a4b6a96`
**Seam status:** not green. OdooLS was not re-parsed. Enterprise Docker tests were not run.

The pack receipt `13_EXECUTION_RECEIPT_TEMPLATE.json` stays `NOT_EXECUTED`. Filling it would break the pre-execution checksum seal, and a PASS result would be false. This report is the execution record.

## Contracts

| Contract | Result | Evidence |
|---|---|---|
| C00 | Done, read-only | `.l9/odools/c00-baseline.json` — 66 live rows bound, 0 missing |
| C01 | Code moved, runtime unknown | Transaction, logistics, documents, native hooks |
| C02 | Code moved, runtime unknown | Offer, PO, product, privacy, dashboard timestamp |
| C03 | Code moved, runtime unknown | Intake-field audit, stock count, Gate and native tests relocated |
| C04 | Not green | No fresh OdooLS census and no CE/EE run |
| C05 | Not published | `.l9/odools/c05-not-published.json` |

## Row disposition

41 rows were moved to the addon that already owns the model. 17 rows are analyzer or environment limits and were not rewritten. 8 rows stay unproven until the scripts import is shown at runtime.

| Root | Rows | Disposition |
|---|---|---|
| R01 | 4 | Analyzer limit. Gate SDK kwargs are valid on the pinned SDK. No code change. |
| R02 | 8 | Unproven. `scripts.evidence_odoo_mapping_consumer` was not imported in a runtime. No code change. |
| R03 | 2 | Environment. Gate exception types. No code change. |
| R04 | 9 | Moved. `plasticos_product` implements `_purchase_product`. |
| R05 | 2 | Moved. Send Offer lives on `plasticos_offer`. |
| R06 | 1 | Moved. Make PO lives on `plasticos_transaction`. |
| R07 | 3 | Moved. The intake field write is the audit. The automation-log create is gone. |
| R08 | 1 | Moved. `is_private` is written from `plasticos_security_base`. |
| R09 | 1 | Left in place. The commission stub stays. The real constraint is `plasticos_commission`. |
| R10 | 7 | Moved. Load lock and reconcile live on `plasticos_logistics`. |
| R11 | 3 | Moved. Compliance service calls live on `plasticos_documents`. |
| R12 | 1 | Moved. The worksheet test counts `stock.quant` and `stock.move`. |
| R13 | 1 | Moved. Accepted-document protection lives on the documents load bridge. |
| R14 | 3 | Moved. Native document lookup lives on `plasticos_documents_native`. |
| R15 | 3 | Moved. Native-dependent tests live in `plasticos_documents_native/tests/test_rehomed_native_cases.py`. |
| R16 | 6 | Moved. Gate enrichment tests live in `plasticos_enrichment`. |
| R17 | 1 | Moved. `last_refresh` is written in `action_refresh`. |
| R18 | 4 | Left in place. Optional semantic-kernel tests. `plasticos_semantic_kernel` was not added to `crm_sync`. |
| R19 | 1 | Left in place. `markupsafe.Markup` stays escaped. |
| R20 | 1 | Left in place. Multiple-definition warning on `test_common.py`. |
| R21 | 4 | Left in place. Informational nested classes. |

## Checks that ran

| Check | Result |
|---|---|
| `ruff` 0.16.0 on the edited Python | Pass |
| `ci/check_critical_manifest.py` | Pass |
| `ci/check_circular_deps.py` | Pass |
| `scripts/check_module_wiring.py` | Pass after wizard models are indexed |
| XML parse of the three intake views | Pass |
| OdooLS re-parse | Not run |
| `make test-module` / `make test-odoo` | Not run |

`plasticos_security_base` now depends directly on `plasticos_partner_import` so the privacy wizard inherit loads. The wiring checker only indexed `models/`, so the wizard `_name` looked unknown. `find_model_definitions` now also indexes `wizards/`.

Native document tests are no longer collected from `plasticos_documents`. They are collected from `plasticos_documents_native`. Whether the Docker roster still runs them was not proven.

## Publication

`make pr` was not run. No push, no GitHub API pull request, no merge, no deploy.

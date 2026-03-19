# Semgrep Audit Summary

**Date:** audit

## Overview

| Metric | Count |
|--------|-------|
| Total Findings | 188 |
| ERROR | 44 |
| WARNING | 144 |
| INFO | 0 |
| Scan Errors | 4 |

## Findings by File

### `ci/audit_cross_module_deps.py` 🟡 4 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 63 | WARNING | odoo-commented-code | Remove commented-out Odoo code |
| 67 | WARNING | odoo-commented-code | Remove commented-out Odoo code |
| 70 | WARNING | odoo-commented-code | Remove commented-out Odoo code |
| 72 | WARNING | odoo-commented-code | Remove commented-out Odoo code |

### `ci/check_automation_field_refs.py` 🔴 2 ERROR

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 26 | ERROR | use-defused-xml | The Python documentation recommends using `defusedxml` inste |
| 262 | ERROR | use-defused-xml-parse | The native Python `xml` library is vulnerable to XML Externa |

### `ci/check_odoo_antipatterns.py` 🟡 2 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 298 | WARNING | odoo-commented-code | Remove commented-out Odoo code |
| 428 | WARNING | odoo-commented-code | Remove commented-out Odoo code |

### `ci/check_state_guard_bypass.py` 🔴 2 ERROR

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 26 | ERROR | use-defused-xml | The Python documentation recommends using `defusedxml` inste |
| 114 | ERROR | use-defused-xml-parse | The native Python `xml` library is vulnerable to XML Externa |

### `ci/check_xpath_stability.py` 🔴 2 ERROR

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 23 | ERROR | use-defused-xml | The Python documentation recommends using `defusedxml` inste |
| 136 | ERROR | use-defused-xml-parse | The native Python `xml` library is vulnerable to XML Externa |

### `plasticos_automation/models/account_move_penalty.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 127 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_automation/models/contract_renewal.py` 🔴 2 ERROR 🟡 2 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 16 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 24 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 27 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 66 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_automation/models/invoice_reminder.py` 🔴 2 ERROR 🟡 2 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 16 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 22 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 57 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 59 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_automation/models/load_automation.py` 🔴 2 ERROR 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 32 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 44 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 81 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_automation/models/purchase_order_automation.py` 🔴 2 ERROR 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 19 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 39 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 75 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_automation/models/sale_approval.py` 🔴 2 ERROR 🟡 3 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 16 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 27 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 35 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 47 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 59 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_automation/models/stock_picking_automation.py` 🔴 2 ERROR 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 39 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 61 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 110 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_automation/models/stock_reorder_alert.py` 🔴 2 ERROR 🟡 2 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 15 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 23 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 26 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 65 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_base/models/feature_gate_mixin.py` 🟡 3 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 41 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 49 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 55 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_base/models/ir_attachment.py` 🔴 2 ERROR

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 16 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 59 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_base/models/midnight_recompute.py` 🔴 2 ERROR 🟡 2 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 40 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 54 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 69 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 110 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_buyer_match_engine/Knowledge Base V8.0/buyer_matching_rag.py` 🟡 3 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 214 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 215 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 359 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_buyer_match_engine/models/graph_service.py` 🔴 2 ERROR 🟡 34 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 130 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 160 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 601 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 605 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 610 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 617 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 810 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 883 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1074 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 1086 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 1115 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1149 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1170 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1191 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1212 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1233 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1254 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1277 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1321 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1350 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1378 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1406 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1435 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1474 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1497 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1518 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1539 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1575 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1656 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1766 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1837 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1892 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1976 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1977 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 2131 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 2207 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_buyer_match_engine/models/intake_extension.py` 🟡 3 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 45 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 70 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 90 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_buyer_match_engine/models/intake_graph_hooks.py` 🟡 2 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 38 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 43 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_buyer_match_engine/models/match_exclusion.py` 🔴 2 ERROR

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 165 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 186 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_buyer_match_engine/models/matcher.py` 🟡 7 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 75 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 81 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 130 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 254 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 310 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 315 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 428 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_buyer_match_engine/models/material_profile_graph_hooks.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 49 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_enrichment/models/enrichment_run.py` 🔴 4 ERROR 🟡 12 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 19 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 108 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 164 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 217 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 219 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 254 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 376 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 410 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 411 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 457 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 465 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 498 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 505 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 513 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 514 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 539 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_enrichment/models/enrichment_service.py` 🟡 9 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 207 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 414 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 425 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 431 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 436 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 445 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 460 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 461 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 528 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_intake/models/intake.py` 🟡 11 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 416 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 441 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 481 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 524 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 757 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 789 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 833 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 863 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 913 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 979 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1000 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_intake/models/material_profile_intake.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 25 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_intake/models/res_partner_intake.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 25 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_logistics/models/load.py` 🔴 2 ERROR 🟡 5 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 20 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 109 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 127 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 362 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 385 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 399 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 425 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_logistics/models/transaction_inherit.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 29 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_offer/models/offer.py` 🔴 2 ERROR 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 242 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 391 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 414 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_transaction/models/account_move_inherit.py` 🟡 5 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 18 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 41 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 56 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 61 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 85 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_transaction/models/audit_cron.py` 🔴 2 ERROR 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 14 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 15 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 45 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_transaction/models/purchase_inherit.py` 🟡 4 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 30 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 45 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 87 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 92 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_transaction/models/sale_inherit.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 26 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_transaction/models/transaction.py` 🔴 5 ERROR 🟡 9 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 510 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 515 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 574 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 792 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 814 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 851 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 942 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 944 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 948 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 1103 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 1177 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 1231 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 1249 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |
| 1298 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_transaction/models/transaction_import_service.py` 🟡 3 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 160 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 179 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 289 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_transaction/services/status_cascade.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 67 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `plasticos_transaction/wizards/transaction_bulk_update_wizard.py` 🔴 1 ERROR

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 83 | ERROR | odoo-raw-sql | Raw SQL detected - prefer ORM methods to prevent SQL injecti |

### `plasticos_transaction/wizards/transaction_import_wizard.py` 🟡 4 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 128 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 185 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 188 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |
| 189 | WARNING | odoo-hardcoded-model-string | Consider using a module-level constant instead of hardcoded  |

### `scripts/check_module_wiring.py` 🟡 1 WARNING

| Line | Severity | Rule | Message |
|------|----------|------|--------|
| 282 | WARNING | odoo-commented-code | Remove commented-out Odoo code |

## Top 10 Rules Triggered

| Rule | Count |
|------|-------|
| semgrep.odoo-hardcoded-model-string | 137 |
| semgrep.odoo-raw-sql | 38 |
| semgrep.odoo-commented-code | 7 |
| python.lang.security.use-defused-xml.use-defused-xml | 3 |
| python.lang.security.use-defused-xml-parse.use-defused-xml-parse | 3 |

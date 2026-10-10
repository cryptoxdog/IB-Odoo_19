# CURSOR EXECUTION REPORT — ODOO PRODUCTION DEBT ROOT-CAUSE REPAIR

The blank `70_FINAL_REPORT_TEMPLATE.md` is unchanged so `SHA256SUMS.txt` still matches the pack. This file is the filled report.

## TARGET

- repository: `cryptoxdog/IB-Odoo_19`
- starting origin/Staging SHA: `92142d367abb04890b6a3a51604d227788ec92d8`
- execution branch(es): `fix/production-debt-root-cause`
- final head(s): recorded at commit time on this branch
- Staging moved during execution: NO (re-fetched before this report)
- reconciliation performed if moved: not required

## SCOPE

- original scoped N+1 findings: transaction profile search, purchase delivery-term search, load transaction searches, facility profile browse, commission rule browse
- original scoped sensitive-log findings: the two static `perplexity_api_key` / `api_key` lines in `plasticos_web_leads/migrations/19.0.1.5.0/post-migrate.py`
- unrelated findings discovered: 78 `N_PLUS_ONE_QUERY` hits from the structural scanner (listed under Slice D)
- unrelated findings modified: NO

## SLICE A — RUNTIME RELATIONSHIPS

### Transaction profiles

- files changed: `plasticos_transaction/models/transaction.py`
- matching semantics preserved: supplier and buyer profile refs still match `(partner_id, polymer_id)` and keep the first row in model order. Supplier material is still the first material profile of the first purchase-order partner.
- batch behavior proven: `TestRelationshipBatch.test_profile_refs_match_polymer_for_a_recordset` and `test_supplier_material_uses_the_first_purchase_partner_profile`
- stored recomputation proven: `test_buyer_facility_recomputes_when_the_profile_is_created` reads `sale.order.partner_id.facility_profile_ids`
- runtime module version: `19.0.2.3.32`

### Purchase order

- M2M remains authority: search domain is `purchase_order_ids in self.ids`
- origin substitution absent: `@api.depends("origin")` is unchanged and `origin` is not the lookup key
- multi-record behavior proven: `test_purchase_delivery_term_uses_m2m_membership`. Several transactions containing one PO keep the first row in transaction `id` order.

### Load relationship

- duplicate load assignment census: `plasticos_logistics/migrations/19.0.1.10.3/pre-migrate.py` ran on local database `odoo` and did not raise
- one-to-one business invariant result: YES
- DB enforcement added if YES: `models.Constraint("UNIQUE (load_id)")` → `plasticos_transaction_unique_load_id`
- inverse relation proof: `TestLoadCardinality.test_create_links_the_sale_order_transaction_once` and `test_a_second_transaction_cannot_take_the_same_load`
- load create batched: one search on `sale_order_id in sale_orders.ids`
- close chatter behavior preserved: `test_close_posts_one_chatter_message` reads `transaction_id` and posts `Logistics closed.` once
- delivery override behavior preserved: `test_delivery_term_override_reads_the_linked_transaction`
- logistics module version: `19.0.1.10.3`

## SLICE B — UNIQUENESS

### Facility profile

- DB constraint retained: `unique(partner_id)`
- same-batch duplicate proof: `TestFacilityUniqueness.test_same_batch_duplicate_partner_is_rejected`
- multi-write proof: `test_multi_write_to_one_partner_is_rejected`
- facility module version: `19.0.5.3.11`

### Commission

- pre-migration duplicate census: `plasticos_commission/migrations/19.0.1.4.1/pre-migrate.py` ran on local database `odoo` and did not raise
- DB invariant mechanism: `models.UniqueIndex("(sales_rep_id) WHERE (active IS TRUE)")` → `plasticos_commission_rule_unique_active_sales_rep`
- same-batch create proof: `TestCommissionUniqueness.test_same_batch_duplicate_rep_is_rejected`
- activation collision proof: `test_activating_a_second_rule_is_rejected`
- reassignment collision proof: `test_reassigning_onto_an_active_rep_is_rejected`
- concurrency proof: `test_database_index_rejects_a_second_active_row` inserts a second active row with SQL, bypassing the Python precheck
- commission module version: `19.0.1.4.1`
- migration version/path if applicable: `plasticos_commission/migrations/19.0.1.4.1/pre-migrate.py`. `migrations/19.0.1.4.0/` was not edited.

## SLICE C — SECURITY SCANNER

- scanner owner changed: `scripts/audit/security_audit.py` `check_sensitive_logging` now walks the AST
- original migration messages changed: NO
- constant sensitive vocabulary negative-control: `tests/test_audit_sensitive_logging.py` (static `api_key` and `token` prose)
- dynamic secret positive-control: positional `api_key` argument
- f-string positive-control: f-string `token`
- format interpolation positive-control: `%` interpolation and `.format`
- original 2 false positives remaining: 0 (repo scan returned 0 `SENSITIVE_DATA_LOGGED` findings)

## SLICE D — PERFORMANCE SCANNER

- AST/structural implementation: `scripts/audit/performance_audit.py` `check_n_plus_one_queries`
- self.search positive-control: PASS
- alias.search positive-control: PASS
- env search positive-control: PASS
- browse-only negative-control: PASS (not reported)
- batch-query negative-control: PASS (not reported)
- `intake_extension` fingerprint: unchanged. `39bbc2ad6a8906c4` remains because that retired file is not this campaign's successor. The current `plasticos_matching/models/intake_extension.py` does not emit a replacement create-in-loop finding.
- newly exposed unrelated findings: 78, not modified and not baselined

1. `plasticos_enrichment/models/enrichment_run.py:300` create
2. `plasticos_enrichment/models/enrichment_run.py:599` search
3. `plasticos_enrichment/models/enrichment_run.py:650` create
4. `plasticos_transaction/models/transaction.py:898` search
5. `plasticos_transaction/models/transaction.py:906` search
6. `plasticos_transaction/models/transaction.py:967` search
7. `plasticos_transaction/models/transaction.py:975` search
8. `plasticos_transaction/models/sale_inherit.py:46` create
9. `plasticos_transaction/models/sale_inherit.py:65` search
10. `plasticos_transaction/models/transaction_import_service.py:185` create
11. `plasticos_logistics/models/freight_estimate.py:83` search
12. `plasticos_logistics/models/freight_governance.py:117` search
13. `plasticos_logistics/models/freight_quote.py:135` search
14. `plasticos_logistics/models/freight_quote.py:629` search_count
15. `plasticos_logistics/models/rate_memory.py:75` create
16. `plasticos_logistics/models/load.py:316` search_count
17. `plasticos_logistics/models/load.py:317` search_count
18. `plasticos_logistics/models/load.py:492` search
19. `plasticos_logistics/models/load.py:498` create
20. `plasticos_logistics/models/load.py:606` search
21. `plasticos_logistics/models/load.py:706` search
22. `plasticos_logistics/models/load.py:709` search
23. `plasticos_logistics/models/load.py:772` search
24. `plasticos_logistics/models/load.py:891` search
25. `plasticos_logistics/models/load.py:1212` search_count
26. `plasticos_logistics/models/load.py:1224` search
27. `plasticos_facility_profile/models/partner_type.py:37` search
28. `plasticos_facility_profile/models/partner_type.py:45` search
29. `plasticos_facility_profile/models/equipment_type.py:38` search
30. `plasticos_facility_profile/models/equipment_type.py:46` search
31. `plasticos_facility_profile/models/res_partner.py:371` create
32. `plasticos_documents/models/transaction_docs.py:153` search
33. `plasticos_documents/models/transaction_docs.py:186` search_count
34. `plasticos_documents/models/transaction_docs.py:308` search_count
35. `plasticos_documents/models/document.py:154` search
36. `plasticos_documents/models/document.py:160` search
37. `plasticos_automation/models/sale_approval.py:50` create
38. `plasticos_automation/models/stock_picking_automation.py:84` create
39. `plasticos_automation/models/purchase_order_automation.py:56` create
40. `plasticos_automation/models/stock_reorder_alert.py:40` search_count
41. `plasticos_automation/models/stock_reorder_alert.py:56` create
42. `plasticos_automation/models/automation_config.py:63` search
43. `plasticos_automation/models/load_automation.py:72` create
44. `plasticos_automation/models/contract_renewal.py:40` search_count
45. `plasticos_automation/models/contract_renewal.py:57` create
46. `plasticos_offer/models/offer.py:195` search_count
47. `plasticos_offer/models/offer_price_bridge.py:27` search
48. `plasticos_material_profile/models/filler_type.py:25` search
49. `plasticos_material_profile/models/filler_type.py:33` search
50. `plasticos_material_profile/models/material_profile.py:344` search_count
51. `plasticos_material_profile/models/material_profile.py:455` search_count
52. `plasticos_material_profile/models/material_profile.py:467` search_count
53. `plasticos_material_profile/models/process_type.py:31` search
54. `plasticos_material_profile/models/process_type.py:39` search
55. `plasticos_material_profile/models/source_type.py:31` search
56. `plasticos_material_profile/models/source_type.py:39` search
57. `plasticos_material_profile/models/material_attribute.py:36` search
58. `plasticos_material_profile/models/material_attribute.py:44` search
59. `plasticos_material_profile/models/packaging_type.py:32` search
60. `plasticos_material_profile/models/packaging_type.py:40` search
61. `plasticos_material_profile/models/material_form.py:31` search
62. `plasticos_material_profile/models/material_form.py:39` search
63. `plasticos_material_profile/models/polymer.py:46` search
64. `plasticos_material_profile/models/polymer.py:54` search
65. `plasticos_material_profile/models/res_partner.py:51` search_count
66. `plasticos_material_profile/models/material_color.py:31` search
67. `plasticos_material_profile/models/material_color.py:39` search
68. `plasticos_crm_bridge/models/material_profile.py:68` search
69. `plasticos_crm_bridge/models/crm_lead.py:110` search_count
70. `plasticos_crm_bridge/models/crm_lead.py:198` search
71. `plasticos_claims/models/claim.py:237` search
72. `plasticos_claims/models/claim.py:246` search
73. `plasticos_claims/models/claim.py:415` search_count
74. `plasticos_intake/models/intake.py:406` search_count
75. `plasticos_intake/models/intake.py:460` search_count
76. `plasticos_intake/models/intake.py:919` create
77. `plasticos_intake/models/res_partner_intake.py:27` search_count
78. `plasticos_intake/models/material_profile_intake.py:27` search_count

Freight `search_count` loops in `load.py` (316, 317) and `_cron_check_dispatch_acknowledgments` (1212, 1224) were left unchanged and appear in this list.

## SLICE E — BASELINE

- stale scoped fingerprints removed: `1bef73dd5727a194`, `361407e29c868b3d`, `a3a81efda66a6c85`, `e987ff873a459254`, `80a9d9186ba1ce44`, `815742c77c786932`, plus the six sensitive-log fingerprints `9920ba370736e92a`, `72a4c9e9b37ef7df`, `bd02e882c6df983c`, `79cc4d7b2b6d857b`, `a1f8d7e4eb29a3ae`, `45dfbc98aa6ed7f9`
- new baseline suppressions introduced: 0
- unrelated baseline entries changed: `39bbc2ad6a8906c4` kept. `_root_cause` rewritten so it no longer claims the removed rows are still present.

## VALIDATION

- `.venv/bin/ruff check` and `.venv/bin/ruff format` on the touched Python trees: passed (ruff 0.16.0)
- `.venv/bin/python -m pytest tests/test_audit_n_plus_one.py tests/test_audit_sensitive_logging.py`: 14 passed
- `make update m=plasticos_commission,plasticos_facility_profile,plasticos_transaction,plasticos_logistics`: Odoo reported `Modules loaded` and `Registry loaded in 7.265s`. Installed versions are `19.0.1.4.1`, `19.0.5.3.11`, `19.0.2.3.32`, `19.0.1.10.3`. The Makefile tail check then exited 1 because pre-existing filestore `FileNotFoundError` tracebacks match its `Traceback` grep. No migration `RuntimeError`.
- Database `odoo`: `plasticos_transaction_unique_load_id` is `UNIQUE (load_id)`. `plasticos_commission_rule_unique_active_sales_rep` is `UNIQUE ... (sales_rep_id) WHERE (active IS TRUE)`.
- Odoo behavior tests on a clone of that database, `--test-tags :TestRelationshipBatch,:TestFacilityUniqueness,:TestCommissionUniqueness,:TestLoadCardinality`: `0 failed, 0 error(s) of 19 tests`
- Extended-audit diff after the baseline edit: known 0, new 78, stale 1 (the retained retired intake fingerprint)

## PUBLICATION

- current publication surface inspected: `Makefile` `pr:` calls `bash scripts/make_push_pipeline.sh`
- `make pr` verified to be publication SSOT: YES
- publication attempted: YES, once, after this report is committed
- if NO, exact blocker: `scripts/audit/check_baseline.py` fails on the 78 new HIGH findings. The plan forbids adding them to the baseline and forbids fixing them in this change. `make pr` also requires a clean worktree, so unrelated local edits (`pyproject.toml`, `odools.toml`, `docs/runbooks/crm lead import/`) are stashed only for the publication command and restored afterward.
- if YES, publication command invoked exactly once: `PR_STACK=auto PR_REMEDIATE=0 make pr`
- PR(s): none expected while the audit-baseline gate is red. The command result is appended below if it differs.

## FINAL VERDICT

- `BLOCKED`

### Remaining blocker(s)

1. Acceptance row H, "current repo-native validation passes", is not met. The truthful performance scanner emits 78 HIGH findings that are absent from `ci/baselines/extended_audit_baseline.json`. Adding them would be a new suppression. Fixing them would leave this campaign's scope.

### Separate future findings (non-blocking to this closed scope)

1. The 78 loop findings listed in Slice D. Load freight counts and the dispatch-acknowledgment cron are in that list on purpose.

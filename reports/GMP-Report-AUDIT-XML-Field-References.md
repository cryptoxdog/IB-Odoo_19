# FIELD REFERENCE AUDIT REPORT
==================================================
**Date:** 2026-03-05 03:26
**Branch:** staging
**Scope:** All plasticos_*/views/*.xml files

## Summary
- **XML files scanned:** 79
- **Models in registry:** 55
- **Total field references checked:** 675
- **Fields verified OK:** 576
- **Fields MISSING (in known models):** 99
- **Skipped (unknown models/wizards):** 66

## MISSING FIELDS (CRITICAL — will crash registry)

| # | XML File | Line | Field | Model | Notes |
|---|----------|------|-------|-------|-------|
| 1 | `plasticos_enrichment/views/enrichment_run_views.xml` | ~59 | `url` | `plasticos.enrichment.run` | Field not defined on model |
| 2 | `plasticos_enrichment/views/enrichment_run_views.xml` | ~60 | `source_type` | `plasticos.enrichment.run` | Field not defined on model |
| 3 | `plasticos_enrichment/views/enrichment_run_views.xml` | ~61 | `crawl_status` | `plasticos.enrichment.run` | Field not defined on model |
| 4 | `plasticos_enrichment/views/enrichment_run_views.xml` | ~62 | `last_crawled_at` | `plasticos.enrichment.run` | Field not defined on model |
| 5 | `plasticos_enrichment/views/enrichment_run_views.xml` | ~63 | `error_message` | `plasticos.enrichment.run` | Field not defined on model |
| 6 | `plasticos_enrichment/views/res_partner_enrichment.xml` | ~13 | `url` | `res.partner` | Field not defined on model |
| 7 | `plasticos_enrichment/views/res_partner_enrichment.xml` | ~14 | `source_type` | `res.partner` | Field not defined on model |
| 8 | `plasticos_enrichment/views/res_partner_enrichment.xml` | ~15 | `crawl_status` | `res.partner` | Field not defined on model |
| 9 | `plasticos_enrichment/views/res_partner_enrichment.xml` | ~16 | `last_crawled_at` | `res.partner` | Field not defined on model |
| 10 | `plasticos_transaction/views/transaction_views.xml` | ~195 | `detail_id` | `plasticos.transaction` | Field not defined on model |
| 11 | `plasticos_transaction/views/transaction_views.xml` | ~196 | `grade_id` | `plasticos.transaction` | Field not defined on model |
| 12 | `plasticos_transaction/views/transaction_views.xml` | ~197 | `description` | `plasticos.transaction` | Field not defined on model |
| 13 | `plasticos_transaction/views/transaction_views.xml` | ~198 | `sale_weight` | `plasticos.transaction` | Field not defined on model |
| 14 | `plasticos_transaction/views/transaction_views.xml` | ~199 | `weight_uom` | `plasticos.transaction` | Field not defined on model |
| 15 | `plasticos_transaction/views/transaction_views.xml` | ~200 | `sale_price` | `plasticos.transaction` | Field not defined on model |
| 16 | `plasticos_transaction/views/transaction_views.xml` | ~201 | `sale_amount` | `plasticos.transaction` | Field not defined on model |
| 17 | `plasticos_transaction/views/transaction_views.xml` | ~202 | `purchase_price` | `plasticos.transaction` | Field not defined on model |
| 18 | `plasticos_transaction/views/transaction_views.xml` | ~203 | `purchase_amount` | `plasticos.transaction` | Field not defined on model |
| 19 | `plasticos_transaction/views/transaction_views.xml` | ~204 | `margin` | `plasticos.transaction` | Field not defined on model |
| 20 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~176 | `max_monthly_throughput_lbs` | `res.partner` | Field not defined on model |
| 21 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~177 | `process_type` | `res.partner` | Field not defined on model |
| 22 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~178 | `feedstock_type` | `res.partner` | Field not defined on model |
| 23 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~179 | `capacity_lbs_month` | `res.partner` | Field not defined on model |
| 24 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~180 | `has_horizontal_baler` | `res.partner` | Field not defined on model |
| 25 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~181 | `has_wash_line` | `res.partner` | Field not defined on model |
| 26 | `plasticos_facility_profile/views/facility_profile_views.xml` | ~182 | `handles_bales` | `res.partner` | Field not defined on model |
| 27 | `plasticos_automation/views/purchase_order_views.xml` | ~11 | `x_ready_for_pickup` | `purchase.order` | Field not defined on model |
| 28 | `plasticos_automation/views/purchase_order_views.xml` | ~12 | `x_ready_confirmed_on` | `purchase.order` | Field not defined on model |
| 29 | `plasticos_automation/views/purchase_order_views.xml` | ~13 | `x_buyer_id` | `purchase.order` | Field not defined on model |
| 30 | `plasticos_automation/views/purchase_order_views.xml` | ~16 | `x_followup_count` | `purchase.order` | Field not defined on model |
| 31 | `plasticos_automation/views/purchase_order_views.xml` | ~17 | `x_last_followup_on` | `purchase.order` | Field not defined on model |
| 32 | `plasticos_automation/views/stock_picking_views.xml` | ~11 | `x_trucker_id` | `stock.picking` | Field not defined on model |
| 33 | `plasticos_automation/views/stock_picking_views.xml` | ~12 | `x_receipt_confirmation` | `stock.picking` | Field not defined on model |
| 34 | `plasticos_automation/views/stock_picking_views.xml` | ~15 | `x_trucker_notified_on` | `stock.picking` | Field not defined on model |
| 35 | `plasticos_automation/views/stock_picking_views.xml` | ~16 | `x_trucker_followup_count` | `stock.picking` | Field not defined on model |
| 36 | `plasticos_automation/views/sale_order_views.xml` | ~11 | `x_delivery_term` | `sale.order` | Field not defined on model |
| 37 | `plasticos_automation/views/sale_order_views.xml` | ~14 | `x_appt_requested` | `sale.order` | Field not defined on model |
| 38 | `plasticos_automation/views/sale_order_views.xml` | ~15 | `x_appt_requested_on` | `sale.order` | Field not defined on model |
| 39 | `plasticos_enrichment_bridge/views/crm_lead_views.xml` | ~35 | `state` | `crm.lead` | Field not defined on model |
| 40 | `plasticos_enrichment_bridge/views/crm_lead_views.xml` | ~36 | `confidence` | `crm.lead` | Field not defined on model |
| 41 | `plasticos_enrichment_bridge/views/crm_lead_views.xml` | ~37 | `fields_enriched` | `crm.lead` | Field not defined on model |
| 42 | `plasticos_enrichment_bridge/views/crm_lead_views.xml` | ~38 | `tokens_used` | `crm.lead` | Field not defined on model |
| 43 | `plasticos_material_profile/views/partner_material_ux.xml` | ~37 | `polymer_id` | `res.partner` | Field not defined on model |
| 44 | `plasticos_material_profile/views/partner_material_ux.xml` | ~38 | `form_id` | `res.partner` | Field not defined on model |
| 45 | `plasticos_material_profile/views/partner_material_ux.xml` | ~39 | `color_id` | `res.partner` | Field not defined on model |
| 46 | `plasticos_material_profile/views/partner_material_ux.xml` | ~40 | `source_type_id` | `res.partner` | Field not defined on model |
| 47 | `plasticos_material_profile/views/partner_material_ux.xml` | ~41 | `contamination_percent` | `res.partner` | Field not defined on model |
| 48 | `plasticos_material_profile/views/partner_material_ux.xml` | ~43 | `has_fr` | `res.partner` | Field not defined on model |
| 49 | `plasticos_material_profile/views/partner_material_ux.xml` | ~45 | `has_metal` | `res.partner` | Field not defined on model |
| 50 | `plasticos_material_profile/views/material_profile_views.xml` | ~198 | `polymer_id` | `res.partner` | Field not defined on model |
| 51 | `plasticos_material_profile/views/material_profile_views.xml` | ~199 | `form_id` | `res.partner` | Field not defined on model |
| 52 | `plasticos_material_profile/views/material_profile_views.xml` | ~200 | `color_id` | `res.partner` | Field not defined on model |
| 53 | `plasticos_material_profile/views/material_profile_views.xml` | ~201 | `source_type_id` | `res.partner` | Field not defined on model |
| 54 | `plasticos_material_profile/views/material_profile_views.xml` | ~202 | `monthly_volume_lbs` | `res.partner` | Field not defined on model |
| 55 | `plasticos_material_profile/views/material_profile_views.xml` | ~203 | `contamination_percent` | `res.partner` | Field not defined on model |
| 56 | `plasticos_crm_bridge/views/material_profile_views.xml` | ~150 | `match_count` | `res.partner` | Field not defined on model |
| 57 | `plasticos_crm_bridge/views/material_profile_views.xml` | ~151 | `best_match_score` | `res.partner` | Field not defined on model |
| 58 | `plasticos_crm_bridge/views/material_profile_views.xml` | ~152 | `transaction_count` | `res.partner` | Field not defined on model |
| 59 | `plasticos_crm_bridge/views/material_profile_views.xml` | ~153 | `last_pickup_date` | `res.partner` | Field not defined on model |
| 60 | `plasticos_crm_bridge/views/crm_lead_views.xml` | ~115 | `lead_id` | `crm.lead` | Field not defined on model |
| 61 | `plasticos_crm_bridge/views/crm_lead_views.xml` | ~117 | `decision` | `crm.lead` | Field not defined on model |
| 62 | `plasticos_crm_bridge/views/crm_lead_views.xml` | ~120 | `state` | `crm.lead` | Field not defined on model |
| 63 | `plasticos_crm_bridge/views/crm_lead_views.xml` | ~125 | `material_description` | `crm.lead` | Field not defined on model |
| 64 | `plasticos_crm_bridge/views/crm_lead_views.xml` | ~126 | `estimated_lbs_per_load` | `crm.lead` | Field not defined on model |
| 65 | `plasticos_order_lines/views/purchase_order_views.xml` | ~15 | `material_description` | `purchase.order` | Field not defined on model |
| 66 | `plasticos_order_lines/views/purchase_order_views.xml` | ~16 | `material_profile_id` | `purchase.order` | Field not defined on model |
| 67 | `plasticos_order_lines/views/purchase_order_views.xml` | ~28 | `color_id` | `purchase.order` | Field not defined on model |
| 68 | `plasticos_order_lines/views/purchase_order_views.xml` | ~29 | `form_id` | `purchase.order` | Field not defined on model |
| 69 | `plasticos_order_lines/views/purchase_order_views.xml` | ~30 | `packaging_type_id` | `purchase.order` | Field not defined on model |
| 70 | `plasticos_order_lines/views/purchase_order_views.xml` | ~31 | `source_type_id` | `purchase.order` | Field not defined on model |
| 71 | `plasticos_order_lines/views/purchase_order_views.xml` | ~32 | `filler_type_id` | `purchase.order` | Field not defined on model |
| 72 | `plasticos_order_lines/views/purchase_order_views.xml` | ~33 | `material_attribute_ids` | `purchase.order` | Field not defined on model |
| 73 | `plasticos_order_lines/views/sale_order_views.xml` | ~15 | `material_description` | `sale.order` | Field not defined on model |
| 74 | `plasticos_order_lines/views/sale_order_views.xml` | ~16 | `material_profile_id` | `sale.order` | Field not defined on model |
| 75 | `plasticos_order_lines/views/sale_order_views.xml` | ~28 | `color_id` | `sale.order` | Field not defined on model |
| 76 | `plasticos_order_lines/views/sale_order_views.xml` | ~29 | `form_id` | `sale.order` | Field not defined on model |
| 77 | `plasticos_order_lines/views/sale_order_views.xml` | ~30 | `packaging_type_id` | `sale.order` | Field not defined on model |
| 78 | `plasticos_order_lines/views/sale_order_views.xml` | ~31 | `source_type_id` | `sale.order` | Field not defined on model |
| 79 | `plasticos_order_lines/views/sale_order_views.xml` | ~32 | `filler_type_id` | `sale.order` | Field not defined on model |
| 80 | `plasticos_order_lines/views/sale_order_views.xml` | ~33 | `material_attribute_ids` | `sale.order` | Field not defined on model |
| 81 | `plasticos_intake/views/intake_views.xml` | ~376 | `selected` | `plasticos.intake` | Field not defined on model |
| 82 | `plasticos_intake/views/intake_views.xml` | ~377 | `buyer_name` | `plasticos.intake` | Field not defined on model |
| 83 | `plasticos_intake/views/intake_views.xml` | ~378 | `buyer_city` | `plasticos.intake` | Field not defined on model |
| 84 | `plasticos_intake/views/intake_views.xml` | ~379 | `buyer_state` | `plasticos.intake` | Field not defined on model |
| 85 | `plasticos_intake/views/intake_views.xml` | ~380 | `match_reason` | `plasticos.intake` | Field not defined on model |
| 86 | `plasticos_intake/views/intake_views.xml` | ~381 | `match_score` | `plasticos.intake` | Field not defined on model |
| 87 | `plasticos_intake/views/intake_views.xml` | ~382 | `typical_price` | `plasticos.intake` | Field not defined on model |
| 88 | `plasticos_product/views/polymer_views.xml` | ~14 | `product_id` | `plasticos.polymer` | Field not defined on model |
| 89 | `plasticos_documents_native/views/document_native_views.xml` | ~18 | `x_doc_type` | `documents.document` | Field not defined on model |
| 90 | `plasticos_documents_native/views/document_native_views.xml` | ~19 | `x_polymer_id` | `documents.document` | Field not defined on model |
| 91 | `plasticos_documents_native/views/document_native_views.xml` | ~22 | `x_transaction_id` | `documents.document` | Field not defined on model |
| 92 | `plasticos_documents_native/views/document_native_views.xml` | ~23 | `x_load_id` | `documents.document` | Field not defined on model |
| 93 | `plasticos_documents_native/views/document_native_views.xml` | ~24 | `x_intake_id` | `documents.document` | Field not defined on model |
| 94 | `plasticos_documents_native/views/document_native_views.xml` | ~29 | `x_verified` | `documents.document` | Field not defined on model |
| 95 | `plasticos_documents_native/views/document_native_views.xml` | ~30 | `x_verified_by` | `documents.document` | Field not defined on model |
| 96 | `plasticos_documents_native/views/document_native_views.xml` | ~32 | `x_verified_at` | `documents.document` | Field not defined on model |
| 97 | `plasticos_documents_native/views/document_native_views.xml` | ~36 | `x_override` | `documents.document` | Field not defined on model |
| 98 | `plasticos_documents_native/views/document_native_views.xml` | ~37 | `x_override_reason` | `documents.document` | Field not defined on model |
| 99 | `plasticos_documents_native/views/document_native_views.xml` | ~42 | `x_plasticos_doc_id` | `documents.document` | Field not defined on model |

## Recommended Fixes

### `plasticos_automation/views/purchase_order_views.xml`
- **x_ready_for_pickup** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_ready_confirmed_on** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_buyer_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_followup_count** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_last_followup_on** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_automation/views/sale_order_views.xml`
- **x_delivery_term** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_appt_requested** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_appt_requested_on** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_automation/views/stock_picking_views.xml`
- **x_trucker_id** on `stock.picking`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_receipt_confirmation** on `stock.picking`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_trucker_notified_on** on `stock.picking`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_trucker_followup_count** on `stock.picking`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_crm_bridge/views/crm_lead_views.xml`
- **lead_id** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **decision** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **state** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **material_description** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **estimated_lbs_per_load** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_crm_bridge/views/material_profile_views.xml`
- **match_count** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **best_match_score** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **transaction_count** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **last_pickup_date** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_documents_native/views/document_native_views.xml`
- **x_doc_type** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_polymer_id** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_transaction_id** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_load_id** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_intake_id** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_verified** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_verified_by** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_verified_at** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_override** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_override_reason** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **x_plasticos_doc_id** on `documents.document`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_enrichment/views/enrichment_run_views.xml`
- **url** on `plasticos.enrichment.run`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **source_type** on `plasticos.enrichment.run`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **crawl_status** on `plasticos.enrichment.run`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **last_crawled_at** on `plasticos.enrichment.run`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **error_message** on `plasticos.enrichment.run`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_enrichment/views/res_partner_enrichment.xml`
- **url** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **source_type** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **crawl_status** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **last_crawled_at** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_enrichment_bridge/views/crm_lead_views.xml`
- **state** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **confidence** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **fields_enriched** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **tokens_used** on `crm.lead`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_facility_profile/views/facility_profile_views.xml`
- **max_monthly_throughput_lbs** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **process_type** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **feedstock_type** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **capacity_lbs_month** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **has_horizontal_baler** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **has_wash_line** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **handles_bales** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_intake/views/intake_views.xml`
- **selected** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **buyer_name** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **buyer_city** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **buyer_state** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **match_reason** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **match_score** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **typical_price** on `plasticos.intake`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_material_profile/views/material_profile_views.xml`
- **polymer_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **form_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **color_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **source_type_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **monthly_volume_lbs** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **contamination_percent** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_material_profile/views/partner_material_ux.xml`
- **polymer_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **form_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **color_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **source_type_id** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **contamination_percent** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **has_fr** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **has_metal** on `res.partner`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_order_lines/views/purchase_order_views.xml`
- **material_description** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **material_profile_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **color_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **form_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **packaging_type_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **source_type_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **filler_type_id** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **material_attribute_ids** on `purchase.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_order_lines/views/sale_order_views.xml`
- **material_description** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **material_profile_id** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **color_id** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **form_id** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **packaging_type_id** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **source_type_id** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **filler_type_id** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **material_attribute_ids** on `sale.order`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_product/views/polymer_views.xml`
- **product_id** on `plasticos.polymer`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view

### `plasticos_transaction/views/transaction_views.xml`
- **detail_id** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **grade_id** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **description** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **sale_weight** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **weight_uom** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **sale_price** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **sale_amount** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **purchase_price** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **purchase_amount** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view
- **margin** on `plasticos.transaction`:
  - Option A: Add field to Python model
  - Option B: Remove field reference from view


## Models in Registry

- `account.move`: 29 fields
- `crm.lead`: 41 fields
- `documents.document`: 38 fields
- `enrichment.mixin`: 31 fields
- `enrichment.run`: 42 fields
- `plasticos.automation.config`: 31 fields
- `plasticos.automation.log`: 31 fields
- `plasticos.claim`: 57 fields
- `plasticos.commission.rule`: 30 fields
- `plasticos.dispatch`: 28 fields
- `plasticos.document`: 45 fields
- `plasticos.document.rule`: 36 fields
- `plasticos.document.tag`: 28 fields
- `plasticos.document.validation.matrix`: 32 fields
- `plasticos.enrichment.extraction`: 36 fields
- `plasticos.enrichment.provenance`: 40 fields
- `plasticos.enrichment.run`: 39 fields
- `plasticos.enrichment.source`: 35 fields
- `plasticos.equipment.type`: 29 fields
- `plasticos.facility.profile`: 73 fields
- `plasticos.filler.type`: 29 fields
- `plasticos.graph.service`: 28 fields
- `plasticos.graph.sync.log`: 33 fields
- `plasticos.intake`: 92 fields
- `plasticos.intake.match`: 36 fields
- `plasticos.load`: 75 fields
- `plasticos.match.exclusion`: 34 fields
- `plasticos.match.result`: 46 fields
- `plasticos.material.attribute`: 31 fields
- `plasticos.material.color`: 29 fields
- `plasticos.material.form`: 29 fields
- `plasticos.material.profile`: 74 fields
- `plasticos.midnight.recompute`: 28 fields
- `plasticos.normalizer.config`: 35 fields
- `plasticos.offer`: 51 fields
- `plasticos.packaging.type`: 29 fields
- `plasticos.partner.type`: 31 fields
- `plasticos.polymer`: 31 fields
- `plasticos.process.type`: 29 fields
- `plasticos.rate.memory`: 31 fields
- `plasticos.source.type`: 29 fields
- `plasticos.transaction`: 106 fields
- `plasticos.transaction.line`: 50 fields
- `plasticos.web.lead`: 54 fields
- `plasticos.web.lead.config`: 41 fields
- `product.product`: 29 fields
- `product.template`: 30 fields
- `purchase.order`: 33 fields
- `purchase.order.line`: 35 fields
- `res.config.settings`: 31 fields
- `res.partner`: 47 fields
- `res.users`: 28 fields
- `sale.order`: 33 fields
- `sale.order.line`: 35 fields
- `stock.picking`: 32 fields

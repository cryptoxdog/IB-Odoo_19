# Field Audit Report — 2026-03-19

## Summary

This report identifies XML views that reference fields not defined on their Python models.
These cause Odoo to fail during module loading.

---


## Statistics

- **Total issues found:** 111
- **Modules affected:** 13
- **Models scanned:** 122

---

## Issues by Module

### plasticos_enrichment (23 issues)

**./plasticos_enrichment/views/enrichment_run_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `crawl_status` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `error_message` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `extracted_at` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `governance_passed` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `inference_type` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `is_injectable` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `last_crawled_at` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `previous_value` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `source_id` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `source_sentence` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `source_type` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `status` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `target_field` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `url` |
| `view_enrichment_run_form` | `plasticos.enrichment.run` | `value_written` |

**./plasticos_enrichment/views/res_partner_enrichment.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_partner_form_enrichment` | `res.partner` | `confidence_score` |
| `view_partner_form_enrichment` | `res.partner` | `crawl_status` |
| `view_partner_form_enrichment` | `res.partner` | `injected_at` |
| `view_partner_form_enrichment` | `res.partner` | `last_crawled_at` |
| `view_partner_form_enrichment` | `res.partner` | `profiles_created` |
| `view_partner_form_enrichment` | `res.partner` | `profiles_updated` |
| `view_partner_form_enrichment` | `res.partner` | `source_type` |
| `view_partner_form_enrichment` | `res.partner` | `url` |

---

### plasticos_order_lines (18 issues)

**./plasticos_order_lines/views/purchase_order_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `purchase_order_form_inherit_material` | `purchase.order` | `color_id` |
| `purchase_order_form_inherit_material` | `purchase.order` | `filler_type_id` |
| `purchase_order_form_inherit_material` | `purchase.order` | `form_id` |
| `purchase_order_form_inherit_material` | `purchase.order` | `material_attribute_ids` |
| `purchase_order_form_inherit_material` | `purchase.order` | `material_description` |
| `purchase_order_form_inherit_material` | `purchase.order` | `material_profile_id` |
| `purchase_order_form_inherit_material` | `purchase.order` | `order_line` |
| `purchase_order_form_inherit_material` | `purchase.order` | `packaging_type_id` |
| `purchase_order_form_inherit_material` | `purchase.order` | `source_type_id` |

**./plasticos_order_lines/views/sale_order_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `sale_order_form_inherit_material` | `sale.order` | `color_id` |
| `sale_order_form_inherit_material` | `sale.order` | `filler_type_id` |
| `sale_order_form_inherit_material` | `sale.order` | `form_id` |
| `sale_order_form_inherit_material` | `sale.order` | `material_attribute_ids` |
| `sale_order_form_inherit_material` | `sale.order` | `material_description` |
| `sale_order_form_inherit_material` | `sale.order` | `material_profile_id` |
| `sale_order_form_inherit_material` | `sale.order` | `order_line` |
| `sale_order_form_inherit_material` | `sale.order` | `packaging_type_id` |
| `sale_order_form_inherit_material` | `sale.order` | `source_type_id` |

---

### plasticos_automation (17 issues)

**./plasticos_automation/views/penalty_rule_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_account_move_form_scrap_management` | `account.move` | `adjustment_line_ids` |
| `view_account_move_form_scrap_management` | `account.move` | `commission_amount` |
| `view_account_move_form_scrap_management` | `account.move` | `commission_paid` |
| `view_account_move_form_scrap_management` | `account.move` | `freight_actual` |
| `view_account_move_form_scrap_management` | `account.move` | `freight_charged` |
| `view_account_move_form_scrap_management` | `account.move` | `freight_variance` |
| `view_account_move_form_scrap_management` | `account.move` | `has_penalty` |
| `view_account_move_form_scrap_management` | `account.move` | `penalty_amount` |
| `view_account_move_form_scrap_management` | `account.move` | `penalty_reason` |
| `view_account_move_form_scrap_management` | `account.move` | `penalty_rule_id` |
| `view_account_move_form_scrap_management` | `account.move` | `reconciliation_notes` |
| `view_account_move_form_scrap_management` | `account.move` | `reconciliation_status` |
| `view_account_move_form_scrap_management` | `account.move` | `transaction_id` |
| `view_account_move_form_scrap_management` | `account.move` | `weight_variance_approved` |
| `view_account_move_form_scrap_management` | `account.move` | `weight_variance_approved_by` |
| `view_account_move_form_scrap_management` | `account.move` | `weight_variance_approved_date` |
| `view_account_move_form_scrap_management` | `account.move` | `weight_variance_percent` |

---

### plasticos_transaction (12 issues)

**./plasticos_transaction/views/transaction_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `transaction_search_ux` | `plasticos.transaction` | `filter_non_compliant` |
| `transaction_search_ux` | `plasticos.transaction` | `group_buyer` |

**./plasticos_transaction/views/transaction_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_transaction_form` | `plasticos.transaction` | `description` |
| `view_transaction_form` | `plasticos.transaction` | `detail_id` |
| `view_transaction_form` | `plasticos.transaction` | `grade_id` |
| `view_transaction_form` | `plasticos.transaction` | `margin` |
| `view_transaction_form` | `plasticos.transaction` | `purchase_amount` |
| `view_transaction_form` | `plasticos.transaction` | `purchase_price` |
| `view_transaction_form` | `plasticos.transaction` | `sale_amount` |
| `view_transaction_form` | `plasticos.transaction` | `sale_price` |
| `view_transaction_form` | `plasticos.transaction` | `sale_weight` |
| `view_transaction_form` | `plasticos.transaction` | `weight_uom` |

---

### plasticos_intake (9 issues)

**./plasticos_intake/views/intake_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `intake_form_ux` | `plasticos.intake` | `buyer_matches` |

**./plasticos_intake/views/intake_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_plasticos_intake_form` | `plasticos.intake` | `buyer_city` |
| `view_plasticos_intake_form` | `plasticos.intake` | `buyer_name` |
| `view_plasticos_intake_form` | `plasticos.intake` | `buyer_state` |
| `view_plasticos_intake_form` | `plasticos.intake` | `match_reason` |
| `view_plasticos_intake_form` | `plasticos.intake` | `match_score` |
| `view_plasticos_intake_form` | `plasticos.intake` | `selected` |
| `view_plasticos_intake_form` | `plasticos.intake` | `typical_price` |

**./plasticos_intake/views/material_profile_intake_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_material_profile_form_intake` | `plasticos.material.profile` | `action_create_purchase_order` |

---

### plasticos_crm_bridge (8 issues)

**./plasticos_crm_bridge/views/crm_lead_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `crm_lead_plastos_bridge_form` | `crm.lead` | `company_name` |
| `crm_lead_plastos_bridge_form` | `crm.lead` | `estimated_lbs_per_load` |
| `crm_lead_plastos_bridge_form` | `crm.lead` | `lead_id` |
| `crm_lead_plastos_bridge_form` | `crm.lead` | `material_description` |

**./plasticos_crm_bridge/views/material_profile_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `partner_form_material_bridge_stats` | `res.partner` | `best_match_score` |
| `partner_form_material_bridge_stats` | `res.partner` | `last_pickup_date` |
| `partner_form_material_bridge_stats` | `res.partner` | `match_count` |
| `partner_form_material_bridge_stats` | `res.partner` | `transaction_count` |

---

### plasticos_facility_profile (7 issues)

**./plasticos_facility_profile/views/facility_profile_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_partner_form_profile_tab` | `res.partner` | `capacity_lbs_month` |
| `view_partner_form_profile_tab` | `res.partner` | `feedstock_type` |
| `view_partner_form_profile_tab` | `res.partner` | `handles_bales` |
| `view_partner_form_profile_tab` | `res.partner` | `has_horizontal_baler` |
| `view_partner_form_profile_tab` | `res.partner` | `has_wash_line` |
| `view_partner_form_profile_tab` | `res.partner` | `process_type` |

**./plasticos_facility_profile/views/partner_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `partner_form_plasticos_ux` | `res.partner` | `facility_profile` |

---

### plasticos_enrichment_bridge (7 issues)

**./plasticos_enrichment_bridge/views/crm_lead_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `crm_lead_enrichment_form` | `crm.lead` | `enrichment_run_ids` |
| `crm_lead_enrichment_form` | `crm.lead` | `enrichment_state` |
| `crm_lead_enrichment_form` | `crm.lead` | `fields_enriched` |
| `crm_lead_enrichment_form` | `crm.lead` | `last_enrichment_confidence` |
| `crm_lead_enrichment_form` | `crm.lead` | `last_enrichment_date` |
| `crm_lead_enrichment_form` | `crm.lead` | `tokens_used` |

**./plasticos_enrichment_bridge/views/res_config_settings_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `res_config_settings_enrichment` | `res.config.settings` | `general_settings` |

---

### plasticos_material_profile (5 issues)

**./plasticos_material_profile/views/partner_material_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `view_partner_form_material_tab` | `res.partner` | `color_id` |
| `view_partner_form_material_tab` | `res.partner` | `contamination_percent` |
| `view_partner_form_material_tab` | `res.partner` | `form_id` |
| `view_partner_form_material_tab` | `res.partner` | `polymer_id` |
| `view_partner_form_material_tab` | `res.partner` | `source_type_id` |

---

### plasticos_product (2 issues)

**./plasticos_product/views/polymer_views.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `plasticos_polymer_view_list_product` | `plasticos.polymer` | `product_id` |
| `plasticos_polymer_view_form_product` | `plasticos.polymer` | `product_id` |

---

### plasticos_logistics (1 issues)

**./plasticos_logistics/views/load_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `load_form_ux` | `plasticos.load` | `status` |

---

### plasticos_offer (1 issues)

**./plasticos_offer/views/offer_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `offer_search_ux` | `plasticos.offer` | `filter_expiring_soon` |

---

### plasticos_claims (1 issues)

**./plasticos_claims/views/claim_ux.xml**

| View ID | Model | Missing Field |
|---------|-------|---------------|
| `claim_search_ux` | `plasticos.claim` | `my_claims` |

---

## Priority Recommendations

### CRITICAL (Will crash on module load)

These are fields referenced in views but not defined on models. Odoo will fail to load.

**Fix approach:** Either:
1. Add the missing field to the Python model
2. Remove the field reference from the XML view

### FALSE POSITIVES (Safe to ignore)

Some items may be false positives:
- Fields from `mail.thread` mixin (message_ids, activity_ids)
- Fields from Odoo base models not in our codebase
- Page/group names mistakenly detected as fields

### Recommended Fix Order

1. Fix modules that are dependencies of others first
2. Start with `plasticos_base`, `plasticos_facility_profile`, `plasticos_material_profile`
3. Then fix bridge modules (`plasticos_crm_bridge`, `plasticos_transaction`)
4. Finally fix UX modules (`*_ux.xml` files)

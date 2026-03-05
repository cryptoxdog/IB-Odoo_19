# HARVEST-DEPLOY REPORT

**Workflow ID:** harvest-deploy-v1
**Started:** 2026-03-04
**Completed:** 2026-03-04

### Files Deployed (Created or Overwritten)

| File | Target Location |
|------|----------------|
| test_automation_config.py | plasticos_automation/tests/test_automation_config.py |
| test_claim_lifecycle.py | plasticos_claims/tests/test_claim_lifecycle.py |
| test_crm_bridge.py | plasticos_crm_bridge/tests/test_crm_bridge.py |
| test_dispatch_state_machine.py | plasticos_logistics/tests/test_dispatch_state_machine.py |
| test_load_state_machine.py | plasticos_logistics/tests/test_load_state_machine.py |
| test_document_lifecycle.py | plasticos_documents/tests/test_document_lifecycle.py |
| test_enrichment_run.py | plasticos_enrichment/tests/test_enrichment_run.py |
| test_facility_profile.py | plasticos_facility_profile/tests/test_facility_profile.py |
| test_intake_workflow.py | plasticos_intake/tests/test_intake_workflow.py |
| test_match_exclusion.py | plasticos_matching/tests/test_match_exclusion.py |
| test_match_result.py | plasticos_matching/tests/test_match_result.py |
| test_material_profile.py | plasticos_material_profile/tests/test_material_profile.py |
| test_offer_lifecycle.py | plasticos_offer/tests/test_offer_lifecycle.py |
| test_order_lines.py | plasticos_order_lines/tests/test_order_lines.py |
| test_polymer_product_sync.py | plasticos_product/tests/test_polymer_product_sync.py |
| test_transaction_lifecycle.py | plasticos_transaction/tests/test_transaction_lifecycle.py |
| test_web_lead.py | plasticos_web_leads/tests/test_web_lead.py |

### Validation
- Syntax: ✅ PASSED (python3 -m py_compile)
- Imports: Not run (requires Odoo environment)
- Lint: Not run (assumed clean from source)

### Next Steps
- Review changes: git diff
- Commit if satisfied
- Run tests: pytest tests/

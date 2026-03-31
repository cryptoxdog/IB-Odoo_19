# Odoo 19 ReBoot - File Tree

**Last Updated:** 2026-03-31
**Totals (approx., excluding `.git` / `.venv`):** ~10,000 directories, ~58,000 files — full clone includes all `plasticos_*` tests, `docs/`, `ci/`, and generated artifacts; numbers drift with daily work.

**Installable Odoo addons:** 30 root-level `plasticos_*` modules with `__manifest__.py`. **Not addons:** `plasticos_graph_3d_embedding/`, `plasticos_graph_engine/`, `plasticos_graph_integration/`, `plasticos_graph_intelligence/` (no root manifest — research / graph code).

```
.
├── AI Agent Files
│   ├── AGENT.md
│   ├── ARCHITECTURE.md
│   ├── CHANGELOG.md
│   ├── CONTRIBUTING.md
│   ├── DEPLOYMENT.md
│   ├── ENVIRONMENT_SPEC.yaml
│   ├── FAQ.md
│   ├── FIXTURE_POLICY.md
│   ├── GLOSSARY.md
│   ├── INVARIANTS.md
│   ├── MIGRATION_GUIDE.md
│   ├── NEO4J_ONTOLOGY.md
│   ├── NEO4J_ONTOLOGY.yaml
│   ├── QUICK_START.md
│   ├── README.md
│   ├── ROADMAP.md
│   ├── SECURITY_MODEL.md
│   ├── TEST_STRATEGY.md
│   ├── compliance_scan.json
│   ├── dependency_graph.json
│   ├── external_id_registry.json
│   ├── model_registry.json
│   ├── repo_spec.md
│   └── repo_spec.yaml
├── PlasticOS
│   └── l9_trace/
├── ci
│   ├── critical_manifest.json
│   ├── check_odoo19_xml.py
│   ├── check_orphan_model_refs.py
│   ├── check_circular_deps.py
│   └── … (~27 `*.py` audit helpers — see `ci/`)
├── config
│   ├── odoo_module_order.yaml
│   └── subsystems/
│       └── readme_config.yaml
├── docs
│   ├── adr/
│   │   ├── ADR-001-master-data-field-architecture.md
│   │   └── ADR-002-action-methods.md
│   ├── Files To Harvest/
│   ├── New AI Use Cases/
│   ├── TEST_WRITING_GUIDE.md
│   └── TODO.md
├── plasticos_accounting
│   ├── data/
│   │   ├── accounts.xml
│   │   └── payment_terms.xml
│   ├── __init__.py
│   ├── __manifest__.py
│   └── README.md
├── plasticos_automation
│   ├── data/
│   │   ├── automation_config_data.xml
│   │   ├── config_parameters.xml
│   │   ├── contract_renewal_cron.xml
│   │   ├── cron_load_sla.xml
│   │   ├── cron_supplier_followup.xml
│   │   ├── cron_trucker_followup.xml
│   │   ├── email_templates.xml
│   │   ├── invoice_reminder_cron.xml
│   │   ├── sale_approval_cron.xml
│   │   ├── stock_alert_cron.xml
│   │   └── workflow_automations.xml
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── automation_config.py
│   │   ├── automation_log.py
│   │   ├── contract_renewal.py
│   │   ├── invoice_reminder.py
│   │   ├── load_automation.py
│   │   ├── purchase_order_automation.py
│   │   ├── sale_approval.py
│   │   ├── sale_order_automation.py
│   │   ├── stock_picking_automation.py
│   │   └── stock_reorder_alert.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_automation_config.py
│   │   ├── test_automation_log.py
│   │   ├── test_contract_renewal.py
│   │   ├── test_cron_contract_invoice.py
│   │   ├── test_cron_load_sla.py
│   │   ├── test_cron_plasticos_automation.py
│   │   ├── test_cron_sale_approval.py
│   │   ├── test_invoice_reminder.py
│   │   ├── test_load_automation.py
│   │   ├── test_module_install.py
│   │   ├── test_purchase_order_automation.py
│   │   ├── test_sale_approval.py
│   │   ├── test_sale_order_automation.py
│   │   ├── test_stock_picking_automation.py
│   │   └── test_stock_reorder_alert.py
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_base
│   ├── data/
│   │   ├── attachment_maintenance_cron.xml
│   │   ├── material_taxonomy.xml
│   │   ├── midnight_recompute_cron.xml
│   │   ├── partner_tags.xml
│   │   ├── sales_reps.xml
│   │   └── service_user.xml
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ir_attachment.py
│   │   └── midnight_recompute.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_cron_graph_sync.py
│   │   ├── test_ir_attachment.py
│   │   ├── test_midnight_recompute.py
│   │   └── test_wizard_partner_import.py
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_buyer_match_engine
│   ├── Knowledge Base V8.0/
│   │   └── (24 YAML knowledge base files)
│   ├── data/
│   │   └── ir_cron_graph_sync.xml
│   ├── doc/
│   │   ├── BOOLEAN_FIELD_MATRIX.md
│   │   ├── CYPHER_BUYER_MATCH_LOGIC.md
│   │   └── GAP_ANALYSIS_*.md
│   ├── models/
│   │   ├── __init__.py
│   │   ├── facility_profile_graph_hooks.py
│   │   ├── graph_service.py
│   │   ├── graph_sync_log.py
│   │   ├── intake_extension.py
│   │   ├── intake_graph_hooks.py
│   │   ├── match_exclusion.py
│   │   ├── matcher.py
│   │   └── material_profile_graph_hooks.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── monitoring.py
│   │   └── neo4j_pool.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_cron_expire_exclusions_deep.py
│   │   ├── test_facility_profile_graph_hooks.py
│   │   ├── test_graph_service.py
│   │   ├── test_graph_service_sync.py
│   │   ├── test_graph_sync_log.py
│   │   ├── test_intake_extension.py
│   │   ├── test_intake_graph_hooks.py
│   │   ├── test_match_exclusion.py
│   │   ├── test_matcher.py
│   │   ├── test_material_profile_graph_hooks.py
│   │   ├── test_module_install.py
│   │   └── test_statemachine_match_result.py
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_claims
│   ├── data/
│   │   ├── claim_cron.xml
│   │   ├── claim_sequence.xml
│   │   └── email_templates.xml
│   ├── models/
│   │   ├── __init__.py
│   │   ├── claim.py
│   │   ├── document_inherit.py
│   │   ├── transaction_claims.py
│   │   └── transaction_claims_bridge.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_action_claim.py
│   │   ├── test_claim.py
│   │   ├── test_claim_computes.py
│   │   ├── test_claim_constraints.py
│   │   ├── test_claim_lifecycle.py
│   │   ├── test_claim_states.py
│   │   ├── test_constraints_claims.py
│   │   ├── test_cron_claims_docs_geo.py
│   │   ├── test_cron_sla_deep.py
│   │   ├── test_depends_plasticos_claim.py
│   │   ├── test_document_inherit.py
│   │   ├── test_module_install.py
│   │   ├── test_statemachine_claim.py
│   │   ├── test_transaction_claims.py
│   │   ├── test_transaction_claims_bridge.py
│   │   └── test_wizard_claim_bulk_update.py
│   ├── views/
│   ├── wizards/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_commission
│   ├── models/
│   │   ├── __init__.py
│   │   ├── commission_rule.py
│   │   └── commission_service.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_commission_rule.py
│   │   └── test_commission_service.py
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_crm_bridge
│   ├── data/
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── crm_lead.py
│   │   ├── crm_lead_vanillasoft.py
│   │   ├── material_profile.py
│   │   └── web_lead.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_action_crm_lead.py
│   │   ├── test_crm_bridge.py
│   │   ├── test_crm_lead.py
│   │   ├── test_crm_lead_vanillasoft.py
│   │   ├── test_material_profile.py
│   │   └── test_web_lead.py
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_dev_tools
│   ├── forbidden/
│   ├── migrations/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_enhanced_matching.py
│   │   ├── test_integrity_audit.py
│   │   ├── test_kb_integration.py
│   │   └── test_seed_validator.py
│   ├── tools/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_documents
│   ├── data/
│   │   ├── cron.xml
│   │   ├── cron_missing_docs.xml
│   │   ├── document_tags_data.xml
│   │   └── scale_ticket_rule.xml
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── compliance_service.py
│   │   ├── document.py
│   │   ├── document_rule.py
│   │   ├── document_tag.py
│   │   ├── document_validation_matrix.py
│   │   ├── load_docs_bridge.py
│   │   ├── transaction_docs.py
│   │   └── transaction_docs_bridge.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_compliance_service.py
│   │   ├── test_cron_compliance_audit_deep.py
│   │   ├── test_document.py
│   │   ├── test_document_lifecycle.py
│   │   ├── test_document_rule.py
│   │   ├── test_document_rules.py
│   │   ├── test_document_tag.py
│   │   ├── test_document_tags.py
│   │   ├── test_document_validation_matrix.py
│   │   ├── test_load_docs_bridge.py
│   │   ├── test_module_install.py
│   │   ├── test_scale_ticket_cron.py
│   │   ├── test_transaction_docs.py
│   │   └── test_transaction_docs_bridge.py
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_documents_native
│   ├── data/
│   ├── migrations/
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_enrichment
│   ├── data/
│   ├── knowledge_base/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enrichment_extraction.py
│   │   ├── enrichment_provenance.py
│   │   ├── enrichment_run.py
│   │   ├── enrichment_service.py
│   │   ├── enrichment_source.py
│   │   └── res_partner.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_cron_enrichment.py
│   │   ├── test_enrichment_e2e.py
│   │   ├── test_enrichment_extraction.py
│   │   ├── test_enrichment_provenance.py
│   │   ├── test_enrichment_run.py
│   │   ├── test_enrichment_service.py
│   │   ├── test_enrichment_source.py
│   │   ├── test_injection.py
│   │   ├── test_module_install.py
│   │   ├── test_normalization.py
│   │   └── test_res_partner.py
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_enrichment_bridge
│   ├── data/
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── wizard/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_facility_profile
│   ├── data/
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── equipment_type.py
│   │   ├── facility_profile.py
│   │   ├── lead_source.py
│   │   ├── partner_type.py
│   │   └── res_partner.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_depends_plasticos_facility_profile.py
│   │   ├── test_equipment_type.py
│   │   ├── test_equipment_types.py
│   │   ├── test_facility_constraints.py
│   │   ├── test_facility_crud.py
│   │   ├── test_facility_profile.py
│   │   ├── test_lead_source.py
│   │   ├── test_module_install.py
│   │   ├── test_partner_type.py
│   │   ├── test_partner_types.py
│   │   └── test_res_partner.py
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── process_codes.py
├── plasticos_geolocalize
│   ├── data/
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_graph_3d_embedding
│   └── memory/kge/
├── plasticos_graph_engine
│   ├── adaptive_tier/
│   ├── anomaly/
│   ├── federated_queries/
│   ├── gnn/
│   ├── ml_tenant_isolation/
│   ├── models/
│   ├── negotiation/
│   ├── services/
│   └── shard_rebalancing/
├── plasticos_graph_integration
│   ├── models/
│   └── services/
├── plasticos_graph_intelligence
│   ├── controllers/
│   ├── models/
│   ├── services/
│   └── tests/
├── plasticos_inference_engine
│   ├── knowledge_base_v8.0/
│   │   └── (24 YAML knowledge base files)
│   ├── tests/
│   ├── ARCHITECTURE_v2_segregated.md
│   ├── README.md
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── contamination_engine.py
│   ├── engine.py
│   ├── grade_engine.py
│   ├── inference_init.py
│   ├── inference_models.py
│   ├── kb_loader.py
│   ├── models.py
│   ├── pipeline_v2.py
│   ├── polymer_aliases.py
│   ├── rule_engine.py
│   └── tier_engine.py
├── plasticos_intake
│   ├── data/
│   │   └── sequence.xml
│   ├── models/
│   │   ├── __init__.py
│   │   ├── intake.py
│   │   ├── intake_match.py
│   │   ├── material_profile_intake.py
│   │   └── res_partner_intake.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_depends_intake_computes.py
│   │   ├── test_depends_plasticos_intake.py
│   │   ├── test_intake.py
│   │   ├── test_intake_computes.py
│   │   ├── test_intake_constraints.py
│   │   ├── test_intake_crud.py
│   │   ├── test_intake_match.py
│   │   ├── test_intake_onchanges.py
│   │   ├── test_intake_properties.py
│   │   ├── test_intake_workflow.py
│   │   ├── test_lazy_partner_sync.py
│   │   ├── test_material_profile_intake.py
│   │   ├── test_module_install.py
│   │   ├── test_onchange_intake.py
│   │   ├── test_onchange_plasticos_intake_all.py
│   │   ├── test_plasticos_intake.py
│   │   └── test_res_partner_intake.py
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_intake_normalizer
│   ├── data/
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_logistics
│   ├── data/
│   │   ├── cron.xml
│   │   ├── incoterms.xml
│   │   └── sequence.xml
│   ├── models/
│   │   ├── __init__.py
│   │   ├── dispatch.py
│   │   ├── load.py
│   │   ├── rate_memory.py
│   │   ├── sale_order_inherit.py
│   │   └── transaction_inherit.py
│   ├── report/
│   │   ├── load_reports.xml
│   │   ├── report_bol_delivery.xml
│   │   ├── report_bol_pickup.xml
│   │   └── report_delivery_order.xml
│   ├── security/
│   ├── services/
│   │   ├── __init__.py
│   │   ├── escalation_engine.py
│   │   ├── rate_engine.py
│   │   └── state_machine.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_cron_escalation_deep.py
│   │   ├── test_dispatch.py
│   │   ├── test_dispatch_state_machine.py
│   │   ├── test_dispatch_transitions.py
│   │   ├── test_load.py
│   │   ├── test_load_reports.py
│   │   ├── test_load_state_machine.py
│   │   ├── test_load_states.py
│   │   ├── test_module_install.py
│   │   ├── test_onchange_logistics_load.py
│   │   ├── test_rate_engine.py
│   │   ├── test_rate_memory.py
│   │   ├── test_sale_order_inherit.py
│   │   ├── test_statemachine_load.py
│   │   ├── test_transaction_inherit.py
│   │   └── test_wizard_load_bulk_update.py
│   ├── views/
│   ├── wizards/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_matching
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   └── match_result.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_match_exclusion.py
│   │   ├── test_match_result.py
│   │   ├── test_match_result_states.py
│   │   └── test_module_install.py
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_material_profile
│   ├── data/
│   │   ├── filler_type_data.xml
│   │   ├── material_attribute_data.xml
│   │   ├── material_color_data.xml
│   │   ├── material_form_data.xml
│   │   ├── packaging_type_data.xml
│   │   ├── polymer_data.xml
│   │   ├── process_type_data.xml
│   │   └── source_type_data.xml
│   ├── models/
│   │   ├── __init__.py
│   │   ├── filler_type.py
│   │   ├── material_attribute.py
│   │   ├── material_color.py
│   │   ├── material_form.py
│   │   ├── material_profile.py
│   │   ├── packaging_type.py
│   │   ├── polymer.py
│   │   ├── process_type.py
│   │   ├── res_partner.py
│   │   └── source_type.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_constraints_material_profile.py
│   │   ├── test_depends_material_profile_computes.py
│   │   ├── test_depends_plasticos_material_profile.py
│   │   ├── test_filler_type.py
│   │   ├── test_form_enum_alignment.py
│   │   ├── test_material_attribute.py
│   │   ├── test_material_color.py
│   │   ├── test_material_form.py
│   │   ├── test_material_profile.py
│   │   ├── test_material_profile_enhanced.py
│   │   ├── test_module_install.py
│   │   ├── test_onchange_material_profile.py
│   │   ├── test_onchange_plasticos_material_profile.py
│   │   ├── test_packaging_type.py
│   │   ├── test_partner_material_sync.py
│   │   ├── test_polymer.py
│   │   ├── test_process_type.py
│   │   ├── test_profile_computes.py
│   │   ├── test_profile_crud.py
│   │   ├── test_registry_uniqueness.py
│   │   ├── test_res_partner.py
│   │   └── test_source_type.py
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── form_codes.py
├── plasticos_offer
│   ├── TODO/
│   ├── data/
│   │   ├── offer_cron.xml
│   │   └── sequence.xml
│   ├── models/
│   │   ├── __init__.py
│   │   ├── intake_offers_bridge.py
│   │   └── offer.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_action_offer.py
│   │   ├── test_depends_offer_computes.py
│   │   ├── test_depends_plasticos_offer.py
│   │   ├── test_intake_offers_bridge.py
│   │   ├── test_module_install.py
│   │   ├── test_offer.py
│   │   ├── test_offer_constraints.py
│   │   ├── test_offer_expiry_cron.py
│   │   ├── test_offer_lifecycle.py
│   │   ├── test_offer_states.py
│   │   ├── test_onchange_offer.py
│   │   ├── test_statemachine_offer.py
│   │   └── test_wizard_offer_bulk_action.py
│   ├── views/
│   ├── wizards/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_order_lines
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_partner_import
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── crm_lead_import_service.py
│   │   ├── partner_import_service.py
│   │   └── validation.py
│   ├── scripts/
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_crm_lead_import_service.py
│   │   ├── test_partner_import_service.py
│   │   ├── test_validation.py
│   │   └── test_wizard_partner_bulk_update.py
│   ├── views/
│   ├── wizards/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_product
│   ├── data/
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_security_base
│   ├── migrations/
│   ├── models/
│   ├── security/
│   ├── tests/
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_transaction
│   ├── data/
│   │   ├── audit_cron.xml
│   │   ├── cron_missing_docs.xml
│   │   ├── res.groups.csv
│   │   └── sequence.xml
│   ├── migrations/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── account_move_inherit.py
│   │   ├── audit_cron.py
│   │   ├── commission_rule.py
│   │   ├── commission_service.py
│   │   ├── intake_bridge.py
│   │   ├── match_result_bridge.py
│   │   ├── offer_bridge.py
│   │   ├── partner_bridge.py
│   │   ├── purchase_inherit.py
│   │   ├── res_users_inherit.py
│   │   ├── sale_inherit.py
│   │   ├── transaction.py
│   │   ├── transaction_bridge.py
│   │   ├── transaction_import_service.py
│   │   └── transaction_line.py
│   ├── scripts/
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_account_move_inherit.py
│   │   ├── test_audit_cron.py
│   │   ├── test_close_race.py
│   │   ├── test_commission_rule.py
│   │   ├── test_commission_rules.py
│   │   ├── test_commission_service.py
│   │   ├── test_compliance_failure.py
│   │   ├── test_concurrency.py
│   │   ├── test_constraints_transaction.py
│   │   ├── test_depends_plasticos_transaction.py
│   │   ├── test_depends_transaction_computes.py
│   │   ├── test_deterministic_replay.py
│   │   ├── test_domain_isolation.py
│   │   ├── test_financial_audit.py
│   │   ├── test_full_replay.py
│   │   ├── test_intake_bridge.py
│   │   ├── test_integrity_enforcement.py
│   │   ├── test_legacy_migration.py
│   │   ├── test_load_inherit.py
│   │   ├── test_match_result_bridge.py
│   │   ├── test_migration.py
│   │   ├── test_migration_safety.py
│   │   ├── test_module_install.py
│   │   ├── test_multi_currency.py
│   │   ├── test_offer_bridge.py
│   │   ├── test_partner_bridge.py
│   │   ├── test_performance_scale.py
│   │   ├── test_purchase_inherit.py
│   │   ├── test_res_users_inherit.py
│   │   ├── test_rpc_abuse.py
│   │   ├── test_sale_inherit.py
│   │   ├── test_security_permissions.py
│   │   ├── test_sequence_concurrency.py
│   │   ├── test_sequence_race.py
│   │   ├── test_statemachine_transaction.py
│   │   ├── test_transaction.py
│   │   ├── test_transaction_bridge.py
│   │   ├── test_transaction_computes.py
│   │   ├── test_transaction_constraints.py
│   │   ├── test_transaction_crud.py
│   │   ├── test_transaction_import_service.py
│   │   ├── test_transaction_lifecycle.py
│   │   ├── test_transaction_line.py
│   │   ├── test_transaction_states.py
│   │   ├── test_weight_reconciliation.py
│   │   ├── test_wizard_transaction_bulk_assign.py
│   │   ├── test_wizard_transaction_bulk_update.py
│   │   └── test_wizard_transaction_import.py
│   ├── views/
│   ├── wizards/
│   ├── GUIDE.md
│   ├── __init__.py
│   ├── __manifest__.py
│   └── hooks.py
├── plasticos_web_leads
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── web_lead_api.py
│   ├── data/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ai_normalizer.py
│   │   ├── classification_engine.py
│   │   ├── image_analyzer.py
│   │   ├── web_lead.py
│   │   ├── web_lead_bridge.py
│   │   └── web_lead_config.py
│   ├── security/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_ai_normalizer.py
│   │   ├── test_classification_engine.py
│   │   ├── test_controller_api.py
│   │   ├── test_image_analyzer.py
│   │   ├── test_module_install.py
│   │   ├── test_web_lead.py
│   │   ├── test_web_lead_bridge.py
│   │   ├── test_web_lead_config.py
│   │   ├── test_web_lead_create_from_agent.py
│   │   ├── test_web_lead_triage_pipeline.py
│   │   └── test_wizard_lead_bulk_action.py
│   ├── views/
│   ├── wizards/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_admin_dashboard
│   ├── data/
│   ├── models/
│   │   ├── __init__.py
│   │   └── admin_dashboard.py
│   ├── security/
│   ├── views/
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_odoo_standard_apps
│   ├── README.rst
│   ├── __init__.py
│   └── __manifest__.py
├── plasticos_website
│   ├── data/
│   │   └── website_data.xml
│   ├── static/
│   │   └── src/img/logo.png
│   ├── views/
│   │   └── website_templates.xml
│   ├── __init__.py
│   └── __manifest__.py
├── reports
│   ├── repo-index/
│   │   └── repo-index-json/
│   ├── BUG_FIXES_SUMMARY.md
│   ├── GAP_ANALYSIS_AND_CONSOLIDATION.md
│   ├── GMP-Report-*.md
│   ├── cron_hardening_report.md
│   ├── csv_schema_index.json
│   └── repo_spec.md
├── scripts
│   ├── audit/
│   │   ├── api_regression.py
│   │   ├── business_logic_audit.py
│   │   ├── odoo_audit.py
│   │   ├── performance_audit.py
│   │   ├── run_all_audits.py
│   │   ├── schema_audit.py
│   │   ├── security_audit.py
│   │   ├── test_audit.py
│   │   └── xml_field_audit.py
│   ├── check_module_wiring.py
│   ├── check_module_wiring.sh
│   ├── check_odoo_patterns.sh
│   ├── collect_module_info.py
│   ├── convert_sql_constraints.py
│   ├── export_odoo_index.py
│   ├── fix_db_permissions.py
│   ├── generate_subsystem_readmes.py
│   ├── get_odoo_module_order.py
│   ├── rebuild-odoo-no-demo.sh
│   ├── run-odoo-tests.sh
│   ├── setup_neo4j.sh
│   └── validate_manifest.py
├── tests
│   ├── contracts/
│   │   ├── __init__.py
│   │   ├── test_api_signature_contracts.py
│   │   ├── test_bridge_wiring_contracts.py
│   │   ├── test_computed_field_deps.py
│   │   ├── test_crm_lead_contracts.py
│   │   ├── test_intake_contracts.py
│   │   ├── test_partner_contracts.py
│   │   ├── test_selection_contracts.py
│   │   └── test_transaction_contracts.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_account_move_transaction_link.py
│   │   ├── test_compliance_service.py
│   │   ├── test_cron_idempotency.py
│   │   ├── test_graph_hooks_trigger.py
│   │   ├── test_intake_onchange_cascade.py
│   │   ├── test_match_result_guards.py
│   │   ├── test_offer_state_machine.py
│   │   ├── test_polymer_product_sync.py
│   │   ├── test_sale_order_transaction_autocreate.py
│   │   └── test_write_unlink_guards.py
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── common.py
│   ├── test_action_methods.py
│   ├── test_bridge_contracts.py
│   ├── test_bridge_models.py
│   ├── test_constraint_validation.py
│   ├── test_constraints_material_profile.py
│   ├── test_constraints_onchanges.py
│   ├── test_cron_*.py
│   ├── test_cypher_schema_alignment.py
│   ├── test_error_handling.py
│   ├── test_golden_flows.py
│   ├── test_integration_flows.py
│   ├── test_odoo19_compat.py
│   ├── test_odoo_test_setup_validity.py
│   ├── test_onchange_*.py
│   ├── test_performance.py
│   ├── test_phantom_enum_values.py
│   ├── test_process_enum_alignment.py
│   ├── test_repo_dependency_integrity.py
│   ├── test_security_acl.py
│   └── test_state_machines.py
├── tests-odoo
│   ├── __init__.py
│   ├── case.py
│   ├── common.py
│   ├── form.py
│   ├── loader.py
│   ├── result.py
│   ├── shell.py
│   ├── suite.py
│   ├── tag_selector.py
│   └── test_*.py
├── tools
│   └── cron_invariant_check.py
├── .github/workflows/
│   ├── lint.yml
│   ├── module-check.yml
│   ├── odoo-audit.yml
│   ├── release.yml
│   ├── security.yml
│   └── test-quality.yml
├── .pre-commit-config.yaml
├── Dockerfile
├── docker-compose.yml
├── filetree.md
├── pyproject.toml
├── requirements.txt
├── TODO.md
└── workflow_state.md
```

## Module Summary

| Module | Description | Tests |
|--------|-------------|-------|
| `plasticos_admin_dashboard` | RevOps KPI dashboard (admin) | - |
| `plasticos_accounting` | Chart of accounts and payment terms | - |
| `plasticos_automation` | Cron jobs, workflow automation, alerts | 16 tests |
| `plasticos_base` | Core utilities, attachments, midnight recompute | 5 tests |
| `plasticos_buyer_match_engine` | Neo4j graph matching, buyer matching AI | 13 tests |
| `plasticos_claims` | Claims management and tracking | 17 tests |
| `plasticos_commission` | Commission rules and calculations | 3 tests |
| `plasticos_crm_bridge` | CRM lead integration | 7 tests |
| `plasticos_dev_tools` | Development utilities, audits | 5 tests |
| `plasticos_documents` | Document management, compliance | 15 tests |
| `plasticos_documents_native` | Native Odoo documents integration | 3 tests |
| `plasticos_enrichment` | Data enrichment pipeline | 12 tests |
| `plasticos_enrichment_bridge` | Enrichment CRM bridge | 5 tests |
| `plasticos_facility_profile` | Facility profiles and equipment | 12 tests |
| `plasticos_geolocalize` | Geolocation services | 3 tests |
| `plasticos_inference_engine` | AI inference, polymer knowledge base | 2 tests |
| `plasticos_intake` | Material intake management | 18 tests |
| `plasticos_intake_normalizer` | Intake data normalization | 3 tests |
| `plasticos_logistics` | Loads, dispatches, BOL reports | 17 tests |
| `plasticos_matching` | Match results management | 5 tests |
| `plasticos_material_profile` | Material profiles, polymers | 23 tests |
| `plasticos_offer` | Offer management | 14 tests |
| `plasticos_order_lines` | Sale/Purchase order line extensions | 4 tests |
| `plasticos_odoo_standard_apps` | Auto-install bundle of standard Odoo CE apps | - |
| `plasticos_partner_import` | Partner data import | 5 tests |
| `plasticos_product` | Product template extensions | 3 tests |
| `plasticos_security_base` | Security groups and rules | 3 tests |
| `plasticos_transaction` | Transaction management (core) | 49 tests |
| `plasticos_web_leads` | Web lead ingestion, AI triage | 12 tests |
| `plasticos_website` | Website theme/templates, branding assets | - |

## Test Directories

- `tests/` - Root-level cross-module tests
- `tests/contracts/` - Contract tests (**8** test modules, plus `__init__.py`)
- `tests/integration/` - Integration tests (**10** test modules, plus `__init__.py`)
- `tests-odoo/` - Odoo test framework utilities
- `*/tests/` - Module-specific tests

**Note:** Test counts in the module table are point-in-time; module and root `tests/` suites change often. Use `pytest tests/ --collect-only` (with Odoo test deps as required) for current totals.

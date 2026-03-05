.
├── .cursorignore
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── TODO.md
├── cieTrade.WksDetail.Test.csv
├── pyproject.toml
├── requirements.txt
├── workflow_state.md
├── .github
│   └── workflows
│       ├── lint.yml
│       ├── module-check.yml
│       ├── release.yml
│       └── security.yml
├── config
│   ├── odoo_module_order.yaml
│   └── subsystems
│       └── readme_config.yaml
├── docs
│   └── adr
│       └── ADR-001-master-data-field-architecture.md
├── plasticos_accounting
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   └── data
│       ├── accounts.xml
│       └── payment_terms.xml
├── plasticos_automation
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
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
│   ├── models
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
│   ├── security
│   │   ├── ir.model.access.csv
│   │   └── security.xml
│   └── views
│       ├── automation_config_views.xml
│       ├── automation_log_views.xml
│       ├── purchase_order_views.xml
│       ├── sale_order_views.xml
│       └── stock_picking_views.xml
├── plasticos_base
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── attachment_maintenance_cron.xml
│   │   ├── material_taxonomy.xml
│   │   ├── midnight_recompute_cron.xml
│   │   ├── partner_tags.xml
│   │   ├── sales_reps.xml
│   │   └── service_user.xml
│   └── models
│       ├── __init__.py
│       ├── ir_attachment.py
│       └── midnight_recompute.py
├── plasticos_buyer_match_engine
│   ├── Mack_agent_buyer_matching v7.0.py
│   ├── README.md
│   ├── README.rst
│   ├── Readme-IB.md
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── Knowledge Base V8.0
│   │   ├── KB Leverage Ideas.md
│   │   ├── buyer_matching_rag.md
│   │   ├── buyer_matching_rag.py
│   │   ├── buyer_matching_rag.yaml
│   │   ├── plasticos_kb_abs_v8.0.yaml
│   │   ├── plasticos_kb_blowmolding_standards_v8.0.yaml
│   │   ├── plasticos_kb_eva_v8.0.yaml
│   │   ├── plasticos_kb_gaylord_boxes_v8.0.yaml
│   │   ├── plasticos_kb_hdpe_v8.0.yaml
│   │   ├── plasticos_kb_hips_v8.0.yaml
│   │   ├── plasticos_kb_ldpe_v8.0.yaml
│   │   ├── plasticos_kb_lldpe_v8.0.yaml
│   │   ├── plasticos_kb_pa_v8.0.yaml
│   │   ├── plasticos_kb_pbt_v8.0.yaml
│   │   ├── plasticos_kb_pc_v8.0.yaml
│   │   ├── plasticos_kb_pet_v8.0.yaml
│   │   ├── plasticos_kb_pmma_v8.0.yaml
│   │   ├── plasticos_kb_pom_v8.0.yaml
│   │   ├── plasticos_kb_pp_supersacs_v8.0.yaml
│   │   ├── plasticos_kb_pp_v8.0.yaml
│   │   ├── plasticos_kb_ppo_v8.0.yaml
│   │   ├── plasticos_kb_process_fit_atoms_v8.0.yaml
│   │   ├── plasticos_kb_ps_v8.0.yaml
│   │   ├── plasticos_kb_pvc_v8.0.yaml
│   │   ├── plasticos_kb_template_v8.0.yaml
│   │   ├── plasticos_kb_tpe_v8.0.yaml
│   │   └── plasticos_kb_tpu_v8.0.yaml
│   ├── data
│   │   └── ir_cron_graph_sync.xml
│   ├── doc
│   │   ├── BOOLEAN_FIELD_MATRIX.md
│   │   ├── BUILT_NOT_WIRED_AUDIT.md
│   │   ├── CYPHER_BUYER_MATCH_LOGIC.md
│   │   ├── GAP_ANALYSIS_45_STEP_CURRENT.md
│   │   ├── GAP_ANALYSIS_45_STEP_FRAMEWORK.md
│   │   ├── MATCHER_GAP_ANALYSIS.md
│   │   └── gap_analysis_v2.md
│   ├── models
│   │   ├── __init__.py
│   │   ├── facility_profile_graph_hooks.py
│   │   ├── graph_service.py
│   │   ├── graph_sync_log.py
│   │   ├── intake_extension.py
│   │   ├── intake_graph_hooks.py
│   │   ├── match_exclusion.py
│   │   ├── matcher.py
│   │   └── material_profile_graph_hooks.py
│   ├── security
│   │   └── ir.model.access.csv
│   ├── services
│   │   ├── __init__.py
│   │   ├── monitoring.py
│   │   └── neo4j_pool.py
│   ├── tests
│   │   ├── __init__.py
│   │   └── test_matcher.py
│   └── views
│       ├── intake_button_views.xml
│       └── match_exclusion_views.xml
├── plasticos_claims
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── claim_cron.xml
│   │   ├── claim_sequence.xml
│   │   └── email_templates.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── claim.py
│   │   ├── document_inherit.py
│   │   ├── transaction_claims.py
│   │   └── transaction_claims_bridge.py
│   ├── security
│   │   ├── claims_security.xml
│   │   └── ir.model.access.csv
│   ├── views
│   │   ├── claim_bulk_update_wizard_views.xml
│   │   ├── claim_menus.xml
│   │   ├── claim_ux.xml
│   │   ├── claim_views.xml
│   │   └── transaction_claims_bridge_views.xml
│   └── wizards
│       ├── __init__.py
│       └── claim_bulk_update_wizard.py
├── plasticos_crm_bridge
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── plasticos_crm_bridge.md
│   ├── data
│   │   ├── crm_stage_data.xml
│   │   ├── lead_source_data.xml
│   │   └── partner_category_data.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── crm_lead.py
│   │   ├── crm_lead_vanillasoft.py
│   │   ├── material_profile.py
│   │   └── web_lead.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       ├── crm_lead_views.xml
│       └── material_profile_views.xml
├── plasticos_dev_tools
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── forbidden
│   │   ├── README.md
│   │   ├── agent_health_monitor_v6.0C.py
│   │   ├── buyer_matching_runtime_v6.0C.py
│   │   ├── error_recovery_daemon_v6.0C.py
│   │   ├── governance_edit_lock_v6.0.py
│   │   ├── offer_handler.py
│   │   ├── plasticos_event_logger_v6.0.py
│   │   ├── plasticos_module_init_v6.0.py
│   │   ├── system_state_registry_v6.0C.py
│   │   └── trust_index_calculator_v6.0C.py
│   ├── migrations
│   │   └── 19.0.1.0.0
│   │       ├── post-migrate.py
│   │       └── pre-migrate.py
│   ├── tests
│   │   ├── README.md
│   │   ├── __init__.py
│   │   ├── test_enhanced_matching_v6.0.py
│   │   ├── test_integrity_audit.py
│   │   ├── test_kb_integration.py
│   │   └── test_seed_validator.py
│   └── tools
│       ├── index_export.py
│       ├── integrity_audit.py
│       ├── seed_validator.py
│       ├── test_enhanced_matching_v6.0.py
│       └── test_kb_integration.py
├── plasticos_documents
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── cron.xml
│   │   ├── cron_missing_docs.xml
│   │   ├── document_tags_data.xml
│   │   └── scale_ticket_rule.xml
│   ├── migrations
│   │   └── 19.0.2.1.0
│   │       └── pre-migrate.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── compliance_service.py
│   │   ├── document.py
│   │   ├── document_bridge.py
│   │   ├── document_rule.py
│   │   ├── document_tag.py
│   │   ├── document_validation_matrix.py
│   │   ├── load_docs_bridge.py
│   │   ├── transaction_docs.py
│   │   └── transaction_docs_bridge.py
│   ├── security
│   │   ├── ir.model.access.csv
│   │   └── security.xml
│   ├── tests
│   │   ├── __init__.py
│   │   └── test_scale_ticket_cron.py
│   └── views
│       ├── document_extension_views.xml
│       ├── document_rule_views.xml
│       ├── document_tag_views.xml
│       ├── document_views.xml
│       ├── load_docs_bridge_views.xml
│       ├── transaction_docs_bridge_views.xml
│       ├── transaction_docs_views.xml
│       └── validation_matrix_views.xml
├── plasticos_documents_native
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── data
│   │   ├── document_folders.xml
│   │   └── document_tags.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── document_native.py
│   │   └── document_sync.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       └── document_native_views.xml
├── plasticos_enrichment
│   ├── README.md
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── cron.xml
│   │   └── sequence.xml
│   ├── knowledge_base
│   │   ├── plasticos_kb_PP_v8.0.yaml
│   │   ├── plasticos_kb_template_v8.0.yaml
│   │   └── pp_compounding_recycling_v7.0r.yaml
│   ├── models
│   │   ├── __init__.py
│   │   ├── enrichment_extraction.py
│   │   ├── enrichment_provenance.py
│   │   ├── enrichment_run.py
│   │   ├── enrichment_service.py
│   │   ├── enrichment_source.py
│   │   └── res_partner.py
│   ├── security
│   │   ├── ir.model.access.csv
│   │   └── security.xml
│   ├── tests
│   │   ├── __init__.py
│   │   ├── test_injection.py
│   │   └── test_normalization.py
│   └── views
│       ├── enrichment_run_views.xml
│       ├── enrichment_source_views.xml
│       └── res_partner_enrichment.xml
├── plasticos_enrichment_bridge
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── ir_config_parameter.xml
│   │   └── ir_cron.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── crm_lead.py
│   │   ├── enrichment_mixin.py
│   │   ├── enrichment_run.py
│   │   └── res_config_settings.py
│   ├── security
│   │   └── ir.model.access.csv
│   ├── views
│   │   ├── crm_lead_views.xml
│   │   ├── enrichment_run_views.xml
│   │   └── res_config_settings_views.xml
│   └── wizard
│       ├── __init__.py
│       ├── enrichment_wizard.py
│       └── enrichment_wizard_views.xml
├── plasticos_facility_profile
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── process_codes.py
│   ├── data
│   │   ├── equipment_type_data.xml
│   │   ├── lead_source_data.xml
│   │   └── partner_type_data.xml
│   ├── migrations
│   │   └── 19.0.4.0.0
│   │       └── post-migrate.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── equipment_type.py
│   │   ├── facility_profile.py
│   │   ├── lead_source.py
│   │   ├── partner_type.py
│   │   └── res_partner.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       ├── facility_profile_ux.xml
│       ├── facility_profile_views.xml
│       ├── lead_source_views.xml
│       ├── partner_type_views.xml
│       └── partner_ux.xml
├── plasticos_geolocalize
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   └── cron_geo_backfill.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── intake_geo.py
│   │   └── res_partner_geo.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       └── intake_geo_views.xml
├── plasticos_inference_engine
│   ├── ARCHITECTURE_v2_segregated.md
│   ├── README.md
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── additional files to harvest.md
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
│   ├── tier_engine.py
│   └── knowledge_base_v8.0
│       ├── plasticos_kb_abs_v8.0.yaml
│       ├── plasticos_kb_blowmolding_standards_v8.0.yaml
│       ├── plasticos_kb_eva_v8.0.yaml
│       ├── plasticos_kb_gaylord_boxes_v8.0.yaml
│       ├── plasticos_kb_hdpe_v8.0.yaml
│       ├── plasticos_kb_hips_v8.0.yaml
│       ├── plasticos_kb_ldpe_v8.0.yaml
│       ├── plasticos_kb_lldpe_v8.0.yaml
│       ├── plasticos_kb_pa_v8.0.yaml
│       ├── plasticos_kb_pbt_v8.0.yaml
│       ├── plasticos_kb_pc_v8.0.yaml
│       ├── plasticos_kb_pet_v8.0.yaml
│       ├── plasticos_kb_pmma_v8.0.yaml
│       ├── plasticos_kb_pom_v8.0.yaml
│       ├── plasticos_kb_pp_supersacs_v8.0.yaml
│       ├── plasticos_kb_pp_v8.0.yaml
│       ├── plasticos_kb_ppo_v8.0.yaml
│       ├── plasticos_kb_process_fit_atoms_v8.0.yaml
│       ├── plasticos_kb_ps_v8.0.yaml
│       ├── plasticos_kb_pvc_v8.0.yaml
│       ├── plasticos_kb_template_v8.0.yaml
│       ├── plasticos_kb_tpe_v8.0.yaml
│       └── plasticos_kb_tpu_v8.0.yaml
├── plasticos_intake
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── intake.py
│   │   ├── intake_match.py
│   │   ├── material_profile_intake.py
│   │   └── res_partner_intake.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       ├── intake_ux.xml
│       ├── intake_views.xml
│       └── material_profile_intake_views.xml
├── plasticos_intake_normalizer
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── cron_batch_normalize.xml
│   │   └── normalizer_config_data.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── intake_normalizer.py
│   │   └── normalizer_config.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       ├── intake_normalizer_views.xml
│       └── normalizer_config_views.xml
├── plasticos_logistics
│   ├── BOL - DELIVERY-59422.pdf
│   ├── BOL - PICKUP-59422.pdf
│   ├── DELIVERY ORDER-59422.pdf
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── cron.xml
│   │   └── incoterms.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── dispatch.py
│   │   ├── load.py
│   │   ├── rate_memory.py
│   │   ├── sale_order_inherit.py
│   │   └── transaction_inherit.py
│   ├── report
│   │   ├── load_reports.xml
│   │   ├── report_bol_delivery.xml
│   │   ├── report_bol_pickup.xml
│   │   └── report_delivery_order.xml
│   ├── security
│   │   └── ir.model.access.csv
│   ├── services
│   │   ├── escalation_engine.py
│   │   ├── init.py
│   │   ├── rate_engine.py
│   │   └── state_machine.py
│   ├── views
│   │   ├── load_bulk_update_wizard_views.xml
│   │   ├── load_ux.xml
│   │   ├── load_views.xml
│   │   ├── sale_order_button.xml
│   │   └── transaction_load_views.xml
│   └── wizards
│       ├── __init__.py
│       └── load_bulk_update_wizard.py
├── plasticos_matching
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── migrations
│   │   └── 19.0.1.0.1
│   │       └── pre-migrate.py
│   ├── models
│   │   ├── __init__.py
│   │   └── match_result.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       └── match_result_views.xml
├── plasticos_material_profile
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── form_codes.py
│   ├── data
│   │   ├── filler_type_data.xml
│   │   ├── material_attribute_data.xml
│   │   ├── material_color_data.xml
│   │   ├── material_form_data.xml
│   │   ├── packaging_type_data.xml
│   │   ├── polymer_data.xml
│   │   ├── process_type_data.xml
│   │   └── source_type_data.xml
│   ├── models
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
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       ├── material_color_views.xml
│       ├── material_form_views.xml
│       ├── material_profile_ux.xml
│       ├── material_profile_views.xml
│       ├── partner_material_ux.xml
│       ├── polymer_views.xml
│       ├── process_type_views.xml
│       └── source_type_views.xml
├── plasticos_offer
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── TODO
│   │   ├── Offer_Drafting_Agent_v4.0.md
│   │   ├── Offer_Response_Agent_v4.0.md
│   │   └── gap analysis.md
│   ├── data
│   │   └── offer_cron.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── intake_offers_bridge.py
│   │   └── offer.py
│   ├── security
│   │   └── ir.model.access.csv
│   ├── views
│   │   ├── intake_offers_bridge_views.xml
│   │   ├── offer_bulk_action_wizard_views.xml
│   │   ├── offer_ux.xml
│   │   └── offer_views.xml
│   └── wizards
│       ├── __init__.py
│       └── offer_bulk_action_wizard.py
├── plasticos_order_lines
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── purchase_order_line.py
│   │   └── sale_order_line.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       ├── purchase_order_views.xml
│       └── sale_order_views.xml
├── plasticos_partner_import
│   ├── 1. Counterparties - Parent - CORPORATE-Ready To Import.csv
│   ├── 2. Counterparties - Child - FACILITY LOCATIONS.csv
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models
│   │   ├── __init__.py
│   │   ├── crm_lead_import_service.py
│   │   ├── partner_import_service.py
│   │   └── validation.py
│   ├── scripts
│   │   └── run_import.py
│   ├── security
│   │   └── ir.model.access.csv
│   ├── views
│   │   ├── partner_bulk_update_wizard_views.xml
│   │   └── partner_import_wizard_views.xml
│   └── wizards
│       ├── __init__.py
│       ├── partner_bulk_update_wizard.py
│       └── partner_import_wizard.py
├── plasticos_product
│   ├── README.md
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── hooks.py
│   ├── data
│   │   ├── product_category_data.xml
│   │   └── product_data.xml
│   ├── models
│   │   ├── __init__.py
│   │   └── product_template.py
│   ├── security
│   │   └── ir.model.access.csv
│   └── views
│       └── polymer_views.xml
├── plasticos_security_base
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models
│   │   ├── __init__.py
│   │   └── res_partner.py
│   ├── security
│   │   ├── ir.model.access.csv
│   │   ├── record_rules.xml
│   │   └── security_groups.xml
│   └── views
│       └── res_partner_views.xml
├── plasticos_transaction
│   ├── GUIDE.md
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── cieTrade.WksDetail.csv
│   ├── hooks.py
│   ├── data
│   │   ├── audit_cron.xml
│   │   ├── cron_missing_docs.xml
│   │   ├── res.groups.csv
│   │   └── sequence.xml
│   ├── migrations
│   │   └── 1.1.0
│   │       ├── post-migrate.py
│   │       └── pre-migrate.py
│   ├── models
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
│   ├── scripts
│   │   └── run_transaction_import.py
│   ├── security
│   │   ├── commission_acl.xml
│   │   ├── ir.model.access.csv
│   │   └── security_hardening.xml
│   ├── tests
│   │   ├── __init__.py
│   │   └── test_weight_reconciliation.py
│   ├── views
│   │   ├── commission_views.xml
│   │   ├── intake_bridge_views.xml
│   │   ├── match_result_bridge_views.xml
│   │   ├── offer_bridge_views.xml
│   │   ├── partner_bridge_views.xml
│   │   ├── transaction_bridge_views.xml
│   │   ├── transaction_bulk_assign_wizard_views.xml
│   │   ├── transaction_bulk_update_wizard_views.xml
│   │   ├── transaction_docs_views.xml
│   │   ├── transaction_import_wizard_views.xml
│   │   ├── transaction_ux.xml
│   │   └── transaction_views.xml
│   └── wizards
│       ├── __init__.py
│       ├── transaction_bulk_assign_wizard.py
│       ├── transaction_bulk_update_wizard.py
│       └── transaction_import_wizard.py
├── plasticos_web_leads
│   ├── README.md
│   ├── README.rst
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── controllers
│   │   ├── __init__.py
│   │   └── web_lead_api.py
│   ├── data
│   │   ├── logistics_ir_rules.xml
│   │   └── web_lead_config_data.xml
│   ├── models
│   │   ├── __init__.py
│   │   ├── ai_normalizer.py
│   │   ├── classification_engine.py
│   │   ├── image_analyzer.py
│   │   ├── web_lead.py
│   │   ├── web_lead_bridge.py
│   │   └── web_lead_config.py
│   ├── security
│   │   └── ir.model.access.csv
│   ├── views
│   │   ├── lead_bulk_action_wizard_views.xml
│   │   ├── web_lead_bridge_views.xml
│   │   ├── web_lead_config_views.xml
│   │   ├── web_lead_ux.xml
│   │   └── web_lead_views.xml
│   └── wizards
│       ├── __init__.py
│       └── lead_bulk_action_wizard.py
├── reports
│   ├── BUG_FIXES_SUMMARY.md
│   ├── GAP_ANALYSIS_AND_CONSOLIDATION.md
│   ├── GMP-Report-KB-v8.0-Wiring.md
│   ├── README-PIPELINE-AUDIT-2026-02-24.md
│   ├── cron_hardening_report.md
│   ├── csv_schema_index.json
│   ├── repo_spec.md
│   └── repo-index
│       ├── README_ODOO_INDEX.md
│       ├── odoo_ai_agent_files.md
│       ├── odoo_dependency_order.md
│       ├── odoo_external_id_registry.md
│       ├── odoo_model_index.md
│       └── repo-index-json
│           ├── odoo_ai_agent_files.json
│           ├── odoo_compliance_scan.json
│           ├── odoo_dependency_graph.json
│           ├── odoo_external_id_registry.json
│           ├── odoo_migrations.json
│           ├── odoo_model_index.json
│           ├── odoo_test_catalog.json
│           ├── odoo_transaction_spine.json
│           └── odoo_xml_index.json
├── scripts
│   ├── check_module_wiring.py
│   ├── check_module_wiring.sh
│   ├── check_odoo_patterns.sh
│   ├── get_odoo_module_order.py
│   ├── rebuild-odoo-no-demo.sh
│   ├── setup_neo4j.sh
│   └── validate_manifest.py
├── tests
│   ├── test_cron_invariants.py
│   ├── test_form_enum_alignment.py
│   ├── test_phantom_enum_values.py
│   ├── test_process_enum_alignment.py
│   └── modules
│       ├── test_cypher_schema_alignment.py
│       ├── test_plasticos_buyer_match_engine.py
│       └── test_repo_dependency_integrity.py
└── tools
    └── cron_invariant_check.py

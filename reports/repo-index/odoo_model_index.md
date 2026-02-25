# Odoo Model Index

## plasticos_enrichment :: plasticos.enrichment.provenance
- **file:** `plasticos_enrichment/models/enrichment_provenance.py`
- **inherit:** None
- **fields:** 12
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_enrichment :: plasticos.enrichment.source
- **file:** `plasticos_enrichment/models/enrichment_source.py`
- **inherit:** None
- **fields:** 9
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_enrichment :: plasticos.enrichment.run
- **file:** `plasticos_enrichment/models/enrichment_run.py`
- **inherit:** ['mail.thread']
- **fields:** 12
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_enrichment :: plasticos.enrichment.extraction
- **file:** `plasticos_enrichment/models/enrichment_extraction.py`
- **inherit:** None
- **fields:** 9
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_enrichment :: None
- **file:** `plasticos_enrichment/models/res_partner.py`
- **inherit:** ['res.partner']
- **fields:** 2
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_enrichment :: plasticos.enrichment.service
- **file:** `plasticos_enrichment/models/enrichment_service.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: plasticos.audit.cron
- **file:** `plasticos_transaction/models/audit_cron.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: None
- **file:** `plasticos_transaction/models/res_users_inherit.py`
- **inherit:** ['res.users']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: plasticos.transaction
- **file:** `plasticos_transaction/models/transaction.py`
- **inherit:** ['mail.thread']
- **fields:** 51
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: None
- **file:** `plasticos_transaction/models/sale_inherit.py`
- **inherit:** ['sale.order']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: plasticos.transaction.line
- **file:** `plasticos_transaction/models/transaction_line.py`
- **inherit:** None
- **fields:** 23
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: plasticos.transaction.import.service
- **file:** `plasticos_transaction/models/transaction_import_service.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: None
- **file:** `plasticos_transaction/models/purchase_inherit.py`
- **inherit:** ['purchase.order']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: plasticos.commission.rule
- **file:** `plasticos_transaction/models/commission_rule.py`
- **inherit:** None
- **fields:** 4
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: None
- **file:** `plasticos_transaction/models/load_inherit.py`
- **inherit:** ['plasticos.load']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: plasticos.commission.service
- **file:** `plasticos_transaction/models/commission_service.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_transaction :: None
- **file:** `plasticos_transaction/models/account_move_inherit.py`
- **inherit:** ['account.move']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_partner_import :: plasticos.partner.import.service
- **file:** `plasticos_partner_import/models/partner_import_service.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_partner_import :: plasticos.partner.import.validation
- **file:** `plasticos_partner_import/models/validation.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_logistics :: plasticos.dispatch
- **file:** `plasticos_logistics/models/dispatch.py`
- **inherit:** None
- **fields:** 2
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_logistics :: None
- **file:** `plasticos_logistics/models/sale_order_inherit.py`
- **inherit:** ['sale.order']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_logistics :: plasticos.rate.memory
- **file:** `plasticos_logistics/models/rate_memory.py`
- **inherit:** None
- **fields:** 4
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_logistics :: plasticos.load
- **file:** `plasticos_logistics/models/load.py`
- **inherit:** ['mail.thread']
- **fields:** 43
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_facility_profile :: plasticos.facility.profile
- **file:** `plasticos_facility_profile/models/facility_profile.py`
- **inherit:** ['mail.thread']
- **fields:** 45
- **constraints:** @api.constrains=['partner_id', 'density_min', 'density_max', 'melt_index_min', 'melt_index_max'] _sql=[] models.Constraint=[]

## plasticos_facility_profile :: plasticos.partner.type
- **file:** `plasticos_facility_profile/models/partner_type.py`
- **inherit:** None
- **fields:** 7
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_facility_profile :: plasticos.equipment.type
- **file:** `plasticos_facility_profile/models/equipment_type.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_facility_profile :: None
- **file:** `plasticos_facility_profile/models/res_partner.py`
- **inherit:** ['res.partner']
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_geolocalize :: None
- **file:** `plasticos_geolocalize/models/res_partner_geo.py`
- **inherit:** ['res.partner']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_geolocalize :: None
- **file:** `plasticos_geolocalize/models/intake_geo.py`
- **inherit:** ['plasticos.intake']
- **fields:** 2
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: plasticos.document.validation.matrix
- **file:** `plasticos_documents/models/document_validation_matrix.py`
- **inherit:** None
- **fields:** 8
- **constraints:** @api.constrains=['doc_category', 'tag_id'] _sql=[] models.Constraint=[]

## plasticos_documents :: None
- **file:** `plasticos_documents/models/transaction_docs.py`
- **inherit:** ['plasticos.transaction']
- **fields:** 6
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: None
- **file:** `plasticos_documents/models/document_rule_extension.py`
- **inherit:** ['plasticos.document.rule']
- **fields:** 4
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: plasticos.document.tag
- **file:** `plasticos_documents/models/document_tag.py`
- **inherit:** None
- **fields:** 3
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: None
- **file:** `plasticos_documents/models/document_extension.py`
- **inherit:** ['plasticos.document']
- **fields:** 7
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: plasticos.compliance.service
- **file:** `plasticos_documents/models/compliance_service.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: plasticos.document
- **file:** `plasticos_documents/models/document.py`
- **inherit:** ['mail.thread']
- **fields:** 11
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents :: plasticos.document.rule
- **file:** `plasticos_documents/models/document_rule.py`
- **inherit:** None
- **fields:** 7
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_web_leads :: plasticos.web.lead.config
- **file:** `plasticos_web_leads/models/web_lead_config.py`
- **inherit:** None
- **fields:** 15
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_web_leads :: plasticos.web.lead
- **file:** `plasticos_web_leads/models/web_lead.py`
- **inherit:** ['mail.thread']
- **fields:** 26
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/sale_approval.py`
- **inherit:** ['sale.order']
- **fields:** 2
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/stock_picking_automation.py`
- **inherit:** ['stock.picking']
- **fields:** 4
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/purchase_order_automation.py`
- **inherit:** ['purchase.order']
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/stock_reorder_alert.py`
- **inherit:** ['product.product']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: plasticos.automation.config
- **file:** `plasticos_automation/models/automation_config.py`
- **inherit:** None
- **fields:** 6
- **constraints:** @api.constrains=['active', 'sale_approval_threshold', 'invoice_overdue_days', 'contract_alert_days_before', 'stock_threshold_default', ''] _sql=[] models.Constraint=[]

## plasticos_automation :: plasticos.automation.log
- **file:** `plasticos_automation/models/automation_log.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/sale_order_automation.py`
- **inherit:** ['sale.order']
- **fields:** 3
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/load_automation.py`
- **inherit:** ['plasticos.load']
- **fields:** 2
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/contract_renewal.py`
- **inherit:** ['res.partner']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_automation :: None
- **file:** `plasticos_automation/models/invoice_reminder.py`
- **inherit:** ['account.move']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_security_base :: None
- **file:** `plasticos_security_base/models/res_partner.py`
- **inherit:** ['res.partner']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_intake_normalizer :: plasticos.normalizer.config
- **file:** `plasticos_intake_normalizer/models/normalizer_config.py`
- **inherit:** None
- **fields:** 9
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_intake_normalizer :: None
- **file:** `plasticos_intake_normalizer/models/intake_normalizer.py`
- **inherit:** ['plasticos.intake']
- **fields:** 9
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_offer :: plasticos.offer
- **file:** `plasticos_offer/models/offer.py`
- **inherit:** ['mail.thread', 'mail.activity.mixin']
- **fields:** 21
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.filler.type
- **file:** `plasticos_material_profile/models/filler_type.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.material.profile
- **file:** `plasticos_material_profile/models/material_profile.py`
- **inherit:** ['mail.thread']
- **fields:** 41
- **constraints:** @api.constrains=['partner_id'] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.process.type
- **file:** `plasticos_material_profile/models/process_type.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.source.type
- **file:** `plasticos_material_profile/models/source_type.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.material.attribute
- **file:** `plasticos_material_profile/models/material_attribute.py`
- **inherit:** None
- **fields:** 7
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.packaging.type
- **file:** `plasticos_material_profile/models/packaging_type.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.material.form
- **file:** `plasticos_material_profile/models/material_form.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.polymer
- **file:** `plasticos_material_profile/models/polymer.py`
- **inherit:** None
- **fields:** 7
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: None
- **file:** `plasticos_material_profile/models/res_partner.py`
- **inherit:** ['res.partner']
- **fields:** 3
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_material_profile :: plasticos.material.color
- **file:** `plasticos_material_profile/models/material_color.py`
- **inherit:** None
- **fields:** 5
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: None
- **file:** `plasticos_buyer_match_engine/models/intake_extension.py`
- **inherit:** ['plasticos.intake']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: plasticos.buyer.matcher
- **file:** `plasticos_buyer_match_engine/models/matcher.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: plasticos.graph.service
- **file:** `plasticos_buyer_match_engine/models/graph_service.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: plasticos.graph.sync.log
- **file:** `plasticos_buyer_match_engine/models/graph_sync_log.py`
- **inherit:** None
- **fields:** 7
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: None
- **file:** `plasticos_buyer_match_engine/models/facility_profile_graph_hooks.py`
- **inherit:** ['res.partner']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: plasticos.match.exclusion
- **file:** `plasticos_buyer_match_engine/models/match_exclusion.py`
- **inherit:** ['mail.thread']
- **fields:** 8
- **constraints:** @api.constrains=['exclusion_type', 'expiry_date', 'supplier_partner_id', 'buyer_partner_id'] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: None
- **file:** `plasticos_buyer_match_engine/models/intake_graph_hooks.py`
- **inherit:** ['plasticos.intake']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_buyer_match_engine :: None
- **file:** `plasticos_buyer_match_engine/models/material_profile_graph_hooks.py`
- **inherit:** ['plasticos.material.profile']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_order_lines :: None
- **file:** `plasticos_order_lines/models/purchase_order_line.py`
- **inherit:** ['purchase.order.line']
- **fields:** 8
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_order_lines :: None
- **file:** `plasticos_order_lines/models/sale_order_line.py`
- **inherit:** ['sale.order.line']
- **fields:** 8
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_claims :: plasticos.claim
- **file:** `plasticos_claims/models/claim.py`
- **inherit:** ['mail.thread', 'mail.activity.mixin']
- **fields:** 28
- **constraints:** @api.constrains=['state', 'resolution_note'] _sql=[] models.Constraint=[]

## plasticos_claims :: None
- **file:** `plasticos_claims/models/document_inherit.py`
- **inherit:** ['plasticos.document']
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_intake :: plasticos.intake
- **file:** `plasticos_intake/models/intake.py`
- **inherit:** ['mail.thread', 'mail.activity.mixin']
- **fields:** 47
- **constraints:** @api.constrains=['quantity_per_load_lbs', 'loads_per_month'] _sql=[] models.Constraint=[]

## plasticos_intake :: None
- **file:** `plasticos_intake/models/res_partner_intake.py`
- **inherit:** ['res.partner']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_intake :: plasticos.intake.match
- **file:** `plasticos_intake/models/intake_match.py`
- **inherit:** None
- **fields:** 9
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_intake :: None
- **file:** `plasticos_intake/models/material_profile_intake.py`
- **inherit:** ['plasticos.material.profile']
- **fields:** 1
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_product :: None
- **file:** `plasticos_product/models/product_template.py`
- **inherit:** ['product.template']
- **fields:** 3
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents_native :: None
- **file:** `plasticos_documents_native/models/document_native.py`
- **inherit:** ['documents.document']
- **fields:** 11
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_documents_native :: plasticos.document.sync
- **file:** `plasticos_documents_native/models/document_sync.py`
- **inherit:** None
- **fields:** 0
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

## plasticos_matching :: plasticos.match.result
- **file:** `plasticos_matching/models/match_result.py`
- **inherit:** ['mail.thread']
- **fields:** 19
- **constraints:** @api.constrains=[] _sql=[] models.Constraint=[]

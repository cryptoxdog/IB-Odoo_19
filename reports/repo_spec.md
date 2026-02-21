# ============================================================================
# PlasticOS Odoo 19 Repository Specification
# ============================================================================
# Dense YAML spec for agent onboarding. Assumes access to reports/ folder.
# Generated: 2026-02-18
# ============================================================================

meta:
  name: Odoo_19_ReBoot
  purpose: Plastics recycling brokerage ERP on Odoo 19 Community
  domain: B2B plastics scrap trading (post-industrial/post-consumer)
  company: Scrap Management Inc
  status: active_development

# ============================================================================
# MODULE ARCHITECTURE
# ============================================================================

modules:
  # --- CORE TRANSACTION SPINE ---
  plasticos_transaction:
    version: "19.0.1.1.0"
    purpose: Central transaction lifecycle (sale→purchase→invoice→close)
    models:
      - plasticos.transaction        # Main spine record
      - plasticos.transaction.line   # cieTrade historical line items
      - plasticos.audit.cron         # Monthly audit job
    key_fields:
      transaction:
        - name                       # TRX-YYYY-NNNNNN sequence
        - sale_order_id              # M2O sale.order
        - purchase_order_ids         # M2M purchase.order
        - load_id                    # M2O plasticos.load
        - customer_invoice_id        # M2O account.move (out_invoice)
        - vendor_bill_ids            # M2M account.move (in_invoice)
        - freight_bill_ids           # M2M account.move (in_invoice)
        - line_ids                   # O2M transaction.line (historical)
        - commission_rule_id         # M2O plasticos.commission.rule
        - state                      # draft→active→closed
      transaction_line:
        - detail_id                  # cieTrade DetailID
        - grade_id                   # Material grade code
        - sale_weight / purchase_weight
        - sale_amount / purchase_amount
        - weight_uom                 # L=lbs, S=short tons, E=each
        - unit_type                  # B=bale, G=gaylord, X=box, etc.
    depends:
      - plasticos_logistics
      - plasticos_documents
      - plasticos_commission
      - plasticos_material_profile
      - plasticos_facility_profile
      - plasticos_intake
    security_groups:
      - group_plasticos_manager      # Required for action_close()
    constraints:
      - Closed transactions immutable
      - Commission locked on close
      - Customer invoice required for close
      - Negative margin blocks close

  # --- LOGISTICS ENGINE ---
  plasticos_logistics:
    version: "19.0.1.0.0"
    purpose: Load dispatch, carrier rates, BOL tracking
    models:
      - plasticos.load               # Shipment record
      - plasticos.dispatch           # Dispatch assignment
      - plasticos.rate.memory        # Historical rate cache
    key_fields:
      load:
        - sale_order_id              # M2O sale.order (required)
        - carrier_id                 # M2O res.partner
        - rate_amount / rate_confirmed_at
        - pickup_datetime / delivery_datetime
        - bol_pickup_attached / bol_delivery_attached
        - state                      # draft→awaiting_ready→...→closed
    state_machine:
      - draft → awaiting_ready → ready_confirmed → rate_confirmed
      - rate_confirmed → scheduled → dispatched → picked_up → delivered → closed
      - any → exception

  # --- DOCUMENT COMPLIANCE ---
  plasticos_documents:
    version: "19.0.1.0.0"
    purpose: Document rules, verification, compliance gates
    models:
      - plasticos.document           # Attached document record
      - plasticos.document.tag       # Document type taxonomy
      - plasticos.document.rule      # Required docs per model/client
      - plasticos.compliance.service # Compliance check logic
    key_fields:
      document:
        - res_model / res_id         # Polymorphic attachment
        - attachment_id              # M2O ir.attachment
        - tag_id                     # M2O document.tag
        - verified / override        # Verification state
    security_groups:
      - group_documents_user
      - group_documents_manager      # Override permission

  # --- COMMISSION ENGINE ---
  plasticos_commission:
    version: "19.0.1.0.0"
    purpose: Sales rep commission rules and calculation
    models:
      - plasticos.commission.rule    # Rule definition
      - plasticos.commission.service # Calculation service
    key_fields:
      rule:
        - sales_rep_id               # M2O res.users
        - percentage                 # Commission rate

  # --- MATERIAL INTAKE ---
  plasticos_intake:
    version: "19.0.1.0.0"
    purpose: Raw material intake, normalization, buyer matching
    models:
      - plasticos.intake             # Intake record
    key_fields:
      - partner_id / facility_id     # Source partner
      - polymer / form / color       # Material identity
      - mfi_value / density_value    # Quality metrics
      - quantity_per_load_lbs        # Volume
      - match_status                 # pending→normalized→matched
      - normalized                   # Gate for packet emission

  # --- PARTNER PROFILES ---
  plasticos_material_profile:
    version: "19.0.1.0.0"
    purpose: Material identity profiles per facility
    models:
      - plasticos.material.profile   # Material capability record
    extends: res.partner             # Adds material_profile_ids O2M
    key_fields:
      - polymer                      # PP, HDPE, LDPE, PET, etc.
      - form                         # bale, regrind, flake, pellet
      - source_type                  # post_industrial, post_consumer
      - melt_flow_index / contamination_percent
      - monthly_volume_lbs

  plasticos_facility_profile:
    version: "19.0.1.0.0"
    purpose: Facility equipment and throughput capabilities
    models:
      - plasticos.facility.profile   # Capability record
    extends: res.partner             # Adds facility_profile_ids O2M, x_facility_role
    key_fields:
      - has_horizontal_baler / has_wash_line / has_granulator
      - max_monthly_throughput_lbs
      - handles_bales / handles_regrind / handles_pellet
      - iso_certified / food_grade_certified

  # --- SEED/IMPORT UTILITIES ---
  plasticos_foundation_seed:
    version: "19.0.1.0.0"
    purpose: Deterministic XML seed data
    seeds:
      - partner_tags.xml
      - payment_terms.xml
      - incoterms.xml
      - sales_reps.xml
      - accounts.xml
      - material_taxonomy.xml

  plasticos_partner_import:
    version: "19.0.1.1.0"
    purpose: Zero-click partner import pipeline
    models:
      - plasticos.partner.import.service  # AbstractModel wizard

# ============================================================================
# DATA SOURCES
# ============================================================================

data_sources:
  cieTrade_WksDetail:
    path: plasticos_transaction/cieTrade.WksDetail.csv
    rows: ~20000
    purpose: Historical transaction line items
    key_columns:
      - BuySellNo                    # Transaction reference (groups lines)
      - DetailID                     # Line item ID
      - GradeID                      # Material grade
      - SWeight / PWeight            # Sale/Purchase weight
      - SAmount / PAmount            # Sale/Purchase amount
      - SWeightUOM                   # L=lbs, S=short tons, E=each
      - UnitType                     # B=bale, G=gaylord, etc.
    import_service: plasticos.transaction.import.service

  csv_schema_index:
    path: reports/csv_schema_index.json
    purpose: Master reference data schema
    contains:
      - payment_terms                # Net 15, Net 30, COD, etc.
      - incoterms                    # FOB, SUPPLIER_DELIVERED, etc.
      - sales_reps                   # 6 reps with email/phone
      - chart_of_accounts            # Full COA (40000-80000)
      - material_taxonomy:
          polymers: [ABS, HDPE, LDPE, PP, PET, ...]
          forms: [BALE, FLAKE, PELL, REG, ...]
          source_types: [PI, PC, Clean, Mixed, ...]
      - colors                       # BLK, CLR, NAT, MIX, etc.
      - material_types               # CLEAN, DIRTY, PCR, PIR, etc.

# ============================================================================
# DEPENDENCY GRAPH (Install Order)
# ============================================================================

install_order:
  tier_0_odoo:
    - base
    - contacts
    - mail
    - account
    - sale_management
    - purchase
    - stock

  tier_1_independent:
    - plasticos_commission           # No plasticos deps
    - plasticos_documents            # No plasticos deps
    - plasticos_logistics            # No plasticos deps
    - plasticos_intake               # No plasticos deps

  tier_2_profiles:
    - plasticos_material_profile     # Depends: contacts, mail
    - plasticos_facility_profile     # Depends: contacts, mail, sale_management

  tier_3_spine:
    - plasticos_transaction          # Depends: ALL tier_1 + tier_2

  tier_4_utilities:
    - plasticos_partner_import       # Depends: facility_profile
    - plasticos_foundation_seed      # Seed data

# ============================================================================
# KEY PATTERNS
# ============================================================================

patterns:
  versioning: "{odoo_version}.{major}.{minor}.{patch}"  # e.g., 19.0.1.0.0

  model_naming:
    - plasticos.{domain}             # Main model
    - plasticos.{domain}.{sub}       # Sub-model

  field_conventions:
    - _ids suffix for O2M/M2M
    - _id suffix for M2O
    - x_ prefix for res.partner extensions

  state_machines:
    - All use Selection field named "state"
    - Transitions via action_* methods
    - Tracking enabled for audit

  security:
    - ir.model.access.csv per module
    - XML groups in security/*.xml
    - Manager groups for destructive ops

# ============================================================================
# CRITICAL CONSTRAINTS
# ============================================================================

constraints:
  transaction_close:
    - customer_invoice_id.state == "posted"
    - all vendor_bill_ids.state == "posted"
    - load_id.state == "closed" (if linked)
    - compliance_status == "compliant"
    - gross_margin >= 0
    - user in group_plasticos_manager

  immutability:
    - Closed transactions: protected fields locked
    - Commission locked: rule cannot change
    - Customer invoice: cannot reassign once set

  uniqueness:
    - Transaction name (sequence-generated)
    - Material profile: unique(partner_id, polymer, form) implied
    - Facility profile: unique(partner_id)

# ============================================================================
# DOCUMENTATION INDEX
# ============================================================================

docs:
  specs:
    - docs/docs/material-profile.md      # Material profile spec
    - docs/docs/facility-profile.md      # Facility capability spec
    - docs/docs/economic-profile.md      # Commercial profile spec
    - docs/docs/compliance_gate.md       # Compliance rules
    - docs/docs/commission_freeze.md     # Commission lock logic
    - docs/docs/lifecycle_diagram.md     # Transaction lifecycle

  procedures:
    - docs/docs/production_admin_playbook.md
    - docs/docs/audit_procedure.md

  import:
    - docs/docs/plasticos_partner_import.md
    - docs/migration-suite.md            # Test suite spec
    - docs/seed.md                       # Seed data spec

# ============================================================================
# AGENT QUICK REFERENCE
# ============================================================================

quick_ref:
  run_tests: "./run-odoo-tests.sh"

  import_transactions: |
    env["plasticos.transaction.import.service"].run_csv_import(
        "/path/to/cieTrade.WksDetail.csv",
        dry_run=False
    )

  close_transaction: |
    tx = env["plasticos.transaction"].browse(id)
    tx.action_close()  # Validates all constraints

  check_compliance: |
    svc = env["plasticos.compliance.service"]
    svc.is_compliant("plasticos.transaction", tx_id)

  compute_commission: |
    svc = env["plasticos.commission.service"]
    amount = svc.compute_commission(tx)

# ============================================================================
# KNOWN ISSUES / TECH DEBT
# ============================================================================

tech_debt:
  - L9 adapter stubs (l9_trace module not yet integrated)
  - Processing profile commented out in intake model
  - Some tests reference non-existent fixtures

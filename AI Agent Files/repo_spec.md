### File 5: repo_spec.yaml

```yaml
# repo_spec.yaml — PlasticOS Repository Specification
# Auto-generated from live code extraction: 2026-02-24

meta:
  repo: cryptoxdog/IB-Odoo_19
  branch: staging
  odoo_version: "19.0"
  python_version: "3.12"
  extraction_date: "2026-02-24"
  extraction_method: live_code_analysis

platform:
  framework: odoo
  version: "19.0"
  python_min: "3.10"
  python_recommended: "3.12"
  database: postgresql
  database_version: "15+"
  graph_database: neo4j
  graph_database_version: "5.0+"

architecture:
  pattern: layered_deterministic
  layers:
    - name: material
      level: 1
      modules:
        - plasticos_base
        - plasticos_material_profile
        - plasticos_intake
        - plasticos_product
    - name: capability
      level: 2
      modules:
        - plasticos_facility_profile
        - plasticos_matching
        - plasticos_buyer_match_engine
    - name: commercial
      level: 3
      modules:
        - plasticos_accounting
        - plasticos_offer
        - plasticos_automation
    - name: compliance
      level: 4
      modules:
        - plasticos_documents
        - plasticos_documents_native
        - plasticos_claims
    - name: transaction
      level: 5
      modules:
        - plasticos_logistics
        - plasticos_transaction
        - plasticos_order_lines

modules:
  total_count: 33
  active_count: 33
  deprecated_count: 0

  list:
    - name: plasticos_base
      version: "19.0.1.0.0"
      summary: "Core seed data: partner tags, sales reps, material taxonomy tags"
      category: Hidden
      application: false
      installable: true
      depends:
        - base
        - contacts
        - sale_management
      models: []
      seed_data:
        - data/partner_tags.xml
        - data/material_taxonomy.xml
        - data/sales_reps.xml

    - name: plasticos_material_profile
      version: "19.0.5.0.0"
      summary: "Canonical material master registries: polymer, form, color, source, process"
      category: Operations
      application: false
      installable: true
      depends:
        - base
        - contacts
        - mail
        - purchase
        - sale_management
        - product
      models:
        - plasticos.polymer
        - plasticos.material.form
        - plasticos.material.color
        - plasticos.source.type
        - plasticos.process.type
        - plasticos.material.profile
        - plasticos.filler.type
        - plasticos.material.attribute
        - plasticos.packaging.type

    - name: plasticos_facility_profile
      version: "19.0.3.0.0"
      summary: "Facility capability profiles — equipment, tolerances, and BCP fields"
      category: Hidden
      application: false
      installable: true
      depends:
        - base
        - contacts
        - mail
        - sale_management
        - plasticos_material_profile
      models:
        - plasticos.facility.profile
        - plasticos.equipment.type
        - plasticos.partner.type
      partner_extension:
        fields:
          - facility_profile_ids

    - name: plasticos_intake
      version: "19.0.5.0.0"
      summary: "Transactional Material Intake — contact intelligence, smart memory, UX normalization"
      category: Operations
      application: false
      installable: true
      depends:
        - base
        - contacts
        - mail
        - plasticos_material_profile
        - plasticos_facility_profile
      models:
        - plasticos.intake
        - plasticos.intake.match

    - name: plasticos_matching
      version: "19.0.1.0.0"
      summary: "Match result storage — L9 adapter populates, Odoo displays"
      category: Hidden
      application: false
      installable: true
      depends:
        - base
        - mail
        - plasticos_intake
        - plasticos_facility_profile
      models:
        - plasticos.match.result

    - name: plasticos_buyer_match_engine
      version: "19.0.2.0.0"
      summary: "Buyer matching v2.0: facility.profile-based, 10-gate filtering, Neo4j graph scoring"
      category: Plasticos/Matching
      application: false
      installable: true
      depends:
        - plasticos_intake
        - plasticos_material_profile
        - plasticos_matching
        - plasticos_facility_profile
        - plasticos_transaction
      external_dependencies:
        python:
          - neo4j
      models:
        - plasticos.match.exclusion
      services:
        - services/graph_service.py
        - services/matcher.py

    - name: plasticos_logistics
      version: "19.0.1.0.0"
      summary: "Load management and dispatch"
      category: Operations
      application: false
      installable: true
      depends:
        - sale_management
        - stock
        - mail
      models:
        - plasticos.load
      reports:
        - report/report_bol_pickup.xml
        - report/report_bol_delivery.xml
        - report/report_delivery_order.xml

    - name: plasticos_transaction
      version: "19.0.2.0.0"
      summary: "Core transaction lifecycle management with integrated commission engine"
      category: Operations
      application: false
      installable: true
      depends:
        - base
        - mail
        - product
        - account
        - sale_management
        - purchase
        - plasticos_logistics
        - plasticos_material_profile
        - plasticos_facility_profile
        - plasticos_intake
        - plasticos_product
      models:
        - plasticos.transaction
        - plasticos.commission
        - plasticos.transaction.bulk.update.wizard
        - plasticos.transaction.bulk.assign.wizard
        - plasticos.transaction.import.wizard

    - name: plasticos_documents
      version: "19.0.2.0.0"
      summary: "Document management, compliance, validation matrix, and transaction doc tracking"
      category: Operations
      application: false
      installable: true
      depends:
        - base
        - mail
        - plasticos_transaction
      models:
        - plasticos.document
        - plasticos.document.tag
        - plasticos.document.rule
        - plasticos.document.extension
        - plasticos.validation.matrix
        - plasticos.transaction.docs

    - name: plasticos_web_leads
      version: "19.0.2.0.0"
      summary: "AI-powered web lead triage: Cognito → LLM/Vision → HOT/COLD → Intake"
      category: Operations
      application: false
      installable: true
      depends:
        - base
        - mail
        - plasticos_intake
        - plasticos_material_profile
        - purchase
      external_dependencies:
        python:
          - openai
          - requests
      models:
        - plasticos.web.lead
        - plasticos.web.lead.config
        - plasticos.lead.bulk.action.wizard

    - name: plasticos_accounting
      version: "19.0.1.0.0"
      summary: "Accounting seed data: payment terms, chart of accounts, incoterms"
      category: Accounting/Accounting
      application: false
      installable: true
      depends:
        - account
      models: []
      seed_data:
        - data/payment_terms.xml
        - data/accounts.xml

    - name: plasticos_automation
      version: "19.0.2.0.0"
      summary: "Deterministic workflow automation: approvals, reminders, logistics follow-ups, SLA monitoring"
      category: Operations
      application: false
      installable: true
      depends:
        - base
        - base_automation
        - mail
        - product
        - sale_management
        - account
        - stock
        - purchase
        - plasticos_logistics
        - plasticos_transaction
        - plasticos_claims
      models:
        - plasticos.automation.config
        - plasticos.automation.log

external_dependencies:
  python:
    - name: neo4j
      version: ">=5.0.0"
      modules:
        - plasticos_buyer_match_engine
    - name: openai
      version: ">=1.0.0"
      modules:
        - plasticos_web_leads
    - name: requests
      version: ">=2.28.0"
      modules:
        - plasticos_web_leads

environment_variables:
  required:
    - name: POSTGRES_USER
      description: "PostgreSQL database user"
      default: odoo
    - name: POSTGRES_PASSWORD
      description: "PostgreSQL database password"
      default: null
    - name: POSTGRES_DB
      description: "PostgreSQL database name"
      default: odoo
    - name: NEO4J_URI
      description: "Neo4j connection URI"
      default: "bolt://localhost:7687"
    - name: NEO4J_USER
      description: "Neo4j username"
      default: neo4j
    - name: NEO4J_PASSWORD
      description: "Neo4j password"
      default: null
  optional:
    - name: OPENAI_API_KEY
      description: "OpenAI API key for web lead triage"
      default: null
    - name: ODOO_DB_HOST
      description: "Database host"
      default: db
    - name: ODOO_DB_PORT
      description: "Database port"
      default: "5432"
    - name: ODOO_REBUILD_MODULES
      description: "Comma-separated module list for rebuild script"
      default: null
    - name: ODOO_TEST_MODULES
      description: "Comma-separated module list for test script"
      default: null

testing:
  test_database: odoo_test
  test_count: 52
  passing: 52
  failing: 0
  coverage:
    plasticos_transaction: 47
    plasticos_buyer_match_engine: 5
  disabled_for_ci:
    - plasticos_enrichment
    - plasticos_dev_tools
  test_command: "./scripts/run-odoo-tests.sh"

ci_cd:
  pre_commit:
    enabled: true
    hooks:
      - ruff
      - ruff-format
      - check-xml
      - check-yaml
      - odoo-patterns
      - module-wiring
  github_actions:
    enabled: false
  odoo_sh_ci:
    enabled: true
    auto_test: true

compliance:
  odoo_19_patterns:
    enforced: true
    forbidden:
      - _sql_constraints
      - "@api.depends('id')"
      - "@api.one"
      - "@api.multi"
      - "category_id on res.groups"
      - "numbercall on ir.cron"
  namespace:
    required_prefix: plasticos_
    forbidden_prefixes:
      - plastos_
      - plast_

security:
  rbac:
    enabled: true
    base_module: plasticos_security_base
  acl_required: true
  record_rules_required: true
  multi_company_isolation: true

deployment:
  docker:
    dockerfile: Dockerfile
    base_image: "odoo:19"
    python_version: "3.12"
  odoo_sh:
    supported: true
    requirements_file: requirements.txt
  staging_branch: staging
  production_branch: main
```

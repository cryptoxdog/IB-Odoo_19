# CHANGELOG.md — PlasticOS Release History

**Repository**: cryptoxdog/IB-Odoo_19
**Odoo Version**: 19.0

All notable changes to PlasticOS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Complete documentation suite (ARCHITECTURE.md, API_REFERENCE.md, etc.)
- Production-ready Docker deployment configuration
- Neo4j setup automation script (`setup_neo4j.sh`)

---

## [2.0.0] - 2026-02-24

### Breaking Changes
- **Two-stage buyer matching**: Capability Matcher (Python) runs before Graph Service (Cypher)
- **Lazy partner creation**: Web leads create intakes without partners; partner created on match
- **Removed plasticos_graph duplicate**: Consolidated into plasticos_buyer_match_engine

### Added
- **plasticos_buyer_match_engine**: Two-stage orchestrator (`match_buyers_two_stage`)
- **plasticos_intake**: `pending_company_name`, `source_lead_id` for lazy partner creation
- **plasticos_intake**: Form equipment logic (has_granulator → can accept bales)
- **plasticos_facility_profile**: Boolean field matrix for equipment capabilities
- **plasticos_web_leads**: HOT intake triggers admin activity notification
- **Security**: Check #21 in `check_odoo_patterns.sh` (detects Many2one string writes)

### Fixed
- **BUG-073**: Fixed string writes to Many2one fields in web_lead.py (polymer_id, form_id, source_type_id)
- **BUG-074**: Added missing `deal_type` Selection field to intake.py
- **BUG-075**: Changed `polymer_id` and `form_id` to `required=False` for web lead intakes
- **BUG-079**: Fixed Cypher query typo `tx.count` → `tx.tx_count` in graph_service.py
- **BUG-048 to BUG-056**: Audit fixes (singletons, cron expiry, state guards, etc.)
- **BUG-A**: Synced Selection fields with seed data (polymer, color, source_type)

### Changed
- **plasticos_material_profile**: Removed legacy product.template extension fields
- **plasticos_web_leads**: Intake creation no longer auto-creates partners (pending review)
- **plasticos_enrichment**: Improved polymer code mapping for POLYMER_NORMALIZE

### Documentation
- Added CYPHER_BUYER_MATCH_LOGIC.md
- Added BOOLEAN_FIELD_MATRIX.md
- Added GAP_ANALYSIS_45_STEP_FRAMEWORK.md
- Updated workflow_state.md (Session 5 progress)

---

## [1.5.0] - 2026-02-23

### Added
- **plasticos_buyer_match_engine**: PVC hard gate (`pvc_tolerant` field)
- **plasticos_facility_profile**: Form handling equipment fields (`has_granulator`, `has_shredder`, `has_extruder`, `has_baler`)
- **plasticos_material_profile**: Filler type and material attribute seed data sync
- **CI/CD**: Disabled tests requiring seed data for Odoo.sh deployment

### Fixed
- **Match result views**: Corrected field names (removed erroneous `l9_` prefix)
- **Material profile**: Synced Selection fields with seed data XMLs (added 'mixed', 'pp_pe', 'print')
- **Material profile**: Added 'film' record to material_form_data.xml
- **Enrichment**: Fixed polymer code mapping for special cases (HMW HDPE → hdpe_hmw, PA → nylon)
- **Product template**: Corrected related field types (Char → Selection for polymer/form)
- **Material profile**: Fail loudly when plasticos_order_lines missing (ValidationError instead of silent close)
- **Material profile**: Guard order line fields for optional dependency (hasattr checks)

### Changed
- **plasticos_documents**: Removed duplicate validation_matrix.py
- **plasticos_transaction**: Added denormalized `buyer_facility_id` and `supplier_material_id`
- **plasticos_product**: Populated empty ACL CSV with standard access rules

### Removed
- Circular dependency: plasticos_material_profile no longer depends on plasticos_intake

---

## [1.0.0] - 2026-02-23

### Added
- **Core modules** (93 modules total):
  - `plasticos_base`: Taxonomy, partner tags, sales reps
  - `plasticos_security_base`: RBAC groups and record rules
  - `plasticos_material_profile`: Polymer, form, color, filler master data
  - `plasticos_facility_profile`: Equipment types, partner types
  - `plasticos_intake`: Intake management with normalizer
  - `plasticos_buyer_match_engine`: Neo4j graph-based matching
  - `plasticos_transaction`: Commission tracking, cieTrade import
  - `plasticos_logistics`: Load management, BOL generation
  - `plasticos_offer`: Offer lifecycle with expiry cron
  - `plasticos_documents`: Compliance document validation
  - `plasticos_web_leads`: AI triage with GPT-4o
  - `plasticos_automation`: Cron jobs and workflow automations
  - `plasticos_claims`: Claim management with email templates

- **Testing infrastructure**:
  - 52 passing tests (`plasticos_transaction`, `plasticos_buyer_match_engine`)
  - Test scripts: `run-odoo-tests.sh`, `rebuild-odoo-modules.sh`
  - CI/CD integration for Odoo.sh

- **Development tools**:
  - `check_odoo_patterns.sh`: 20+ anti-pattern checks
  - `check_module_wiring.py`: Module integrity audits
  - `setup_neo4j.sh`: Neo4j automation

- **Documentation**:
  - README.md with quick start guide
  - GUIDE.md for transaction module
  - Module-specific READMEs

### Fixed
- **Registry errors**: Resolved module install errors for Odoo 19 compatibility
- **Search view syntax**: Removed deprecated Odoo 18 patterns
- **Circular dependencies**: Removed plasticos_material_profile → plasticos_intake
- **MRO conflicts**: Documented sale.order.action_confirm override chain
- **Email safety**: Null fallback for trucker name in templates
- **Cron defaults**: All automation crons inactive by default

### Changed
- **Partner model**: Added `is_facility` computed field
- **Polymer views**: Group by category by default
- **Module order**: Enforced via odoo_module_order.yaml

---

## [0.9.0] - 2026-02-20

### Added
- Initial commit with 90+ modules
- Basic transaction flow (intake → match → offer → transaction → load)
- Neo4j integration for buyer matching
- cieTrade CSV import wizard
- Material profile with polymer/form/color master data

### Known Issues
- Circular dependencies (plasticos_material_profile ↔ plasticos_intake)
- Some tests disabled (require seed data)
- Neo4j optional (Python fallback available)

---

## Version Numbering

**Format**: `<odoo_version>.<major>.<minor>.<patch>`

**Example**: `19.0.2.1.5`
- `19.0` = Odoo version
- `2` = Major (breaking changes)
- `1` = Minor (new features, backward compatible)
- `5` = Patch (bug fixes only)

**Migration Required**:
- Major version change (e.g., 1.x → 2.x)
- Odoo version change (e.g., 18.0 → 19.0)

**No Migration Required**:
- Minor version change (e.g., 1.0.x → 1.1.x)
- Patch version change (e.g., 1.0.0 → 1.0.1)

---

## Links

- **Repository**: [cryptoxdog/IB-Odoo_19](https://github.com/cryptoxdog/IB-Odoo_19)
- **Odoo Documentation**: [https://www.odoo.com/documentation/19.0/](https://www.odoo.com/documentation/19.0/)
- **Neo4j Documentation**: [https://neo4j.com/docs/](https://neo4j.com/docs/)

---

**Changelog Version**: 1.0.0
**Last Updated**: 2026-02-24

# Workflow State — Odoo_19_ReBoot

## PHASE

2 (IMPLEMENT) — Partner architecture implemented, ready for validation

---

## Context Summary

Odoo 19 PlasticOS suite: intake, transaction, logistics, documents, commission, facility_profile. Partner model design documented in `docs/TODO.md` — native Odoo fields (company_type, customer_rank, supplier_rank, category_id) vs custom taxonomy. Clean separation: structure (parent_id), legal identity (company_type), operational enablement (rank), classification (category).

---

## Active TODO Plan

- [x] Align PlasticOS partner models with native Odoo fields per docs/TODO.md
- [x] Implement res.partner.category tags (Buyer, Supplier, Carrier, Processor, etc.)
- [x] Use property_payment_term_id for partners (wired into partner_import_service.py)
- [x] Address type handling (contact/invoice/delivery) — implemented in partner_import_service.py
- [x] No custom booleans — use rank + category only

---

## Files in Scope

- `plasticos_facility_profile/models/res_partner.py` — partner hierarchy validation
- `plasticos_partner_import/models/partner_import_service.py` — customer_rank, supplier_rank
- `plasticos_partner_import/models/validation.py` — graph validation
- `plasticos_foundation_seed/data/partner_tags.xml` — business role tags
- `plasticos_foundation_seed/data/material_taxonomy.xml` — material classification tags
- `docs/TODO.md` (reference)

---

## Test Status

✅ Passing — 86 modules loaded, 0 failed, 0 errors (52 tests: plasticos_transaction 47, plasticos_buyer_match_engine 5)

---

## Recent Changes

- 2026-02-24: V3 Audit Fixes — Restored mistakenly deleted inherit files in `plasticos_transaction` (`account_move_inherit`, `load_inherit`, `purchase_inherit`). Fixed null safety in email templates. Documented MRO in `sale_approval.py`. Removed duplicate partner category tags in `plasticos_base`. Set all automation crons to inactive by default.
- 2026-02-24: Enhanced transaction and material profile linkage — Added denormalized `buyer_facility_id` and `supplier_material_id` to `plasticos_transaction` for fast lookup and correct model linkage (Buyer → Facility, Supplier → Material). Added `product_template` linkage (`material_profile_id`) to `plasticos_material_profile` to enable product-based material profile lookup. Registered missing models in `plasticos_intake` to satisfy module wiring check.
- 2026-02-22: Docker & Security Fixes — Created Dockerfile for custom Odoo 19 image with requirements.txt (openai, neo4j, requests); updated docker-compose.yml for local Mac testing; deleted docker-compose.prod.yml (Odoo.sh handles prod); updated all modules to Odoo 19 3-layer security model (Category → Privilege → Group); fixed @api.depends path (product_tmpl_id), duplicate ACL entries, missing plasticos_product dependency.
- 2026-02-22: Neo4j Infrastructure Setup — Created `scripts/setup_neo4j.sh` automation script; updated `requirements.txt` with neo4j>=5.0.0; added `env_file` directive to docker-compose.yml for .env loading.
- 2026-02-22: Inference Engine & Enrichment Integration — Wired `plasticos_inference_engine` as an Odoo addon; integrated into `plasticos_enrichment` with sequential cron (enrichment → inference); fixed critical lint errors (F821) and YAML validation issues in KB files.
- 2026-02-22: Neo4j geo location — Integrated lat/lon into Facility nodes as Neo4j point(); updated `_build_facility_payloads()` to aggregate from res.partner; `sync_facility_nodes()` uses CALL subquery for point upsert; `match_buyers_for_intake()` uses distance() for geo filtering with fallback.
- 2026-02-22: Facility Capability investigation — Confirmed `plasticos_intake_normalizer` assembles supply packet from facility/material profiles; `plasticos_buyer_match_engine` defines demand lanes. Added future task to `docs/TODO.md` for KB enrichment.
- 2026-02-22: Odoo module load order — config/odoo_module_order.yaml (topological), scripts/get_odoo_module_order.py, rebuild/run-odoo-tests.sh use it; added plasticos_security_base, plasticos_geolocalize, plasticos_enrichment, plasticos_inference_engine to default list; readme_config + plasticos_product, plasticos_inference_engine, plasticos_enrichment; docker-compose comment.
- 2026-02-22: Product format — product_template.product_format computed (polymer + type + form + packaging + attributes); product_data.xml unchanged (19 products set attribute_ids; no packaging_id in data).
- 2026-02-22: Material form — removed Film; Bales at top (sequence 5), name/code bales; product_data + buyer_capability + facility_profile + web_leads aligned; film products → form_rollstock.
- 2026-02-22: Polymers — Mixed moved below MRP (sequence 235) in polymer_data.xml.
- 2026-02-22: Partner import — run_csv_import skips None paths (Corporate Only / Facility Only); external ID module plasticos_partner_import; wizard result keys; audit_import_integrity + repair_import_data + wizard Audit/Repair buttons.
- 2026-02-22: .cursorignore added with !.cursor/ !.cursor-commands/ so agent can read/write those paths; they remain in .gitignore. /end-session memory writes run from repo .cursor/memory/cursor_memory_client.py when health succeeds.
- 2026-02-20: Transaction CSV Import Wizard — Import from cieTrade.WksDetail.csv (group by BuySellNo, create transaction + lines); dry run, skip existing; added plasticos_transaction/GUIDE.md for module reference; transaction_line.seal_no added.
- 2026-02-22: /end-session protocol — Handoff in chat; do not write to END-SESSION-REQUIREMENTS; memory path .cursor/memory when present. /dag-authoring skipped (DAG not in repo).
- 2026-02-22: Odoo tests passing — Fixed 10+ module load errors (search view RNG (removed string on search/group_by), tree→list (Odoo 19), related fields (polymer→polymer_id.name), added missing data records (polymers, forms, colors, source_types), restored sale_order_inherit.py, shortened wizard model name (table name >63 chars). CI updated with 3 new checks (#18-20).
- 2026-02-22: CI — Module dependency wiring checker: scripts/check_module_wiring.py + pre-commit hook; fixed plasticos_automation + plasticos_transaction (added product dependency); committed and pushed to staging (18b862e)
- 2026-02-20: /readme + /index — Generated READMEs for all 20 modules, created 14 repo index files
- 2026-02-20: Updated slash commands to be repo-agnostic (02-slash-commands.mdc, readme-dag.md, index.md)
- 2026-02-20: Deprecated "Mack" concept — renamed mack.* namespace to plasticos.* across forbidden/ files
- 2026-02-20: Renamed broker → trucker in logistics context (fields, crons, email templates)
- 2026-02-20: Renamed mail_template → email_template across all modules
- 2026-02-20: Completed full harvest from Files To Harvest/1/ — email templates, security, claims, automation
- 2026-02-19: Wired property_payment_term_id into partner import (Net 30 default for customers/suppliers)
- 2026-02-19: Synced .cursor/memory and .cursor/workflows-synced folders from L9
- 2026-02-18: Created workflow_state.md from docs/TODO.md context

---

## Decision Log

- **Partner architecture:** Use native company_type, customer_rank, supplier_rank, category_id. Business types (Buyer, Supplier, Carrier, etc.) go in res.partner.category, not company_type.
- **Freight:** ✅ RESOLVED — Using Option B (tag only). Carriers use `tag_carrier` tag + `carrier_id` Many2one field on loads. No supplier_rank enforcement.
- **Structure:** Corporate = company; Facility = company + parent_id; AP/Sales Contact = person + parent_id.
- **Address types:** ✅ Using native `type` field (contact/invoice/delivery) in partner_import_service.py

---

## Open Questions

- Which property_* fields to implement first? (payment_term_id, account_receivable_id, account_payable_id)

---

## Next Steps

1. Start full Odoo stack: `docker compose -p plasticos_prod -f docker-compose.prod.yml up -d`
2. Initialize Neo4j graph schema: `./scripts/setup_neo4j.sh --init-schema`
3. Test "Match To Buyers" button on an intake — verify Neo4j graph matching works with fallback.
4. Create KB migration script to rebuild polymer KBs using v8.0 template and v7.0r data.
5. Test enrichment + inference pipeline in Odoo with new v8.0 KB files.

---

## Recent Sessions (7-day window)

- ✅ 2026-02-24: V3 Audit Fixes — Restored mistakenly deleted files, fixed email templates, documented MRO, deduplicated tags, disabled crons.
- ✅ 2026-02-24: Audit Fixes — Removed duplicate model definition in `plasticos_documents` (validation_matrix.py). Populated empty ACL CSV in `plasticos_product`. Verified audit report findings (mostly false positives due to stale index).
- ✅ 2026-02-24: Enhanced transaction and material profile linkage — Added denormalized fields to `plasticos_transaction` and product linkage to `plasticos_material_profile`.
- ✅ 2026-02-22: Plastos sanitization — export_odoo_index, check_odoo_patterns, forbidden files + README, repo-index reports; grep confirms zero "plastos"/"Plastos" remaining.
- ✅ 2026-02-22: Docker & Security Fixes — Dockerfile + docker-compose.yml for local testing; Odoo 19 3-layer security model updates; @api.depends path fix; 83 modules loading successfully.
- ✅ 2026-02-22: Neo4j Infrastructure Setup — setup_neo4j.sh script, requirements.txt neo4j dep, env_file directive for .env loading.
- ✅ 2026-02-22: Inference Engine & Enrichment Integration — Wired inference engine as Odoo addon; integrated into enrichment pipeline with sequential cron; fixed lint/YAML errors.
- ✅ 2026-02-22: Neo4j geo location — Integrated lat/lon into Facility nodes as point(); geo-aware buyer matching with distance filter.
- ✅ 2026-02-22: Facility Capability investigation + TODO — Confirmed normalizer vs match engine roles, added KB enrichment task.
- 2026-02-22: Partner import debug, form/polymer/product format, module load order — Import wizard None-path fix, audit/repair, Bales top/Film removed, Mixed below MRP, product_format computed, config/odoo_module_order.yaml + get_odoo_module_order.py, scripts aligned.
- 2026-02-22: /end-session memory fix + .cursorignore — Ran memory writes from .cursor/memory/cursor_memory_client.py; added .cursorignore so .cursor and .cursor-commands are not Cursor-ignored.
- 2026-02-20: Transaction CSV Import Wizard + plasticos_transaction/GUIDE.md — wizard for cieTrade.WksDetail.csv, grouping by BuySellNo; module guide for states, wizards, CSV mapping.
- 2026-02-22: /dag-authoring → /end-session — DAG not in repo; /end-session command updated (handoff in chat, no requirements file writes).
- ✅ 2026-02-22: Odoo tests passing — Fixed 10+ module load errors (search views, tree→list, related fields, data records, wizard model name); CI updated with 3 new checks (#18-20: related paths, attrs=, states=)
- ✅ 2026-02-22: CI — Module dependency wiring checker (check_module_wiring.py), pre-commit hooks, fixed automation/transaction product deps, staged/committed/pushed to staging
- ✅ 2026-02-21: Pre-commit + CI setup — ruff, XML/YAML checks, Odoo pattern script, fixed 40+ empty __init__.py, fixed UP031 in automation module
- ✅ 2026-02-20: Full harvest + /readme + /index — 14 index files, 20 READMEs, repo-agnostic slash commands
- ✅ 2026-02-19: Session startup, .cursor sync, verified partner architecture complete

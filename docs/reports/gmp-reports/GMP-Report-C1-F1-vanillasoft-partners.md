# GMP Report: C1 lanes F1 + C4, VanillaSoft Company Type and qualified partners

- Campaign: C1, lanes F1 (Company Type everywhere) and C4 (qualified records become partners; operator decisions D32/D33)
- Branch: `feat/c1-f1-vanillasoft-partners`, stacked on `feat/c1-d2-site-consumers` (#528)
- Modules:
  - `plasticos_crm_bridge` `19.0.3.7.6` → `19.0.3.7.7`
  - `plasticos_crm_sync` `19.0.1.9.31` → `19.0.1.9.33` (`.32` carries the backfill migration)
- Production facts (probe 2026-11-17): 4,088 CRM leads, 4,084 of them with no partner; CRM tags Buyer 980 and Supplier 3,010; no Company Type CRM tags.
- No Production run from this lane. `make import-vanillasoft` stays operator-run and Production-only (AGENTS.md, 2026-11-10).

## Phase 0 — Plan

1. **F1, CRM tags:** a CRM tag for each of the 12 Company Types: Distribution Center, Commercial Recycler, Pallet Recycler, Compounder, Grinder/Processor, E-Waste, MRF, Manufacturer, Broker, Carrier, Exporter, Toll Processor.
2. **F1, where Company Type is written:** always on the lead's CRM tags, partner or not. When the lead resolves to a company, also on that company's partner tag (the commercial entity, never a site), mapped by external id.
3. **F1, backfill:** a one-shot, idempotent backfill with counts.
4. **C4, partner rule:**
   - Buyer: becomes a partner at every Lead Status except 2c COLD, 5 Dead Lead, 6 Wrong #, 7 Do Not Call, 8 Duplicate.
   - Supplier-only or unspecified: becomes a partner only at 2a HOT, 2b WARM, 3 Resist, or when already approved.
   - Everything else stays a lead.
   - An existing partner is linked, never duplicated; ERP companies come first.
5. **C4, Do Not Call:** on an existing company, the DNC status tag and a blacklist of the lead's email and phones. Nothing is ever removed.

## Phase 1 — Baseline

| Fact | Where |
|---|---|
| Company Type went to the partner only. Without a verified company it was skipped with `BLOCKED_COMPANY_TYPE_VALUE`. | `orchestrator.py` `_apply_company_type` |
| `COMPANY_TYPE_MAPPING` had 10 names; Exporter and Toll Processor were missing. | `crm_mapping.py` |
| No VanillaSoft path created a `res.partner`. Approved contacts bind to their ERP person through the crosswalk external id. | `_bind_approved_contact`, `_erp_person_for_ct` |
| The raw Company Type is kept only as a `VanillaSoft Company Type: X` paragraph in the lead description. `plasticos.crm.external.table.row` holds custom-table rows, not contact fields. | `_lead_evidence`; `models/crm_external_table_row.py` |
| No `mail.blacklist` or `phone.blacklist` use, and no handling of 7=Do Not Call beyond the stage guard. | |
| Odoo 19 blacklist API, read from the 19.0 source: `mail.blacklist._add(email, message=None)` and `phone.blacklist._add(numbers, message=None)` (`add` sanitizes through `env.user._phone_format`). `phone_validation` is a dependency of `crm`. | |

## Phase 2 — Implement

| File | Change |
|---|---|
| `plasticos_crm_bridge/models/crm_mapping.py` | Adds `CRM_COMPANY_TYPE_TAG_MAPPING` (12 names → `crm_tag_company_type_*`) and `DNC_PARTNER_TAG_XMLID` (`plasticos_base.tag_do_not_contact`). `COMPANY_TYPE_MAPPING` gains Exporter → `plasticos_base.tag_exporter` and Toll Processor → `plasticos_base.tag_toll_processor`; lane F2's #525 puts both in the Company Type group. |
| `plasticos_crm_bridge/data/crm_tag_data.xml` | The 12 Company Type CRM tags, created through the same `_plasticos_adopt_crm_role_tag` used for Buyer and Supplier. An existing tag of the same name is adopted, never duplicated. |
| `plasticos_crm_sync/services/vanillasoft_partners.py` (new, pure) | Status constants; `parse_roles`; `partner_allowed` (the D32/D33 rule); `trade_ranks`; `company_type_from_text`; `normalized_company_name`; `pick_existing` (ERP first, ambiguity refused); `backfill_company_type_tags`. |
| `plasticos_crm_sync/services/orchestrator.py` | Details below. |
| `plasticos_crm_sync/models/crm_lead_sync.py` | `crm.lead._plasticos_backfill_company_type_tags()`: reads every VanillaSoft lead's description paragraph and adds the CRM tag. Returns and logs the four counts below. |
| `plasticos_crm_sync/migrations/19.0.1.9.32/post-migrate.py` | Runs the backfill once on upgrade. |
| Both manifests and READMEs | Versions. |
| `tests/test_vanillasoft_partners.py` (new) | Pure tests. |

Orchestrator changes:

- `_apply_lead_company_type` puts the Company Type CRM tag on the lead, with or without a partner.
- `_apply_company_type` is unchanged. It writes the partner tag on `_verified_company`, which lane A (#528) changed to resolve the commercial entity, never a site.
- `_resolve_vanillasoft_partner` runs before materials on the non-approved path, in its own savepoint. Its steps:
  1. **7=Do Not Call:** only an existing company is resolved; nothing is created or linked.
  2. **Allowed by the rule:**
     - The lead's company is used if it has one.
     - Otherwise `_existing_company` looks for a match.
     - With no match, it creates the company and sets the lead's `partner_id` to it.
     - The lead stays the pipeline record.
     - `_ensure_contact_person` reuses a child with the same name or email, or creates the person.
     - `_raise_trade_ranks` sets `customer_rank` / `supplier_rank` to at least 1 from Buyer/Supplier. It never lowers them.
- **Gate's Company Roles (CTO directive):** wherever ranks are raised, `_link_company_role_tags` also adds the matching Company Roles tag, because Gate still reads `company_role_tag_ids`. Buyer → `plasticos_facility_profile.company_role_buyer`, Supplier → `company_role_supplier`. Tags are added, never removed, and a missing external id is skipped quietly.
- `_apply_existing_partner_rules` covers approved contacts. Their ERP person already exists, so only ranks and DNC are applied, to that person's commercial company.
- `_apply_do_not_call` adds the DNC tag (skipped quietly when the external id is absent). It calls `mail.blacklist._add` for the DTO and lead emails, and `phone.blacklist._add` for each sanitized phone and mobile. Nothing is removed.

Counts the backfill returns:

| Count | Meaning |
|---|---|
| `set` | Tag added |
| `already_set` | Tag was already on the lead |
| `no_source_value` | No recorded Company Type |
| `unmapped` | Recorded value with no Company Type tag |

Materials follow the 2026-10-30 rule with no new code. The lead's `partner_id` is the company. A standalone company is its own facility (`is_facility`), so `_apply_contact_materials` puts the materials on the resolved partner through the existing `_facility_for_material` path.

**Material placement and Material Type / Form (operator, 2026-11-17; ADR-132):**

- **Placement:** `_material_owner` decides where a profile goes. A material profile never lands on a person.
  1. The lead's partner, if it is a site.
  2. Else the person's one linked site.
  3. Else, of several linked sites, the one whose address matches the source record (zip, else city + street). If none matches, nothing is stored and `facility ambiguous: N linked sites` is reported (OPTIONAL_CONTEXT).
  4. Else, when the person's company has no sites, the company.
  5. Otherwise nothing is stored and the owner is reported unresolved.
- **The person fallback is gone** from `_apply_resolved_approved_materials` and from `_apply_person_materials` (approved contact with no lead).
- **Type and Form are separate:** the record-level Material Type and Material Form, plus bare `Type`/`Form`, are two separate slots. One value applies to every profile of the record; several values are ignored with `<field> ignored: N values`. Only an empty field is filled.
  - Material Type resolves to `plasticos.source.type` by name or code (Post Consumer → POST_CONSUMER).
  - Material Form resolves first to `plasticos.packaging.type` (Bales → packaging, never a form), then to an active `plasticos.material.form`.
  - The form is part of the profile identity, so it is passed in at creation and a replay finds the same profile.
- **Section fields kept as they were:** section fields (`Type (LDPE)`, `Form (PP)`) keep their existing behaviour as that section's polymer hint. The census shows they carry polymer text ("LDPE Film"), and the conflict-detection tests depend on it.

### Matching (stated assumption)

The repo has no general VanillaSoft-to-partner duplicate matcher; approved contacts match only through the ERP crosswalk. For the rest, `_existing_company` matches top-level companies, archived ones included:

- **Normalization:** case, punctuation, "&"/"and" and legal suffixes (Inc, LLC, Co, Corp, Ltd, …) are ignored.
- **ERP companies first:** these are companies carrying a `plasticos_transaction.legacy_erp_cp_*` external id.
- **Ambiguity:** more than one match at a tier is refused (`BLOCKED_PARTNER_AMBIGUOUS`) and nothing is created.
- **Blank company:** a company name that normalizes to nothing creates nothing (`BLOCKED_PARTNER_NO_COMPANY`).

If the operator wants a stricter matcher, for example name plus state or phone, it replaces only `_existing_company`.

## Phase 3 — Enforce

- ruff 0.16.0: clean.
- `pre-commit run --files` on the changed files: all hooks passed. No hook was bypassed.

## Phase 4 — Validate

`tests/test_vanillasoft_partners.py`: 96 passed. It covers:

- every status × role combination of the rule;
- approved supplier and unspecified contacts;
- name matching;
- ERP-first linking with no duplicate;
- ambiguity refused;
- person reuse;
- ranks raised but never lowered;
- Do Not Call: DNC tag plus email and phone blacklist on an existing company, nothing without one;
- the Company Type CRM tag on a lead with no partner;
- the partner tag going to the commercial entity, never a site;
- the backfill counts, and that a second run sets nothing;
- the 12-name mappings and data.

Other suites run together with it: 223 passed. These are the classification, approved-identity, site-consumer, history-link and phantom-enum suites.

Not run: Odoo runtime and Enterprise smoke (Cursor lane T). The ORM paths are not yet proven in a running Odoo: partner create, the blacklist `_add` calls, the tag adoption and the backfill on real data.

## Phase 5 — Recursive verify

- Files changed: `plasticos_crm_bridge`, `plasticos_crm_sync`, the new test file and this report.
- Not touched: `plasticos_facility_profile` and `plasticos_partner_import`.
- The import's run authority is unchanged.

## Phase 6 — Finalize

Residual risk:

- **Name matching misses:** with no stronger matcher, a company whose name differs in more than case, punctuation or legal suffix is created as a new partner. Ambiguous matches are refused, never guessed.
- **Production volume:** by the counts above, a first Production run may create several thousand partners.

# ADR-132: A material profile belongs to the site, never to a person

**Status:** Accepted (operator, 2026-11-17)
**Decision date:** 2026-11-17
**Applies to:** every importer that creates `plasticos.material.profile` records: the VanillaSoft sync (`plasticos_crm_sync`), the ERP material-profile loader (`plasticos_transaction`), and manual entry
**Decision owner:** Operator (campaign C1)
**Implementation owner:** `plasticos_crm_sync` (this PR)
**Related:** ADR-004 (intake vs material profile), ADR-005 (intake / material profile bridge), ADR-131 (sites as native addresses), ADR-133 (which VanillaSoft records become partners)

## Context

- A person can come and go, and one person can oversee several sites. The site is what generates the material.
- Before this decision, a VanillaSoft lead matched to an ERP person put its material profiles on the person card whenever no single site resolved (`plasticos_crm_sync/services/orchestrator.py`, `_apply_resolved_approved_materials`).
  Example with synthetic names: Pat Doe of "Acme Recycling" is linked to the site "Acme Plant 2". The record says "Materials: MRP, LDPE, PP Supersacs", and the three profiles landed on Pat Doe instead of on Acme Plant 2.
- The source record also carries a Material Type (for example Post Consumer) and a Material Form (for example Bales). The sync merged both into one "hint" that it applied only when the record had exactly one material.

## Decision

Where a material profile goes, in this order:

1. The lead's partner is a site: that site.
2. The person is linked to one site (`location_partner_ids`, either ADR-131 site shape): that site.
3. The person is linked to several sites: the one site whose address matches the source record (zip, otherwise city and street). If none or several match, nothing is stored and the record is reported as ambiguous. The raw values stay on the lead.
4. The person's company has no child sites: the top-level company.
5. A material profile never lands on a person.

### Material Type and Material Form

| Field | Value | What happens |
|---|---|---|
| Materials | MRP, HDPE, PET, PP | 4 profiles |
| Material Type | Post Consumer, Post Industrial | Ignored (2 values), reported |
| Material Form | Bales | Packaging Bales on all 4 profiles |

- One value applies to every profile from the record.
- Several values: the field is ignored and listed in the run's review section.
- Bales and other packaging names go to packaging type, never to form.

In detail, Material Type and Material Form are two fields:

- Material Type sets `source_type_id` (Post Consumer → `POST_CONSUMER`).
- Material Form sets `form_id`.
- One value in a field applies to every material profile of that record. Several values mean the field is ignored and reported.
- Only an empty field is filled; a stored value is kept.
- Bales (and any other packaging type such as Gaylords) is packaging: it sets `packaging_type_id`, never `form_id`.

Which importers follow this:

| Importer | Status |
|---|---|
| VanillaSoft sync (`plasticos_crm_sync`) | Changed by this PR. It previously fell back to the person and merged Type and Form. |
| ERP material-profile loader (`plasticos_transaction`, AGENTS.md 2026-11-13) | Already conforms. It writes on the ERP site child, or on the company when the company has no site children. |
| Manual entry | Guidance: put the profile on the site, or on the company when it has no sites. |

## Consequences

- No new field and no new model.
- **Unplaced materials are loud and reviewable after every run.**
  - **Summary rows:** each record whose person oversees several sites with no single address match is an error row with `error_type` `MATERIAL_PLACEMENT_REVIEW` and category `optional_context`.
    - The row gives the record ref, lead id, matched partner id, candidate site ids and their cities, the source zip and city, the unplaced phrases, and the reason ("no address match" or "N address matches").
    - The rows are kept ahead of other optional rows under the 1,000-row cap.
    - They do not fail the run and do not enter the balance equation.
    - A Material Type or Form ignored for several values is a row with `error_type` `MATERIAL_FIELD_IGNORED`.
    - The shared summary contract (`contracts/schemas/draft/import-run-summary.schema.json`) allows no extra top-level keys. So these rows are the summary's own `errors` rows, typed by `error_type`, not a separate `material_placement_review` key.
  - **Shell output:** `import_vanillasoft_shell.py` prints two sections after the summary, every row, never truncated. Both sections are printed even when N = 0.
    - `=== NEEDS REVIEW: N VanillaSoft records have materials that were NOT placed (person oversees several sites) ===`
    - `=== NEEDS REVIEW: N Material Type/Form fields ignored (several values) ===`
  - **Make target:** `make import-vanillasoft` prints the placement count as its last line.
  - **Odoo:** the lead gets one native To Do (`mail.activity`), "Place materials: N candidate sites". Its note lists the phrases and candidate site names. It is assigned to the lead's salesperson, else the import user.
    - A replay keeps one activity and updates its text.
    - A later run that places the materials marks it done.
- Material profiles already held by a person are not moved by this PR. A follow-up, either a VanillaSoft replay or a separate migration, re-points them to the site or company.
- This supersedes the AGENTS.md 2026-10-30 sentence "When that site cannot be resolved, they go on the matched ERP contact person." See the AGENTS.md 2026-11-17 correction.

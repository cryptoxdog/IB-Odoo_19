# GMP Report C1-E — ERP importer: sites as native addresses

Campaign C1, lane E. Implements ADR-131 Decision A for `plasticos_partner_import`.
Branch `feat/c1-e-importer-sites` from `origin/fix/c1-erp-contact-identity` (#521, `f4fe473`), merged with `origin/feat/c1-d1-site-core` (#524, `be4cc57`). Merge, no rebase.

## Phase 0 — Plan

| # | File | Action | Expected behavior |
|---|---|---|---|
| 1 | `models/erp_import_service.py` `_create_location` | Replace | A new site is `is_company` False, `type` from `mapping.address_kind`, parent = counterparty. A replay rewrites an old-shape site in place (same record id and `legacy_erp_address_<AddressID>` marker). Company-level folding of billing addresses is unchanged. |
| 2 | `models/erp_import_service.py` person guards | Replace | `_retire_inactive_contacts`, `_retire_stale_contact`, `_retire_superseded_partner` archive persons only. A site of either shape is never archived as a person. |
| 3 | `models/erp_import_service.py` `_fill_sites_from_person` (new), `erp/mapping.py` `site_contact_fill` (new) | Insert | D12: after a counterparty's people are stored, a site with exactly one linked active person takes that person's phone / email where its own is blank. A value already on the site is never replaced. |
| 4 | `models/partner_import_service.py` | Replace | The CSV "Location" facility and `_load_facilities` write the native site shape (`company_type` site, `is_company` False, `type` delivery). |
| 5 | `models/validation.py` | Replace | The audit's "locations missing facility_role" reads `_plasticos_site_domain()` (both shapes). |
| 6 | `wizards/partner_bulk_update_wizard.py` | Replace | Company / contact counts exclude sites; the chatter names a site's old type "Site". |
| 7 | `scripts/validate_partner_layer.py` | Replace | Person reads exclude sites (`company_type = person`, or the D1 predicate). |
| 8 | `__manifest__.py`, `README.md` | Bump | 19.0.2.10.40 (#521) → 19.0.2.10.41 |
| 9 | `tests/test_c1_importer_sites.py` (new) | Insert | Pure pytest |

`_copied_role` is unchanged: a site still takes the parent's ranks, Company Role and role tags. With `is_company` False, Odoo now also syncs the commercial fields from the parent, as ADR-131 intends.

## Phase 1 — Baseline

- `_upsert` writes only the values that differ, against the record named by the marker, so the shape change converts an existing site on replay without creating a record.
- D1 (`plasticos_facility_profile/address_meaning.py`): `is_site` = has a parent and (`type` delivery/invoice or `is_company`). `company_type` stores `site` for both shapes.

## Phase 2 — Implement

As planned. Not touched: `wizards/partner_import_wizard.py` `action_view_partners` lists companies (`is_company` True) on purpose. It is not a site read.

## Phase 3–4 — Enforce / Validate

- `ruff 0.16.0` format + check: clean.
- `python3 scripts/check_module_wiring.py`: passed.
- `tests/test_c1_importer_sites.py`: 20 passed.
- Fixture fix in `tests/test_erp_import_contract.py` / `tests/test_erp_contact_identity.py`: their fake `res.partner` lacked `_plasticos_is_site()` and `site_person_ids`. The real model has both through the `plasticos_facility_profile` dependency. The fakes now mirror D1's predicate and the site–person link. No assertion changed. Before the fix 7 tests errored with `AttributeError`. After it, the import-contract, contact-identity, source-layer, site-core, contact-hierarchy and mapping-status suites pass (253).
- Full `pytest tests/`: see the commit's PR evidence.
- Not run: Odoo runtime / Enterprise install-smoke (Cursor lane T). `plasticos_partner_import/tests/test_validation_query_scope.py` (Odoo runtime) still creates old-shape sites, and the D1 domain still matches them.

## Phase 5 — Recursive verify

Only `plasticos_partner_import`, two existing test fakes, one new test file and this report changed. No new field, model, ACL or XML.

## Open question

The legacy CSV path `_create_facility_contact` creates people with `type` invoice or delivery under a facility. Under D1 such a person with a parent reads as a site. The CSV path is not the canonical ERP import (ADR-021), so it was left as it is. Raised for the CTO.

## Phase 6 — Finalize

Published with `make pr-nosmoke base=fix/c1-erp-contact-identity`.

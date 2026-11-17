# GMP Report — C1 lane D1: site core

- Campaign: C1 (PlasticOS contacts / ERP sync realignment), lane D1
- Branch: `feat/c1-d1-site-core`, stacked on `fix/c1-partner-contact-format` (#522)
- Module: `plasticos_facility_profile` `19.0.5.4.16` → `19.0.5.4.17`
- Decision source: ADR-131 (PR #520). ERP sites become native delivery/invoice
  addresses (`is_company` False) in a later data phase. D1 makes the code accept
  both shapes now, with no data change.

## Phase 0 — Plan

1. Predicate contract that lane D2 codes against, using these exact names:
   `res.partner._plasticos_is_site()` returns a bool for one record;
   `res.partner._plasticos_site_domain()` returns the matching search domain.
2. Site becomes a third Contact type on the existing stored `company_type`, with no new column.
3. Every place this module treats "site = company with a parent" goes through the
   predicate or through `company_type == 'site'`.
4. One address label per address.

## Phase 1 — Baseline

- `company_type` was already a stored override (compute `is_company` → company/person).
- Places that equated a site with a company that has a parent: `location_child_ids`,
  `_compute_linked_person_channels`, `is_facility`, `contact_header_name`,
  `_plasticos_reach_candidates`, `action_remove_location`, `_compute_name_parts`,
  and the view conditions in `facility_profile_views.xml` and `partner_ux.xml`.
- The Material Profile section (`plasticos_material_profile.view_partner_form_material_tab`)
  is shown only when `is_company` is true.

## Phase 2 — Implement

| File | Change |
|---|---|
| `address_meaning.py` | Pure functions: `is_site`, `site_domain`, `contact_type`, `contact_type_inverse`, `address_type_meaning(…, site=)`. |
| `models/res_partner.py` | `company_type` gains `selection_add=[("site", "Site")]` (uninstall falls back to company/person). Compute depends on `is_company`, `parent_id`, `type`. Adds `_plasticos_is_site` and `_plasticos_site_domain`. Routes `is_facility`, `location_child_ids`, linked-person channels, `contact_header_name`, reach candidates, name parts, `action_remove_location` and the address label through the predicate. |
| `views/facility_profile_views.xml` | Conditions use `company_type` (`'company'` / `'site'` / `'person'`) instead of `is_company` + `parent_id`. The Address Type row shows the meaning and hides the raw `type` whenever a meaning exists. |
| `views/partner_ux.xml` | Same conditions on `company_type`. Search filters Companies / People / Sites on `company_type`. New inherited view `partner_form_material_profile_sites` shows the Material Profile section on companies and sites. |
| `migrations/19.0.5.4.17/post-migrate.py` | Recomputes the stored `company_type` and `is_facility` in batches of 1000, without the inverse, and logs counts per Contact type. |
| `__manifest__.py`, `README.md` | Version `19.0.5.4.17`. |

Labels (`address_type_meaning`), applied to sites:

- An invoice type becomes "Mailing Address".
- A PICK-UP source label becomes "Pick-Up Address", whatever the role.
- A supplier site becomes "Pick-Up Address".
- A buyer site becomes "Delivery Address".
- Carrier, broker, internal, prospect, other or no role becomes "Site Address".
- A company itself keeps "This record is the company itself."

Two deviations from the assignment, made so a chosen Contact type round-trips:

- **Site:** choosing Site sets the address type to Delivery unless it is already Delivery or Invoice. The assignment only covered changing `contact`. Without this, Site on an `other` address would compute back to Person.
- **Person:** choosing Person turns a Delivery or Invoice address back into a Contact. The assignment specified only `is_company` False. Without this, Person on a delivery address would compute back to Site.

## Phase 3 — Enforce

- ruff 0.16.0 check and format: clean.
- `pre-commit run --files <changed>`: all hooks passed, including `odoo19-xml`, `xpath-stability`, `field-integrity` and `module-wiring`.
- The phantom-enum scanner reads only Selection values passed as the first
  argument, so it does not see values added through `selection_add`. The
  comparisons use the named constants `CONTACT_SITE`, `CONTACT_COMPANY` and
  `CONTACT_PERSON`; the scanner itself is unchanged.

## Phase 4 — Validate

- `tests/test_partner_site_core.py` (new, pure) covers:
  - the predicate for both site shapes, for people and for top-level companies;
  - the domain evaluated against the predicate on every combination of parent × type × is_company;
  - the compute and the inverse round-trip;
  - labels per role;
  - the model and view contracts.
- Existing tests updated to the new contract:
  - `tests/test_erp_source_layer.py::test_address_type_meaning_follows_the_company_role` checks the new labels.
  - `tests/test_partner_contact_hierarchy.py::test_contacts_list_shows_first_and_last_name_after_name` checks first and last name invisible unless `company_type == 'person'`.
- Targeted run: 275 passed (new, updated, contact-format, phantom-enum and view-inheritance files).
- Not run: Odoo runtime and Enterprise install-smoke (Cursor lane T). The ORM
  behaviour of `selection_add` on the stored override, the recompute migration
  and the inherited material view are proven only by the runtime gate.

## Phase 5 — Recursive verify

- Files changed: `plasticos_facility_profile` (owned) and two existing test files in
  `tests/`, updated because the operator-approved labels and view conditions changed.
- No file of any other module was changed.

## Remediation (operator 2026-11-17)

- **New label:** a site of a company that is both buyer and supplier now shows one label, "Pick-Up / Delivery Address". The company here is the parent's commercial entity, with `customer_rank > 0` and `supplier_rank > 0`.
- **Order of rules:** a PICK-UP source label still wins, and an invoice site stays "Mailing Address".
- **Code:** `address_type_meaning(..., buyer_and_supplier=)` takes the new input, and `_compute_address_type_meaning` reads the company's ranks.
- **Version:** 19.0.5.4.18.
- **Tests:** in `tests/test_partner_site_core.py`.

## Phase 6 — Finalize

Residual risk:

- A top-level company with any native delivery or invoice child now has
  `is_facility` False, and that child is a site with `is_facility` True. This
  follows the ADR-131 shape. Callers of `is_facility` in other modules
  (`plasticos_crm_bridge`, `plasticos_crm_sync`) belong to lane D2.
- Imports that write `company_type: "company"` for an ERP site still produce a
  company child, which computes to `site`.

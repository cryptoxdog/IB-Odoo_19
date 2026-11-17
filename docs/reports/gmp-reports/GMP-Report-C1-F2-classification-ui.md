# GMP Report — C1 F2: partner classification UI on native fields

**Campaign:** C1 (PlasticOS contacts / ERP sync realignment), lane F2
**Authority:** ADR-131 Decision B (`docs/adr/ADR-131-partner-sites-native-addresses-and-native-classification.md`)
**Branch:** `feat/c1-f2-classification-ui`, stacked on `feat/c1-d1-site-core` (#524)
**Module:** `plasticos_facility_profile` 19.0.5.4.17 → 19.0.5.5.0
**Date:** 2026-11-17

## Phase 0 — Plan (scope locked)

| # | Item | Files |
|---|---|---|
| 1 | Trade Role badge from native ranks; Buyer & Supplier filter; Group By Trade Role | `models/res_partner_trade_role.py`, `views/partner_ux.xml`, `migrations/19.0.5.5.0/post-migrate.py` |
| 2 | Company Type (12) and Status (4) tag groups; same-name tags re-parented, never duplicated | `data/partner_classification_data.xml`, `models/res_partner_category.py` |
| 3 | Mirror rule: company Company Type tags onto its sites and people, nothing else | `models/res_partner_company_type_mirror.py` |
| 4 | Tags under the name on company, site and person cards; Tags column shown; Company Type filter | `views/facility_profile_views.xml`, `views/partner_ux.xml` |
| 5 | Contact column on the Locations list | `views/facility_profile_views.xml` |
| — | Pure rules for 1–3 | `classification.py` |

No new fields. `plasticos_crm_bridge`, `plasticos_crm_sync` and `plasticos_base` are not edited.

## Phase 2 — Implementation

1. **Trade Role.** `company_role` stays the stored field it was. It is now a stored compute of the commercial partner's `customer_rank` / `supplier_rank` (`readonly=False`): both ranks → `both` (new selection value, never `broker`), one rank → `buyer` / `supplier`, neither → the current Carrier / Broker / Internal / Prospect / Other value is kept and a stale rank value is cleared. An explicit write still syncs the ranks (`_sync_rank_from_role`, now also for `both`). The post-migrate recomputes stored rows in batches of 1000.
2. **Tag groups.** `partner_category_company_type` and `partner_category_status` (noupdate). `plasticos_base` Exporter and Toll Processor join Company Type; Needs Enrichment, Do Not Contact, Key Account and Preferred Carrier join Status. Those six overrides are `noupdate="0"` because `plasticos_base` resets their parent on its own upgrade and this module upgrades after it. The ten `plasticos_crm_bridge` names load after this module (it depends on it), so a `res.partner.category.create` override puts a root-level tag with a Company Type name into the group unless the group already holds that name; a data `<function>` moves existing same-name root tags on every install and upgrade and creates a missing name only when `plasticos_crm_bridge` is neither installed nor about to be.
3. **Mirror.** One owner. On create or a `category_id` write of a partner whose Contact type is Company, every descendant (`child_of`) gets the company's Company Type tags; its other tags stay. The child writes carry a context key, so they do not mirror again.
4. **Cards and list.** One `category_id` under the name for every card type; the base Tags row is hidden and the company-only Tags row is removed. The Contacts list shows the base Tags column (`optional="show"`) and the Trade Role badge. Search: Buyers, Suppliers, Buyer & Supplier, Has Company Type, Group By Trade Role.
5. **Locations list.** `contact_header_name` as Contact, after Name.

## Phase 4 — Validation

| Check | Result |
|---|---|
| `pytest tests/test_partner_classification.py` (new) | pass |
| `pytest` on every `tests/` module that reads `company_role`, `facility_profile` or partner categories, plus `test_repo_dependency_integrity.py` | 478 passed, 3 skipped |
| `ruff check` / `ruff format --check` (0.16.0) | pass |
| `ci/check_odoo19_xml.py`, `scripts/check_module_wiring.py`, `ci/check_circular_deps.py` | pass |
| Enterprise install / runtime | **not run here** (Cursor lane T) |

Test-only change: `tests/test_partner_contact_hierarchy.py` asserted the replaced layout (Tags on the company card between Lead Source and Salesperson). It now asserts the ADR-131 layout (tags once under the name, not on the company card); its other assertions are unchanged.

## Phase 5 — Residual risk (for lane T)

- `//list/field[@name='category_id']` assumes the Odoo 19 base `view_partner_tree` has a Tags column; the Enterprise smoke proves it.
- `plasticos_security_base.view_partner_form_private` inserts the private toggle before the first `category_id`; when it applies after this view, the toggle sits beside the tags under the name.
- A Broker write syncs `supplier_rank` (unchanged `_SUPPLIER_ROLES`), so a broker shows Supplier. Keeping a Broker badge would need that rank sync changed.
- A site or person created after the company's tags were set gets them on the company's next tag change, not at creation.
- The "Operational" parent in `plasticos_base` is left with no tags.

## Phase 6 — Evidence

Commit and PR are listed in the PR body; Enterprise smoke runs in Cursor lane T.

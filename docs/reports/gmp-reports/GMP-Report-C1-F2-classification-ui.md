# GMP Report — C1 F2: partner classification on native ranks and tags

**Campaign:** C1 (PlasticOS contacts / ERP sync realignment), lane F2
**Authority:** ADR-131 Decision B (`docs/adr/ADR-131-partner-sites-native-addresses-and-native-classification.md`); operator scope change of 2026-11-17 (trade role as two tags, not a badge; Do Not Contact, displayed as DNC, feeds the Odoo blacklists)
**Branch:** `feat/c1-f2-classification-ui`, stacked on `feat/c1-d1-site-core` (#524)
**Module:** `plasticos_facility_profile` 19.0.5.4.17 → 19.0.5.5.1
**Date:** 2026-11-17

## Phase 0 — Plan (scope locked after the operator change)

| # | Item | Files |
|---|---|---|
| 1 | Trade Role tag group (Buyer, Supplier) kept from the native ranks; mirrored to sites; filters Buyers / Suppliers / Buyer & Supplier on the ranks; `company_role` left as it is | `models/res_partner_classification.py`, `migrations/19.0.5.5.0/post-migrate.py`, `views/partner_ux.xml` |
| 2 | Company Type (12) and Status (4) tag groups; same-name tags re-parented, never duplicated | `data/partner_classification_data.xml`, `models/res_partner_category.py` |
| 3 | Mirror: Company Type onto sites and people, Trade Role onto sites, nothing else | `models/res_partner_classification.py` |
| 4 | DNC (the renamed Do Not Contact tag) adds the record's emails to `mail.blacklist` and phones to `phone.blacklist`; never removes | `models/res_partner_classification.py` |
| 5 | Tags under the name on company, site and person cards; Tags column shown; Has Company Type filter; Contact column on the Locations list | `views/facility_profile_views.xml`, `views/partner_ux.xml` |
| — | Pure rules for 1–4 | `classification.py` |

No new fields. `plasticos_crm_bridge`, `plasticos_crm_sync` and `plasticos_base` are not edited.

## Phase 2 — Implementation

1. **Trade Role.** Group `partner_category_trade_role` with the existing `plasticos_crm_bridge` Buyer and Supplier tags. A company's Trade Role tags follow its ranks: `customer_rank > 0` → Buyer, `supplier_rank > 0` → Supplier, both → both tags; a tag the ranks do not mean is removed. It runs on create, on any write of a rank (the first rank increase in `account` `_increase_rank` is an ORM write; later increases go through a postcommit ORM write and leave the tags unchanged), and in the post-migrate for existing companies. No "Both" and no "Broker" trade label exists. `company_role` and its rank sync are unchanged.
2. **Tag groups.** `partner_category_company_type`, `partner_category_trade_role`, `partner_category_status` (noupdate). `plasticos_base` Exporter and Toll Processor join Company Type; Do Not Contact (renamed in place to DNC: same record and external id) joins Status. Those three overrides are `noupdate="0"` because `plasticos_base` resets their parent on its own upgrade and this module upgrades after it. `plasticos_crm_bridge` loads after this module, so a `res.partner.category.create` override puts a root-level tag with a Company Type or Trade Role name into its group unless the group already holds that name; a data `<function>` moves existing same-name root tags on every install and upgrade (keeping their partner links) and creates a missing name only when `plasticos_crm_bridge` is neither installed nor about to be. Broker is built like every other Company Type member.
3. **Mirror.** One owner. When a company's tags change, every descendant (`child_of`) gets the company's Company Type tags, and every descendant that is a site (`_plasticos_is_site`) also gets its Trade Role tags; other tags stay. Child writes carry a context key, so they do not mirror again.
4. **DNC.** When the tag (`plasticos_base.tag_do_not_contact`; logic keys on the record, not the name) is newly on a record (any card type), each valid address in `email` goes to `mail.blacklist._add`, and `phone` / `mobile` (when the field exists and the number formats) go to `phone.blacklist.add` when `phone_validation` is installed. Both checked against the Odoo 19 source (`mail/models/mail_blacklist.py`, `phone_validation/models/phone_blacklist.py`): both reactivate an existing entry and never duplicate it. Nothing removes an entry.
5. **Views.** One `category_id` under the name for every card type; the base Tags row is hidden and the company-only Tags row removed. Contacts list shows the base Tags column (`optional="show"`). Search adds Buyer & Supplier (both ranks) and Has Company Type. Locations list gets `contact_header_name` as Contact.

6. **Company Roles data (remediation).** `data/company_role_tag_data.xml` (the four `plasticos.company.role.tag` records buyer, supplier, service, carrier) was never in the manifest `data` list, so no install or upgrade created them; Production holds 0 records and 0 companies with Company Roles, while `plasticos_gate` `derive_subject_role` and the ERP importer (`plasticos_partner_import/erp/mapping.py`) read them. It now loads right after the security CSV. A test fails when any XML/CSV under `data/` is missing from the manifest.

**Release order:** upgrade `plasticos_facility_profile` before the partner replay, so the ERP import can set Company Roles.

7. **Status group (operator decision 2026-11-17, remediation).** Status holds the VanillaSoft lead status and DNC, nothing else: `status_current` Current (VanillaSoft 1, Currently Working With; replaces Key Account), `status_open` Open (2), `status_hot` Hot (2a), `status_warm` Warm (2b), `status_cold` Cold (2c), `status_resist` Resist (3), `status_unqualified` Unqualified (4), all noupdate under `partner_category_status`. `_plasticos_bind_status_tags` runs before those records and gives an existing same-name tag (in the group, else the oldest root one) the external id, so none is duplicated. Needs Enrichment, Key Account and Preferred Carrier are no longer referenced (Lane B retires them in `plasticos_base`, #527). The seven lead-status tags mirror from a company to its sites like Trade Role; DNC is not mirrored, because it is set per record and drives the blacklist rule. Contacts search adds Has Status.

## Phase 4 — Validation

| Check | Result |
|---|---|
| `pytest tests/test_partner_classification.py tests/test_partner_contact_hierarchy.py tests/test_partner_site_core.py tests/test_phantom_enum_values.py tests/test_module_readme_index.py` | 224 passed |
| `ruff check` / `ruff format` (0.16.0) | pass |
| `ci/check_odoo19_xml.py`, `scripts/check_module_wiring.py`, `ci/check_circular_deps.py` | pass |
| Enterprise install / runtime | **not run here** (Cursor lane T) |

Test-only change: `tests/test_partner_contact_hierarchy.py` asserted the replaced layout (Tags on the company card between Lead Source and Salesperson). It now asserts the ADR-131 layout (tags once under the name, not on the company card); its other assertions are unchanged.

## Phase 5 — Residual risk (for lane T)

- `//list/field[@name='category_id']` assumes the Odoo 19 base `view_partner_tree` has a Tags column; the Enterprise smoke proves it.
- `plasticos_security_base.view_partner_form_private` inserts the private toggle before the first `category_id`; when it applies after this view, the toggle sits beside the tags under the name.
- Trade Role tags follow the ranks of a company only. A rank raised on a site or person does not tag the company.
- A site or person created after the company's tags were set gets them on the company's next tag change, not at creation.
- The "Operational" parent in `plasticos_base` is left with no tags.
- Broker as a Company Type is pending an operator decision; it is built like the other members and keeps its links.

## Phase 6 — Evidence

Commit and PR are listed in the PR body; Enterprise smoke runs in Cursor lane T.

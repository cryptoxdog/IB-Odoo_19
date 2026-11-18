# ADR-131: Partner sites as native addresses; partner classification on native fields

**Status:** Accepted (operator, 2026-11-17)
**Decision date:** 2026-11-17
**Applies to:** `res.partner` as extended by `plasticos_facility_profile`, `plasticos_partner_import` (ERP sites), `plasticos_crm_sync` (VanillaSoft), `plasticos_crm_bridge` (opportunity hand-off), `plasticos_web_leads` (logistics record rule), `plasticos_base` (partner tags)
**Decision owner:** Operator (campaign C1, PlasticOS contacts / ERP sync realignment)
**Implementation owner:** the module named on each line below; phased PRs into `Staging`
**Related:** ADR-002 and ADR-003 (single) for what Odoo sends through Gate; ADR-021 for the ERP SQL import

Code references were checked against `Staging` at `42db406`. Where the decision changes what the code does today, the current behaviour is stated. Production counts come from a read-only Production probe run for this campaign; they are not reproduced from this repository.

## Context

- **ERP sites are stored as companies with a parent.** `plasticos_partner_import/models/erp_import_service.py:382` `_create_location` writes `is_company: True` with `parent_id` and a native `type` (`erp_import_service.py:399-403`; its docstring says "It is a company, not a second counterparty"). Production holds 1,266 such sites: 1,158 delivery and 108 invoice.
- **Standard Odoo treats a company partner as its own commercial entity.** Odoo 19 base `res.partner._compute_commercial_partner` stops at the first `is_company` record, so each site is its own commercial partner: its own receivables, payment terms, fiscal position and ledger. (Odoo core source is not in this repository; this is cited from Odoo 19 base `res_partner.py`, not verified at a line here.)
- **PlasticOS UI reads "site" as "company with a parent".** The campaign inventory counts about 139 such reads across 26 files. The largest are `plasticos_facility_profile/models/res_partner.py`, `plasticos_facility_profile/views/facility_profile_views.xml`, `plasticos_crm_bridge/models/crm_lead.py` and `plasticos_partner_import/models/partner_import_service.py`. There is no single predicate.
- **No document points at a site yet.** The read-only Production probe found 0 sale orders, purchase orders, invoices or pickings whose partner is a site. Production is not live yet, so the conversion is cheap now and expensive later.
- **Classification is spread over custom fields.** `plasticos_facility_profile/models/res_partner.py` declares Partner Type (`:53`), Facility Role (`:81`), Company Role (stored selection, `:97`/`:107`, synced to the native ranks by `_sync_rank_from_role`, `:131`), Company Roles (`plasticos.company.role.tag`, `:123`; model at `plasticos_facility_profile/models/company_role_tag.py:8`) and Trade Role (`:201`). `plasticos_base/data/material_taxonomy.xml` holds 108 material-taxonomy partner tags.

## Decision

### A. Sites become native delivery / invoice addresses

Each site is converted **in place** to `is_company = False` with `type = delivery` or `type = invoice`. Record ids do not change, so material profiles, facility profiles, ERP external ids (`legacy_erp_address_<AddressID>`) and site–person links stay attached.

Accepted impacts of the conversion:

| Impact | Effect |
|---|---|
| Commercial entity | The parent company becomes the site's commercial partner. New documents roll up to the parent. |
| Inherited commercial fields | The site takes the parent's payment terms, accounts, fiscal position, credit limit and VAT. |
| Address | The site keeps its own address. Only `type = contact` children copy the parent address. |
| Display name | Becomes "Parent, Site". |
| Defaults | Odoo's `address_get` will now offer a site as a sale-order delivery / invoice address; Decision E sets which one. |
| Logistics visibility | The rule `plasticos_web_leads/data/logistics_ir_rules.xml:36-48` (`rule_logistics_partner_confirmed_po`) admits every non-company partner, so logistics users see all sites. This is wanted. |
| Form | The Notes group and the Person/Company switch must be adjusted for a site. |

Rules that go with it:

- **"Site" is a third value of the stored `company_type`** beside Company and Person. No new field. The override is `plasticos_facility_profile/models/res_partner.py:24-38`; today it computes only `company` / `person` from `is_company`, and its inverse writes `is_company`. It gains a `site` value for a non-company partner with a parent and `type` delivery or invoice.
- **One predicate.** `res.partner._plasticos_is_site()` and `res.partner._plasticos_site_domain()` are the only definition of "site". Neither exists yet; the ~139 reads move onto them.
- **The address label has one meaning per case.** `plasticos_facility_profile/address_meaning.py:12` `address_type_meaning` becomes:

  | Case | Label |
  |---|---|
  | supplier site | Pick-Up Address |
  | buyer site | Delivery Address |
  | `type = invoice` | Mailing Address |
  | other roles | Site Address |
  | source label contains a PICK-UP token | Pick-Up Address (always) |

  Today the function returns "Pickup address", "Ship-to address", "Mailing address" and "Delivery" (`address_meaning.py:23-36`).
- **Persons keep Odoo's native address** (their company's). A person's Sites list shows the site addresses linked to them.
- **A site shows its contact's information.** The importer fills a site's blank phone and email from its single linked person. The Locations list gets a Contact column.
- **Sites run by a third party stay under the counterparty that owns the location in the historical ERP.** The operator of a site is not created as a company.
- **The ledger lives on the counterparty.** Invoice-type sites act as mailing / remit-to addresses.

### B. Classification on native fields; no new fields

- **Buyer / supplier / both** are the native `customer_rank` / `supplier_rank`, both set for a company that is both. The UI offers the filters Buyers, Suppliers, and Buyer & Supplier. The existing Company Role field (`res_partner.py:97`, stored selection today) becomes a computed **Trade Role** badge: Buyer, Supplier, Both.
- **Company Type** is native partner tags (`res.partner.category`) under one "Company Type" parent: Distribution Center, Commercial Recycler, Pallet Recycler, Compounder, Grinder/Processor, E-Waste, MRF, Manufacturer, Broker, Carrier, Exporter, Toll Processor. VanillaSoft is the authority. The tags of that group only are mirrored onto the company's sites and persons. On CRM leads they are native CRM tags (`crm.tag`) in a matching group.
- **Status tags** (Needs Enrichment, Do Not Contact, Key Account, Preferred Carrier) apply to companies and sites.
- **Buyer and Supplier partner tags are only partly changed.** A VanillaSoft rank write raises `customer_rank` and `supplier_rank` and the matching CRM tags. It does not attach `categ_buyer` or `categ_supplier`. A company-type tag such as Manufacturer still attaches. An ERP rank write still attaches the Buyer or Supplier partner category. The rest of that tag retirement is not done.
- **Retired later, not in this campaign:**
  - the 108 material-taxonomy partner tags (`plasticos_base/data/material_taxonomy.xml`) and the Expense partner tag;
  - Company Roles (`plasticos.company.role.tag`), Facility Role, Partner Type and the current Trade Role field, together with their Gate and matching readers. `plasticos_gate/services/gate_builders.py:207` `derive_subject_role` reads `company_role_tag_ids` and feeds `subject_role` (`gate_builders.py:333`). Retiring them changes what Odoo sends through Gate, so that step needs its own ADR under ADR-002 and ADR-003 (single).

### E. Sale-order delivery address

- New sale orders default the delivery address to the buyer's most recently used one.
- The opportunity hand-off names the facility as the draft sale order's customer and as its delivery address. `partner_id` and `partner_shipping_id` are that facility (`parties["ship_to"]`). `plasticos.transaction.buyer_id` stays the buyer company. The ownership check still requires the facility to belong to that company.

## Consequences

- One commercial entity per counterparty: receivables, credit and fiscal position are read on the company, not split across its sites.
- "Site" has one definition (`_plasticos_is_site` / `_plasticos_site_domain`) instead of ~139 local readings of `is_company` plus `parent_id`.
- Classification uses Odoo's own ranks and tags, so standard filters, reports and imports work without PlasticOS fields.
- Readers of the retired classification fields keep working until the later campaign; Gate payloads do not change in C1.
- A site created after the conversion by any path that still writes `is_company = True` would reintroduce the old shape. The importer (`_create_location`) changes in the same rollout.

## Rollout

1. Phased PRs into `Staging`: predicate and `company_type` value; importer and in-place conversion; address labels and form; classification tags and Trade Role badge; sale-order defaults and the hand-off.
2. One Production partner replay (`make import-erp PARTNERS_ONLY=1`) before go-live, with a fail-closed summary.
3. Enterprise runtime verification in Cursor on the pinned fixture (`config/test_env_fixture.conf`).

## Alternatives rejected

- **Keep sites as companies and override the commercial entity.** Touches core accounting (commercial partner, receivables, fiscal position) for a shape Odoo already models natively.
- **New fields for site, role or company type.** Rejected by the operator; native fields and tags cover every case above.

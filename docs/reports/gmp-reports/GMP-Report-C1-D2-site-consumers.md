# GMP Report C1-D2 — site consumers

Campaign C1, lane D2. Branch `feat/c1-d2-site-consumers`, from `origin/feat/c1-d1-site-core`
(`be4cc57`, PR #524). Decision record: ADR-131 (PR #520).

## Phase 0 — Plan

Make every consumer of "site" use the D1 contract (`res.partner._plasticos_is_site()`,
`_plasticos_site_domain()`, stored `company_type == 'site'`) so code works for both site
shapes: a company record parented under a company (today's ERP data) and a native
delivery/invoice address (after the ADR-131 data phase). A site is never the commercial
entity.

Modules: `plasticos_intake`, `plasticos_crm_bridge`, `plasticos_crm_sync`,
`plasticos_web_leads`. `plasticos_security_base` is not changed (see Phase 6).

## Phase 1 — Baseline

D1 head `be4cc57`. Finding before any edit: Odoo's `commercial_partner_id` stops at the first
record with `is_company` set, so for the company-shaped site it is the site itself. Using it
as "the buyer company" would issue the sale order to the site for all current data. The
lane therefore adds one owning-company walk instead.

## Phase 2 — Implement

| File | Change |
|---|---|
| `plasticos_intake/partner_site.py` (new) | `site_company(partner)`: first ancestor-or-self that is a company and not a site (pure) |
| `plasticos_intake/models/res_partner_intake.py` | `res.partner._plasticos_site_company()` delegates to it |
| `plasticos_intake/models/intake.py` | `facility_id` domain: the company or its sites (`company_type = 'site'`), not its people; `contact_id` domain excludes sites; facility onchange searches `_plasticos_site_domain()` |
| `plasticos_crm_bridge/release_parties.py` (new) | `release_parties(supplier, buyer_facility)` → customer (buyer company), ship-to (facility), vendor (supplier company) |
| `plasticos_crm_bridge/models/crm_lead.py` | `action_submit_release`: purchase order and transaction supplier = supplier company; sale order `partner_id` = buyer company, `partner_shipping_id` = facility; refused when the facility's company is not the selected Buyer Company. Reach-person computes treat a site as a location (`_is_location`); `partner_id.type` added to their depends. Lead→intake conversion: `facility_id` set when the partner is a site (predicate) |
| `plasticos_crm_bridge/models/facility_profile.py` | `link_verified_location` accepts a delivery-shaped site |
| `plasticos_crm_sync/services/orchestrator.py` | `_verified_company` → owning company, never a site; `_facility_for_material` finds sites by predicate; an approved ERP marker pointing at a site is refused like one pointing at a company |
| `plasticos_web_leads/data/logistics_ir_rules.xml` | logistics rule also shows `company_type = 'site'` (company-shaped sites were hidden without their own POs); delivery-shaped sites were already visible |
| four manifests + README version lines | crm_bridge 19.0.3.7.6, crm_sync 19.0.1.9.31, intake 19.0.5.5.1, web_leads 19.0.2.11.8 |

### `is_company` decisions in `plasticos_crm_bridge`

| Location | Meaning | Decision |
|---|---|---|
| `_REACH_PERSON_DEPENDS` (`partner_id.is_company`, child/parent `is_company`) | trigger | kept; `partner_id.type` added |
| `partner_is_company` related + view `crm_lead_views.xml` Personal Intel | "not an individual" | **kept**: the runtime test `test_crm_lead_personal_intel_view` asserts the related value; a delivery site shows the page until a follow-up |
| `release_buyer_company_id` domain `is_company = True` | buyer company | kept (company); submit now refuses a facility owned by another company |
| `_compute_contact_name/email_from/function/phone`, `_plasticos_mirrored_person_value`, `_plasticos_fill_mobile_from_person` | "a location, not a person" | → company **or site** |
| `_find_matching_partner`, `_find_or_create_partner_from_lead` (`is_company` + `parent_id = False`) | top-level company | kept |
| lead→intake `partner.is_company and partner.parent_id` | site | → `_plasticos_is_site()` |
| `facility_profile.link_verified_location` | site or company location | → company or site |
| `opportunity_approval._check_lot_identity` (`not is_company and not parent_id`) | company or one of its sites | kept: a delivery site has a parent and already passes |
| `intake.partner_id` / `intake_match.buyer_id` domains `is_company = True` | the company | kept |

## Phase 3 — Enforce

`ruff check` / `ruff format` (0.16.0) clean; `ci/check_odoo19_xml.py` and
`scripts/check_module_wiring.py` pass. No new field or model; no ACL change.

## Phase 4 — Validate

`tests/test_c1_site_consumers.py` (21, pure): owning company for both shapes and people;
release parties for 2 facility × 4 supplier shapes; submit wiring; `_verified_company` returns
the parent for a site; `_facility_for_material` finds a delivery-shaped site; intake facility
domain accepts the company and both site shapes and rejects a person; contact domain never
offers a site; logistics rule shows both shapes and still hides a company without POs.
Full pure suite: see the PR. Odoo runtime / Enterprise smoke: lane T.

## Phase 5 — Recursive verify

Diff limited to the four owned modules, two new pure helpers, one test file and this
report. `plasticos_facility_profile` (D1) and `plasticos_partner_import` (lane E) untouched.

## Phase 6 — Finalize / open items

- **Not done: `plasticos_security_base/views/res_partner_views.xml` Notes group on sites.**
  `CLAUDE.md` / `AGENTS.md` list `plasticos_security_base` as ask-first; the operator's
  confirmation reached this session only relayed through another session. The change is one
  attribute (`invisible="not is_company"` → `invisible="not is_company and company_type != 'site'"`).
- The logistics record-rule change was made under operator decision D16 relayed by the CTO
  session; it is listed here for explicit review.
- Personal Intel page on a delivery-shaped site: see the decision table.

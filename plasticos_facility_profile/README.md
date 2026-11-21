---
auto_generated: false
authority: derived-index
component_id: plasticos_facility_profile
component_name: PlasticOS Facility Profile
module_version: 19.0.5.7.1
layer: 2
installable: true
auto_install: true
application: false
depends:
  - base
  - contacts
  - mail
  - sale_management
  - utm
  - plasticos_base
  - plasticos_material_profile
models_owned:
  - plasticos.facility.profile
  - plasticos.capability
  - plasticos.capability.type
  - plasticos.partner.type
  - plasticos.partner.phone
  - plasticos.lead.source.utils
models_extended:
  - res.partner
  - plasticos.material.profile
crons: []
---

# PlasticOS Facility Profile

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Records what a facility can physically handle: capabilities, tolerances, and operating details. It also owns several partner-level fields: the facility flag, the trade-facing company role, the partner type, extra phone numbers, and the dock rule.

## How it works

- **Capability profile.** `plasticos.facility.profile` (`models/facility_profile.py`) belongs to one partner (`partner_id`, `ondelete="cascade"`). The field's domain offers partners that have a parent. `_check_partner_is_facility` refuses a save when the partner's `is_facility` is false. What the site can do is `plasticos.capability` lines, not equipment flags.
- **Reference data.** `plasticos.partner.type` is a master list seeded in `data/partner_type_data.xml`.
- **Partner fields.** The `res.partner` extension (`models/res_partner.py`):
  - stores `company_type` so it can be searched;
  - recomputes `is_facility` as a stored field: a child company, or a standalone company with no company children;
  - owns `company_role` (buyer, supplier, carrier, broker, internal, prospect, other). On create and write, `_sync_rank_from_role` sets `supplier_rank` for supplier and broker and `customer_rank` for buyer when they are zero;
  - links `partner_type_id`, `facility_role`, `preferred_contact_id`, and `facility_profile_ids`;
  - refuses to clear `parent_id` on a partner that still has a capability profile.
- **Capabilities.** `plasticos.capability.type` is the seeded verb list (`data/capability_type_data.xml`, `noupdate="1"`). `plasticos.capability` is one machine or line on a facility profile, ordered by drag, with type-specific detail fields. `capability_id` and `rate_lb_hr` are added on `plasticos.material.profile`. A site with exactly one capability links its unlinked profiles; an explicit blank link stays blank.
- **Site logistics.** `models/res_partner_site_logistics.py` adds loading docks, export container loading, truck scale, dock-rule confirmation date, and shipping hours, with no defaults. Blank means unknown. The partner form shows them, the dock rule, and the time zone on a site and on a company with no sites.
- **Dock rule.** `models/res_partner_delivery_term.py` adds `default_delivery_term` (appointment or first come, first served) to every partner. The Appointment default is unchanged.
- **Phones.** `plasticos.partner.phone` stores numbers beyond the one Odoo keeps on the partner (mobile, other, fax).
- **Lead source.** `plasticos.lead.source.utils` is an abstract helper that maps raw lead-source values onto native `utm.source` records. UTM sources are seeded in `data/utm_source_data.xml`.
- **Address meaning.** `address_meaning.py` returns the plain-language meaning shown beside a partner's address type.

## Models

| Model                         | Kind            | File                                             |
| ----------------------------- | --------------- | ------------------------------------------------ |
| `plasticos.facility.profile`  | owned           | `models/facility_profile.py`                     |
| `plasticos.capability`        | owned           | `models/capability.py`                           |
| `plasticos.capability.type`   | owned           | `models/capability_type.py`                      |
| `plasticos.partner.type`      | owned           | `models/partner_type.py`                         |
| `plasticos.partner.phone`     | owned           | `models/partner_phone.py`                        |
| `plasticos.lead.source.utils` | owned, abstract | `models/lead_source.py`                          |
| `res.partner`                 | extended        | `res_partner.py`, `res_partner_delivery_term.py`, `res_partner_site_logistics.py` |
| `plasticos.material.profile`  | extended        | `models/material_profile.py`                     |

## Runtime

- No cron, no install hook.
- `auto_install` is true. `category` is `Hidden`.
- Views: partner types, capability profile forms, and partner form changes under `views/`.
- Upgrade `19.0.5.7.0` moves stored equipment, process and accepted-polymer values onto capabilities and inbound material profiles, then drops those columns. The review list is `plasticos_facility_capability_migration_review`.

## Boundaries

- No outbound call. This module does not sync to a graph engine and makes no HTTP request.
- No pricing. It holds no buy or sell price and does not feed matching by itself.
- A facility profile is optional for a material profile. CRM ownership and facility merges are added by `plasticos_crm_bridge`.
- Depends only on the Odoo modules above and `plasticos_material_profile`.

## Read next

- [`models/facility_profile.py`](models/facility_profile.py)
- [`models/res_partner.py`](models/res_partner.py)
- [`../plasticos_crm_bridge/README.md`](../plasticos_crm_bridge/README.md)

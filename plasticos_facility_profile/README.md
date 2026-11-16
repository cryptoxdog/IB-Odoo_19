---
auto_generated: false
authority: derived-index
component_id: plasticos_facility_profile
component_name: PlasticOS Facility Profile
module_version: 19.0.5.4.15
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
  - plasticos_material_profile
models_owned:
  - plasticos.facility.profile
  - plasticos.facility.template
  - plasticos.equipment.type
  - plasticos.partner.type
  - plasticos.partner.phone
  - plasticos.lead.source.utils
models_extended:
  - res.partner
crons: []
---

# PlasticOS Facility Profile

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Records what a facility can physically handle: equipment, forms and processes, tolerances, and operating details. It also owns several partner-level fields: the facility flag, the trade-facing company role, the partner type, extra phone numbers, and the dock rule.

## How it works

- **Capability profile.** `plasticos.facility.profile` (`models/facility_profile.py`) belongs to one partner (`partner_id`, `ondelete="cascade"`). The field's domain offers partners that have a parent. `_check_partner_is_facility` refuses a save when the partner's `is_facility` is false. Further constraints check density and melt-index ranges.
- **Selections from material profile.** Form and process selections are imported lazily, inside functions, from `plasticos_material_profile.form_codes` and `plasticos_material_profile.process_codes`.
- **Templates.** `plasticos.facility.template` holds a preset. `get_template_values()` returns the equipment and capability flags to copy onto a profile and counts its use. Presets load from `data/facility_template_data.xml`.
- **Reference data.** `plasticos.equipment.type` and `plasticos.partner.type` are master lists seeded in `data/equipment_type_data.xml` and `data/partner_type_data.xml`.
- **Partner fields.** The `res.partner` extension (`models/res_partner.py`):
  - stores `company_type` so it can be searched;
  - recomputes `is_facility` as a stored field: a child company, or a standalone company with no company children;
  - owns `company_role` (buyer, supplier, carrier, broker, internal, prospect, other). On create and write, `_sync_rank_from_role` sets `supplier_rank` for supplier and broker and `customer_rank` for buyer when they are zero;
  - links `partner_type_id`, `facility_role`, `preferred_contact_id`, and `facility_profile_ids`;
  - refuses to clear `parent_id` on a partner that still has a capability profile.
- **Dock rule.** `models/res_partner_delivery_term.py` adds `default_delivery_term` (appointment or first come, first served) to every partner.
- **Phones.** `plasticos.partner.phone` stores numbers beyond the one Odoo keeps on the partner (mobile, other, fax).
- **Lead source.** `plasticos.lead.source.utils` is an abstract helper that maps raw lead-source values onto native `utm.source` records. UTM sources are seeded in `data/utm_source_data.xml`.
- **Address meaning.** `address_meaning.py` returns the plain-language meaning shown beside a partner's address type.

## Models

| Model                         | Kind            | File                                             |
| ----------------------------- | --------------- | ------------------------------------------------ |
| `plasticos.facility.profile`  | owned           | `models/facility_profile.py`                     |
| `plasticos.facility.template` | owned           | `models/facility_template.py`                    |
| `plasticos.equipment.type`    | owned           | `models/equipment_type.py`                       |
| `plasticos.partner.type`      | owned           | `models/partner_type.py`                         |
| `plasticos.partner.phone`     | owned           | `models/partner_phone.py`                        |
| `plasticos.lead.source.utils` | owned, abstract | `models/lead_source.py`                          |
| `res.partner`                 | extended        | `res_partner.py`, `res_partner_delivery_term.py` |

## Runtime

- No cron, no install hook.
- `auto_install` is true. `category` is `Hidden`.
- Views: partner types, templates, capability profile forms, and partner form changes under `views/`.

## Boundaries

- No outbound call. This module does not sync to a graph engine and makes no HTTP request.
- No pricing. It holds no buy or sell price and does not feed matching by itself.
- A facility profile is optional for a material profile. CRM ownership and facility merges are added by `plasticos_crm_bridge`.
- Depends only on the Odoo modules above and `plasticos_material_profile`.

## Read next

- [`models/facility_profile.py`](models/facility_profile.py)
- [`models/res_partner.py`](models/res_partner.py)
- [`../plasticos_crm_bridge/README.md`](../plasticos_crm_bridge/README.md)

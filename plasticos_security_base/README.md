---
auto_generated: false
authority: derived-index
component_id: plasticos_security_base
component_name: Plasticos — Security Base
module_version: 19.0.1.2.28
layer: 1
installable: true
auto_install: true
application: false
depends:
  - base
  - plasticos_base
  - base_geolocalize
  - sale
  - purchase
  - purchase_stock
  - account
  - stock
  - plasticos_transaction
  - plasticos_partner_import
  - plasticos_intake
  - plasticos_material_profile
  - plasticos_facility_profile
  - plasticos_offer
  - plasticos_logistics
  - plasticos_documents
  - plasticos_automation
  - plasticos_web_leads
models_owned: []
models_extended:
  - res.partner
  - plasticos.partner.bulk.update.wizard
crons: []
---

# Plasticos — Security Base

The front matter above is a derived index. `__manifest__.py` and the `_inherit` lines in `models/` win on any conflict.

## What it does

Defines the PlasticOS business roles, the record rules that limit what each role sees, and the private-contact flag on partners.

## How it works

- **Groups.** `security/security_groups.xml` defines eight groups: `group_sales_rep`, `group_logistics`, `group_accounting`, `group_logistics_ops`, `group_qc_manager`, `group_accounting_ops`, `group_operations_manager`, and `group_system_admin`. The manifest description's "three business roles" (Sales Rep, Logistics, Accounting) is the short list.
- **Record rules.** `security/record_rules.xml` holds eleven `ir.rule` records:
  - private partners and their extra phone numbers (`plasticos.partner.phone`);
  - sales-rep row limits on `plasticos.transaction`, `sale.order`, `purchase.order`, `account.move`, and `plasticos.load`;
  - company isolation on `plasticos.load`;
  - own-rows for reps and all-rows for logistics and operations managers on `plasticos.load.dashboard`.
- **Export container grants (S9).** `security/ir.model.access.csv` grants `group_logistics` and `group_operations_manager` read, write and create (no unlink) on `plasticos.shipment.event.proposal`, and read and create (no write, no unlink) on the append-only `plasticos.iso.journey.fact`. Sales reps get neither. The commands still require `group_logistics`.
- **Linda approvals (S11).** `group_logistics` and `group_operations_manager` read `plasticos.linda.approval` (no write, create or unlink; Approve and Reject decide it). Only an Operations Manager who is not Linda can decide one. `security/record_rules.xml` also grants `plasticos_logistics.user_linda` the Logistics group and no other business group.
- **Private contacts.** The `res.partner` extension adds `is_private`. Its help text says a private contact is visible only to its creator and to system administrators, but the enforcing rule is narrower. `rule_partner_private` limits private partners to their creator for users in `group_sales_rep`, `group_logistics`, or `group_accounting`, including users who inherit those groups. It has no administrator exemption, so a PlasticOS system administrator, who inherits logistics and accounting through `group_operations_manager`, is held to the same creator-only domain. A user in none of the three groups (for example, `group_qc_manager` only) is not restricted by it. The `plasticos.partner.bulk.update.wizard` extension (the wizard is owned by `plasticos_partner_import`) writes `is_private` in bulk and posts the old and new status, the reason, and the user to the partner's chatter.
- **Install hook.** `post_init_hook` calls `grant_seed_user_groups`, which assigns groups to the seed users with SQL on the relation table, because Odoo 19 removed `groups_id` from XML user creation.
- **Access rows.** `security/ir.model.access.csv` holds this module's access rows.

## Models

| Model                                  | Kind                | File                                   |
| -------------------------------------- | ------------------- | -------------------------------------- |
| `res.partner`                          | extended            | `models/res_partner.py`                |
| `plasticos.partner.bulk.update.wizard` | extended, transient | `models/partner_bulk_update_wizard.py` |

The module defines no model of its own.

## Runtime

- No cron.
- `auto_install` is true.

## Layer and dependencies

`AGENTS.md` places this module in Layer 1. Its `depends` reach Layer 2 to Layer 5 modules (transaction, logistics, documents, automation, web leads, and others) because its record rules name their models. The manifest keeps `plasticos_matching` as a commented-out line, so matching is not a dependency.

## Boundaries

- Each model's own access rows stay in the module that defines the model.
- No business logic beyond the privacy flag.

## Read next

- [`security/security_groups.xml`](security/security_groups.xml)
- [`security/record_rules.xml`](security/record_rules.xml)
- [`hooks.py`](hooks.py)

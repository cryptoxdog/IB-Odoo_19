---
auto_generated: false
authority: derived-index
component_id: plasticos_material_profile
component_name: PlasticOS Material Profile
module_version: 19.0.5.12.0
layer: 1
installable: true
auto_install: true
application: false
depends:
  - plasticos_base
  - base
  - contacts
  - mail
  - purchase
  - sale_management
  - product
models_owned:
  - plasticos.material.profile
  - plasticos.polymer
  - plasticos.material.grade
  - plasticos.material.form
  - plasticos.material.color
  - plasticos.source.type
  - plasticos.material.attribute
  - plasticos.process.type
  - plasticos.packaging.type
  - plasticos.filler.type
  - plasticos.grade.template
models_extended:
  - res.partner
crons: []
---

# PlasticOS Material Profile

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

The material master. It holds the canonical registries (polymer, grade, form, color, source type, attribute, process type, packaging type, filler type) and one material profile per partner and material: what that partner handles and in what condition.

## How it works

- **Profile.** `plasticos.material.profile` (`models/material_profile.py`) belongs to a partner (`partner_id`, required, `ondelete="cascade"`) and names a required `polymer_id`, plus form, grade, color, source type, attributes, quality (melt flow, density, moisture, contamination), volume, filler, and condition flags. A facility profile is not required.
- **Identity.** A unique index on `(partner_id, polymer_id, form_id, material_grade_id)` with `NULLS NOT DISTINCT` allows one profile per partner for each combination. `_check_unique_triple_before_save` gives a readable error before the insert. The profile has no `name` field; its label is `display_name`.
- **Registries.** Each registry is its own model, seeded from XML under `data/` (`polymer_data.xml`, `material_form_data.xml`, `material_grade_data.xml`, and the others).
- **Code registries in Python.** `process_codes.py` is the import site for `PROCESS_SELECTION`; other modules import it from here. `form_codes.py` and `grade_codes.py` hold the form and grade codes. A grade is what the items were before processing (drums, totes, pallets); a form is the physical form. Tests keep these tuples equal to the seed files.
- **Grade templates.** `plasticos.grade.template` holds preset specifications that fill a profile's fields when chosen.
- **Helpers.** `intake_delta_bridge.py` maps intake fields onto profile fields (used by `plasticos_intake`). `profile_features.py` derives features such as residue without the Odoo registry. `grade_migration.py` moves former forms onto grades during the grade upgrade.
- **Partner.** The `res.partner` extension adds `material_profile_ids`, a profile count, and a non-stored `is_facility` (true for a child partner or a partner with no children). `plasticos_facility_profile` overrides `is_facility` with a stored version.
- **Orders.** `action_create_purchase_order` opens a purchase order with a line from the profile; it needs `plasticos_order_lines` for the line's `material_profile_id`. `action_view_po_lines` and `action_view_so_lines` list order lines.
- **Packet stub.** Create and write call `_emit_material_packet()`, which builds a packet dictionary and discards it. Nothing is sent.

## Models

| Model                          | Kind     | File                           |
| ------------------------------ | -------- | ------------------------------ |
| `plasticos.material.profile`   | owned    | `models/material_profile.py`   |
| `plasticos.polymer`            | owned    | `models/polymer.py`            |
| `plasticos.material.grade`     | owned    | `models/material_grade.py`     |
| `plasticos.material.form`      | owned    | `models/material_form.py`      |
| `plasticos.material.color`     | owned    | `models/material_color.py`     |
| `plasticos.source.type`        | owned    | `models/source_type.py`        |
| `plasticos.material.attribute` | owned    | `models/material_attribute.py` |
| `plasticos.process.type`       | owned    | `models/process_type.py`       |
| `plasticos.packaging.type`     | owned    | `models/packaging_type.py`     |
| `plasticos.filler.type`        | owned    | `models/filler_type.py`        |
| `plasticos.grade.template`     | owned    | `models/grade_template.py`     |
| `res.partner`                  | extended | `models/res_partner.py`        |

## Runtime

- No cron, no install hook.
- `data/material_mapping*.csv` are mapping and resolution ledgers kept beside the seed data; they are not in the manifest `data` list.
- `auto_install` is true.

## Boundaries

- Layer 1: no dependency on intake, matching, offers, or transactions.
- No outbound call. The packet stub builds a dictionary only.
- Partner roles use native `customer_rank` / `supplier_rank`; this module adds no partner role booleans.

## Read next

- [`models/material_profile.py`](models/material_profile.py)
- [`process_codes.py`](process_codes.py)
- [`../docs/adr/ADR-004-intake-vs-material-profile-domain-split.md`](../docs/adr/ADR-004-intake-vs-material-profile-domain-split.md)

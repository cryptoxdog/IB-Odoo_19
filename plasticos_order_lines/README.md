---
auto_generated: false
authority: derived-index
component_id: plasticos_order_lines
component_name: PlasticOS Order Lines
module_version: 19.0.1.1.4
layer: 3
installable: true
auto_install: true
application: false
depends:
  - purchase
  - sale
  - sale_management
  - plasticos_material_profile
  - plasticos_product
models_owned: []
models_extended:
  - sale.order.line
  - purchase.order.line
  - plasticos.material.profile
crons: []
---

# PlasticOS Order Lines

The front matter above is a derived index. `__manifest__.py` and the `_inherit` lines in `models/` win on any conflict.

## What it does

Puts the material specification on sale and purchase order lines: which material profile a line comes from, its grade, color, form, packaging, source, filler, and attributes, and a readable material description.

## How it works

- **Line fields.** `sale.order.line` (`models/sale_order_line.py`) and `purchase.order.line` (`models/purchase_order_line.py`) each get `material_profile_id` plus `material_grade_id`, `color_ids`, `form_id`, `packaging_type_id`, `source_type_id`, `filler_type_id`, and `material_attribute_ids`.
- **Fill from the profile.** Choosing a material profile on a line fills those fields from the profile, sets the product from the profile polymer's product (`plasticos_product`) when there is one, and recomputes the line name. The user can still edit them.
- **Description.** `material_description` is a stored compute: the product name, then the line's specs, joined with dashes. The text comes from `projected_material()` in `models/material_label.py`, a plain function, not a model. A trailing parenthetical on the product name is dropped so a color is not repeated.
- **Printed text.** Sale lines print the material description above Odoo's product description (`_get_sale_order_line_multiline_description_sale`). Purchase lines do the same through `_get_product_purchase_description`.
- **From the profile side.** The `plasticos.material.profile` extension overrides `_purchase_line_description` so a purchase order created from a profile uses the line's material description.
- **Navigation.** `action_view_material_profile()` on both line models opens the linked profile.

## Models

| Model                        | Kind     | File                            |
| ---------------------------- | -------- | ------------------------------- |
| `sale.order.line`            | extended | `models/sale_order_line.py`     |
| `purchase.order.line`        | extended | `models/purchase_order_line.py` |
| `plasticos.material.profile` | extended | `models/material_profile.py`    |

The module defines no model of its own.

## Runtime

- No cron, no install hook, no seed data.
- Views extend the sale and purchase order forms (`views/`).
- `auto_install` is true.

## Boundaries

- It does not price, confirm, or create orders.
- It does not change the material profile; it copies from it.

## Read next

- [`models/sale_order_line.py`](models/sale_order_line.py)
- [`models/material_label.py`](models/material_label.py)
- [`../plasticos_material_profile/README.md`](../plasticos_material_profile/README.md)

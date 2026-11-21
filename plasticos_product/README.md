---
auto_generated: false
authority: derived-index
component_id: plasticos_product
component_name: PlasticOS Product Catalog
module_version: 19.0.1.0.4
layer: 1
installable: true
auto_install: true
application: false
depends:
  - product
  - plasticos_material_profile
models_owned: []
models_extended:
  - product.product
  - product.template
  - plasticos.polymer
crons: []
---

# PlasticOS Product Catalog

The front matter above is a derived index. `__manifest__.py` and the `_inherit` lines in `models/` win on any conflict.

## What it does

Keeps one Odoo product per polymer. The product stands for the polymer only; color, form, packaging, source, filler, and attributes live on the order lines (`plasticos_order_lines`).

## How it works

- **Polymer to product.** The `plasticos.polymer` extension adds `product_id`, a read-only Many2one to `product.template`. Creating a polymer calls `_ensure_product()`, which creates a consumable template named after the polymer, with `polymer_id` set and `is_polymer_product` true.
- **Sync.** Writing `name` or `full_name` on a polymer calls `_sync_product()`, which writes the polymer's name and description onto its product. That keeps the product aligned with the polymer.
- **Backfill.** `action_create_products()` creates missing products for a set of polymers. `post_init_hook` in `hooks.py` runs it for every polymer without a product at install.
- **Template fields.** `product.template` gets `polymer_id` and `is_polymer_product`.
- **Display name.** `product.product` and `product.template` compute `display_name` without the internal reference prefix. The grade number stays on `default_code`.
- **Seed data.** `data/product_category_data.xml` and `data/product_data.xml`.

## Models

| Model               | Kind     | File                         |
| ------------------- | -------- | ---------------------------- |
| `product.product`   | extended | `models/product_template.py` |
| `product.template`  | extended | `models/product_template.py` |
| `plasticos.polymer` | extended | `models/product_template.py` |

The module defines no model of its own.

## Runtime

- No cron.
- `post_init_hook` creates products for existing polymers.
- `auto_install` is true.

## Boundaries

- One product per polymer. Material detail beyond the polymer is not encoded in products.
- No pricing.

## Read next

- [`models/product_template.py`](models/product_template.py)
- [`../plasticos_order_lines/README.md`](../plasticos_order_lines/README.md)
- [`../plasticos_material_profile/README.md`](../plasticos_material_profile/README.md)

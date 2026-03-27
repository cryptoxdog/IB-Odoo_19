# plasticos_material_profile

**Version:** 19.0.4.2.0
**Category:** PlasticOS / Master Data
**Depends:** `plasticos_base`

---

## Purpose

Owns the **canonical material master registries** for PlasticOS: polymer types, material forms, colors, source types, process codes, and all master data that defines what a material *is*. Every other module that classifies materials depends on this one.

Also manages `plasticos.material.profile` — the structured material capability record attached to a partner (buyer or supplier) that captures their material preferences, tolerances, and specifications.

---

## Registries Owned

### `process_codes.py` — `PROCESS_SELECTION`

**Canonical source for all process type selection lists.** Located at `plasticos_material_profile/process_codes.py`.

Import pattern used by all consumers:
```python
from odoo.addons.plasticos_material_profile.process_codes import PROCESS_SELECTION
```

> **History:** Previously lived in `plasticos_facility_profile`. Moved here to eliminate a circular dependency (`plasticos_facility_profile` depends on `plasticos_material_profile` — the reverse import would be circular). All 3 in-repo consumers updated. External consumers in `plasticos_buyer_match_engine` / `plasticos_inference_engine` will be updated when those microservice repos are wired.

### Master Data Models

| Model | Description |
|---|---|
| `plasticos.polymer` | Polymer type master (HDPE, LDPE, PP, PET, etc.) |
| `plasticos.material.form` | Material form (Pellets, Regrind, Flake, Film, etc.) |
| `plasticos.material.color` | Color classification |
| `plasticos.source.type` | Material origin/source type |
| `plasticos.material.attribute` | Attribute tags (with_metal, metalized, flame_retardant, etc.) |
| `plasticos.process.type` | Process type master records |
| `plasticos.filler.type` | Filler type master (fiberglass, talc, carbon black, etc.) |

---

## Model: `plasticos.material.profile`

Structured material record attached to a `res.partner`. Identity is defined by `(partner_id, polymer_id)` — there is **no `name` field**.

> **Critical:** Do not attempt to set `name` in `create()` vals — `plasticos.material.profile` has no `name` field. The ORM will raise `ValueError: Invalid field 'name' in 'plasticos.material.profile'`. Profile display uses `display_name` (falls back to `polymer_id.name + partner_id.name`).

### Key Fields

| Field | Type | Notes |
|---|---|---|
| `partner_id` | `Many2one(res.partner)` | Determines profile ownership |
| `polymer_id` | `Many2one(plasticos.polymer)` | |
| `form_id` | `Many2one(plasticos.material.form)` | |
| `origin_form_id` | `Many2one(plasticos.material.form)` | What the material was before processing — distinct from `form_id` |
| `origin_process_type` | `Selection(PROCESS_SELECTION)` | From `process_codes.py` |
| `color_id` | `Many2one(plasticos.material.color)` | |
| `source_type_id` | `Many2one(plasticos.source.type)` | |
| `material_attribute_ids` | `Many2many(plasticos.material.attribute)` | Single source of truth for condition flags |
| `has_metal` | `Boolean` | **Computed** from `material_attribute_ids` — `store=True` |
| `is_metalized` | `Boolean` | **Computed** from `material_attribute_ids` — `store=True` |
| `has_fr` | `Boolean` | **Computed** from `material_attribute_ids` — `store=True` |
| `moisture_percent` | `Float` | |
| `contamination_percent` | `Float` | |
| `melt_flow_index` | `Float` | |
| `density` | `Float` | |
| `filler_type_id` | `Many2one(plasticos.filler.type)` | |
| `filler_pct` | `Float` | |
| `previously_washed` | `Boolean` | |
| `previously_pelletized` | `Boolean` | |

### `is_facility` Computed Field

`models/res_partner.py` adds `is_facility` to every `res.partner`:

```python
is_facility = fields.Boolean(
    compute='_compute_is_facility',
    store=True, index=True
)
```

Logic mirrors the facility profile constraint: child partners → True; standalone companies (no children) → True; parent companies with children → False; person contacts → False.

**This field is the source of truth** used by `plasticos_facility_profile` views to control Facility Profile tab visibility. Do not redefine it in `plasticos_facility_profile`.

### Boolean Flags — History

`has_metal`, `is_metalized`, `has_fr` were previously stored fields with bidirectional `onchange` sync (± `material_attribute_ids`). That pattern was removed — booleans are now **computed** from attributes. `material_attribute_ids` is the single source of truth.

**`has_residue` was deliberately left** as a computed field from `contamination_pct` — different semantic, different pattern. Not attribute-synced.

### `emit_material_packet()`

Builds the material capability packet dict for CEG sync:

```python
{
    "polymer": rec.polymer_id.code,
    "form": rec.form_id.code,
    "source_type_name": rec.source_type_id.name,
    "origin_process": rec.origin_process_type,
    "condition": {
        "has_metal": rec.has_metal,
        "is_metalized": rec.is_metalized,
        "has_fr": rec.has_fr,
    },
    "filler": {
        "type": rec.filler_type_id.code if rec.filler_type_id else None,
        "pct": rec.filler_pct,
    },
    # ... full packet
}
```

---

## `plasticos.material.attribute`

Master tag model for material condition flags.

| Field | Notes |
|---|---|
| `code` | Machine-readable code (`with_metal`, `metalized`, `flame_retardant`, etc.) |
| `name` | Display label |

> **Cleanup note:** `boolean_field` and `boolean_value` metadata fields were removed from this model — they referenced the deleted boolean sync onchanges and were vestigial. The XML data file was also cleaned.

---

## Constraint

```python
@api.constrains('partner_id')
def _check_partner_is_facility(self):
    # Profiles may only be created for partners where is_facility = True
```

After the boolean cleanup, this constraint was updated to use `is_facility` (from `plasticos_material_profile.res_partner`) instead of `parent_id`. Standalone companies can now have material profiles.

---

## Security

- `ir.model.access.csv` — full ACL for all registry models
- No record rules — master data is globally readable by all authenticated users

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_material_profile --stop-after-init
```


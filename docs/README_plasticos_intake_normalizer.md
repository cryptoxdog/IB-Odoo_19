# plasticos_intake_normalizer

**Version:** 19.0.2.0.0
**Category:** PlasticOS / Data Processing
**Depends:** `plasticos_base`, `plasticos_intake`, `plasticos_material_profile`, `plasticos_facility_profile`

---

## Purpose

Normalizes raw intake form data into a structured, typed packet suitable for the Cognitive Engine Graph (CEG) and downstream matching logic. This module adds the **Normalization tab** to the intake form and owns the `assemble_packet()` method.

Think of this module as the intake data adapter — it translates human-entered form values (text, selections, floats) into a clean, schema-validated dict that the CEG can consume.

---

## Model: `plasticos.intake.normalizer`

Extends `plasticos.intake` via `_inherit`.

### Key Method: `assemble_packet()`

Builds the CEG query payload from the current intake record. Called by `action_match_to_buyers()` before the HTTP POST.

**Packet structure:**

```python
{
    "polymer": self.polymer_id.code,
    "form": self.form_id.code,
    "origin_form": self.origin_form_id.code if self.origin_form_id else None,
    "origin_process": self.origin_process_type,
    "source_type": self.source_type_id.name if self.source_type_id else None,
    "volume": {
        "qty_per_load_lbs": self.quantity_per_load_lbs,
        "loads_per_month": self.loads_per_month,
    },
    "quality": {
        "mfi_value": self.mfi_value or None,
        "density_value": self.density_value or None,
        "moisture_pct": self.moisture_pct or None,      # ← correct field name (was moisture_ppm — fixed)
        "contamination_total_pct": self.contamination_total_pct or None,
    },
    "condition": {
        "material_attributes": self.material_attribute_ids.mapped('code'),
    },
    "geo": {
        "lat": self.lat,
        "lon": self.lon,
    },
    "target_price": self.target_price,
}
```

**Critical fix history:** Line 395 previously referenced `self.moisture_ppm` — field does not exist on `plasticos.intake`. Corrected to `self.moisture_pct`. Dict key also corrected from `moisture_ppm` → `moisture_pct`. When the L9/CEG adapter is wired, any PPM conversion (`moisture_pct * 10000`) belongs at the adapter boundary, not here.

---

## Views

| File | Description |
|---|---|
| `intake_normalizer_views.xml` | Adds the **Normalization** tab to `plasticos.intake` form via XPath |

The Normalization tab displays the assembled packet fields and provides a "Re-Normalize" action for manual refresh.

---

## Process Codes

`origin_process_type` is a `Selection` field. Imported from:
```python
from odoo.addons.plasticos_material_profile.process_codes import PROCESS_SELECTION
```

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_intake_normalizer --stop-after-init
```

No DB migration needed for packet logic changes (all computed, no stored fields modified).

---

## Integration Points

| Consumer | How Used |
|---|---|
| `plasticos_intake.action_match_to_buyers()` | Calls `assemble_packet()` to build CEG POST body |
| CEG (external) | Consumes the packet dict via the HTTP POST body |


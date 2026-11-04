# plasticos_intake_normalizer

**Version:** 19.0.1.0.5
**Category:** PlasticOS / Data Processing
**Depends:** `plasticos_base`, `plasticos_intake`, `plasticos_material_profile`, `plasticos_facility_profile`

---

## Purpose

Normalizes raw intake form data into a structured, typed packet suitable for the Cognitive Engine Graph (CEG) and downstream matching logic. This module adds the **Normalization tab** to the intake form and owns the `_assemble_packet()` method.

Think of this module as the intake data adapter — it translates human-entered form values (text, selections, floats) into a clean, schema-validated dict that the CEG can consume.

---

## Model: `plasticos.intake.normalizer`

Extends `plasticos.intake` via `_inherit`.

### Key Method: `_assemble_packet()`

Builds the packet from the current intake record. `action_normalize` and the batch cron store it in `last_packet_payload`.

**Packet structure:**

```python
{
    "schema_version": PACKET_SCHEMA_VERSION,
    "intake_id": self.name,
    "odoo_record_id": self.id,
    "partner": self._assemble_partner_block(),
    "polymer": self.polymer_id.code,             # null when empty
    "form": self.form_id.code,                   # null when empty
    "material_grade": self.material_grade_id.code,  # null when empty
    "quality": {
        "mfi_value", "density_value", "moisture_pct", "contamination_pct",
        "has_residue", "attributes", "filler_type", "filler_pct", "contamination_notes",
    },
    "origin": {"application", "sector", "process_type"},
    "frequency": {"quantity_per_load_lbs", "loads_per_month", "deal_type", "contract_duration_months"},
    "geo": self._assemble_geo_block(),
    "material_profile": self._assemble_material_profile_block(),  # includes material_grade
    "facility_capability": self._assemble_facility_block(),
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

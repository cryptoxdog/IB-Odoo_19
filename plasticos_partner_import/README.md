# plasticos_partner_import

**Version:** 19.0.2.1.0
**Category:** PlasticOS / Data Operations
**Depends:** `plasticos_base`, `plasticos_facility_profile`, `plasticos_material_profile`, `plasticos_security_base`

---

## Purpose

Provides bulk **partner** import tooling (cieTrade / broker CSVs) for `res.partner` and facility data. **cieTrade partner import is Settings-only** (one-shot server CSV paths via **Settings → PlasticOS Partner Import → Run cieTrade Partner Import**); Contacts / PlasticOS banner menus for the partner wizard are removed — the wizard remains for emergency Technical access only. VanillaSoft **CRM lead** load is API-first via `plasticos_crm_sync` (**Settings → PlasticOS CRM Sync → Run VanillaSoft API Sync**). The CRM lead CSV wizard likewise has no CRM/PlasticOS menu entries (emergency Technical access only).

---

## Models

### `plasticos.partner.import.wizard` (TransientModel)

The primary import UI. Accepts a CSV file, maps columns to `res.partner` fields, previews the mapping, and executes the import with deduplication logic.

**Key fields:**

| Field | Notes |
|---|---|
| `import_file` | Binary CSV upload |
| `file_name` | |
| `facility_role` | Role to assign imported partners — was `x_facility_role` (x-field), renamed via migration, fixed in code |
| `import_mode` | `create_only / update_only / upsert` |
| `dedup_key` | Field to use for deduplication (email, phone, vanillasoft_id) |
| `preview_line_ids` | `One2many` — first 10 rows shown in form before commit |
| `result_summary` | Text summary after import |

---

## Service: `crm_lead_import_service.py` (deprecated UI)

Emergency CSV path for VanillaSoft CRM leads. **Do not use for normal operations** — use `plasticos_crm_sync` API sync. Maps VanillaSoft fields to Odoo `res.partner` and `crm.lead` fields.

**Key field rename history:**
- `x_vanillasoft_id` → `vanillasoft_id` (migration 19.0.1.x renamed the DB column)
- `x_facility_role` → `facility_role` (same migration sweep)
- All code references corrected during the x-field cleanup sweep

**Deduplication logic:** Checks existing partners by `vanillasoft_id` first, then falls back to email, then phone. Creates new or updates existing depending on `import_mode`.

---

## Views

| File | Description |
|---|---|
| `partner_import_wizard_views.xml` | Import wizard form — file upload, column mapping, preview grid, result summary |

**Button labels:** All reference `facility_role` (not `x_facility_role`) after the rename fix.

---

## Migrations

| Version | Change |
|---|---|
| `19.0.1.1.0` | Renames `x_vanillasoft_id` → `vanillasoft_id` in DB |
| `19.0.1.2.0` | Renames `x_facility_role` → `facility_role` in DB |

**Note:** Migration scripts reference the old `x_` names intentionally — that is correct behavior for migration files. Do not treat those as bugs.

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_partner_import --stop-after-init
```

---

## Integration Points

| Module | Notes |
|---|---|
| `plasticos_facility_profile` | Imported partners can be assigned facility profiles post-import |
| `plasticos_crm_bridge` | CRM leads created from import can be bridged to the plasticos pipeline |

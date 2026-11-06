---
auto_generated: false
authority: derived-index
component_id: plasticos_geolocalize
component_name: PlasticOS Geolocalize
module_version: 19.0.1.1.0
layer: 2
installable: true
auto_install: true
application: false
depends:
  - plasticos_base
  - base
  - base_geolocalize
  - plasticos_intake
models_owned: []
models_extended:
  - res.partner
  - plasticos.intake
crons:
  - ir_cron_geo_backfill
---

# PlasticOS Geolocalize

The front matter above is a derived index. `__manifest__.py` and the `_inherit` lines in `models/` win on any conflict.

## What it does

Fills in missing partner coordinates with a nightly backfill, and makes each intake's latitude and longitude follow its partner.

## How it works

- **Backfill.** Cron `ir_cron_geo_backfill` calls `res.partner.cron_geo_backfill()` (`models/res_partner_geo.py`).
  - It takes the advisory lock `plasticos_geolocalize.ir_cron_geo_backfill` and returns when another worker holds it.
  - It searches partners whose `partner_latitude` is empty and that have a street or a city, ordered by id, up to the batch size.
  - For each one it calls Odoo's `partner.geo_localize()` (`base_geolocalize`), commits after each success, and sleeps between calls.
  - It stops after too many consecutive failures, which usually means the geocoder is rate-limiting.
- **Tuning.** System parameters `plasticos_geolocalize.nominatim_delay`, `.failure_delay`, `.batch_size`, and `.max_consecutive_failures` override the defaults (1.1 s, 5 s, 25, 3). A missing or malformed value falls back to the default. The delay never goes below 1.0 s, the Nominatim usage floor.
- **Intake coordinates.** The `plasticos.intake` extension (`models/intake_geo.py`) redefines `lat` and `lon` as stored, read-only fields related to the partner's `partner_latitude` and `partner_longitude`.
- **Install hook.** `post_init_hook` in `hooks.py` grants this module's groups to the users of the crons it owns.

`models/res_partner_geo.py` does not override `create` or `write`. A partner is geocoded by the nightly cron, not when it is saved.

## Models

| Model              | Kind     | File                        |
| ------------------ | -------- | --------------------------- |
| `res.partner`      | extended | `models/res_partner_geo.py` |
| `plasticos.intake` | extended | `models/intake_geo.py`      |

The module defines no model of its own.

## Runtime

- Cron: `ir_cron_geo_backfill`, daily, `active` true in `data/cron_geo_backfill.xml`, run as `plasticos_base.user_system_cron`.
- The geocoder provider and its User-Agent are configured by Odoo's `base_geolocalize`, not here. No geocoder key is stored in this module.
- `auto_install` is true.

## Boundaries

- It does not compute distances or freight.
- It does not choose or configure the geocoding provider.

## Read next

- [`models/res_partner_geo.py`](models/res_partner_geo.py)
- [`models/intake_geo.py`](models/intake_geo.py)

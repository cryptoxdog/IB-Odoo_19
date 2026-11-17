---
auto_generated: false
authority: derived-index
component_id: plasticos_intake_normalizer
component_name: Plasticos Intake Normalizer
module_version: 19.0.1.0.7
layer: 2
installable: true
auto_install: true
application: false
depends:
  - plasticos_intake
  - plasticos_material_profile
  - plasticos_base
models_owned:
  - plasticos.normalizer.config
models_extended:
  - plasticos.intake
crons:
  - cron_batch_normalize_intakes
---

# Plasticos Intake Normalizer

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict. The manifest does not set `application`; Odoo's default is false.

## What it does

Checks an intake against a fixed schema, assembles a JSON packet from it, and stores that packet on the intake.

## How it works

- **Rules.** `plasticos.normalizer.config` is a singleton (`get_config()` creates it when missing). It switches checks on or off: canonical polymer, partner present, positive quantity, density range, positive MFI. `batch_limit` caps the cron; a negative value is refused.
- **Button.** `plasticos.intake.action_normalize()` validates the intake. On errors it stores them, sets `match_status` to `error`, and raises. Otherwise it builds the packet with `_assemble_packet()` (schema version, intake ids, partner, polymer, form, grade, quality, origin, geo, material profile, and facility blocks) and writes `normalized`, `match_status = normalized`, `last_packet_id`, `last_packet_version`, `last_packet_payload`, and `last_packet_ts`. It then tries to geocode the facility, or the partner, with `geo_localize()` when it has an address and no latitude. A geocoding failure is logged, not raised.
- **Cron.** `cron_batch_normalize_intakes` calls `cron_batch_normalize()`. It takes the advisory lock `plasticos_intake_normalizer.cron_batch_normalize_intakes`, picks up to `batch_limit` intakes with `normalized` false and `match_status` `pending`, and stores errors per record instead of raising. The cron path does not geocode.
- **Install hook.** `post_init_hook` in `hooks.py` grants this module's security groups to the users of the crons it owns.

## Models

| Model                         | Kind     | File                          |
| ----------------------------- | -------- | ----------------------------- |
| `plasticos.normalizer.config` | owned    | `models/normalizer_config.py` |
| `plasticos.intake`            | extended | `models/intake_normalizer.py` |

## Runtime

- Cron: `cron_batch_normalize_intakes`, hourly, `active` true in `data/cron_batch_normalize.xml`.
- Default rules load from `data/normalizer_config_data.xml`.
- `auto_install` is true.

## Boundaries

- It stores the packet. It sends nothing to Gate, CEG, or any other service.
- It does not match buyers or change any model other than the intake and, when geocoding succeeds, the partner's coordinates.
- Pure `_inherit` of `plasticos.intake`; no `write()` override.

## Read next

- [`models/intake_normalizer.py`](models/intake_normalizer.py)
- [`models/normalizer_config.py`](models/normalizer_config.py)
- [`../plasticos_intake/README.md`](../plasticos_intake/README.md)

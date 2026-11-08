---
auto_generated: false
authority: derived-index
component_id: plasticos_base
component_name: PlasticOS Base
module_version: 19.0.1.1.10
layer: 1
installable: true
auto_install: true
application: true
depends:
  - plasticos_odoo_standard_apps
  - base
  - base_setup
  - contacts
  - sale_management
models_owned:
  - plasticos.midnight.recompute
models_extended:
  - ir.attachment
crons:
  - ir_cron_midnight_recompute
  - ir_cron_cleanup_attachment_orphans
---

# PlasticOS Base

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

The foundation every PlasticOS module builds on: company and user seed data, partner tags, the PlasticOS root menu, the nightly recompute service for time-based fields, and a filestore cleanup job.

## How it works

- **Midnight recompute.** `plasticos.midnight.recompute` (`models/midnight_recompute.py`) is an abstract service with no table. Cron `ir_cron_midnight_recompute` calls `_cron_midnight_recompute()` daily. It takes the advisory lock `plasticos_base.cron_midnight_recompute` and calls `_recompute_document_expiry()` and `_recompute_claim_time_fields()`. Those hooks are filled in by `plasticos_documents` (document expiry) and `plasticos_claims` (claim age and overdue flags), which inherit this service. Stored fields that depend on "today" are refreshed once a day this way.
- **Attachment cleanup.** Cron `ir_cron_cleanup_attachment_orphans` calls `ir.attachment._cron_cleanup_missing_filestore_orphans()` daily. It takes the advisory lock `plasticos_base.ir_cron_cleanup_attachment_orphans`, reads the 2000 lowest-id binary attachments that have a `store_fname`, and deletes those whose file is missing from the filestore. It skips the run when `data_dir` is not configured.
- **Seed data** (`data/`): the company, a service user for crons (`plasticos_base.user_system_cron`), admin users, sales reps, partner tags, and UoM defaults. `data/material_taxonomy.xml` adds more `res.partner.category` records, including tags named after polymers. It is partner tagging, not the material master; that is `plasticos_material_profile`.
- **Install hooks.** `pre_init_hook` renames an existing `utm.source` named "Referral" to "Referral (legacy)" so Odoo can create its own. `post_init_hook` assigns groups to the admin users and the cron user with SQL on `res_groups_users_rel`, because Odoo 19 `res.users` no longer accepts `groups_id` writes. Migration `19.0.1.1.3` runs the same hook on upgrade.
- **Retired settings.** The manifest summary still says "feature gates". There is no feature-gate model. Migration `19.0.1.1.7` deletes the leftover matching-engine, inference-engine, and `plasticos.feature_gate.user_message` system parameters.
- **Test helpers.** `test_common.py` holds the shared test factory used by other modules' tests.

## Models

| Model                          | Kind            | File                           |
| ------------------------------ | --------------- | ------------------------------ |
| `plasticos.midnight.recompute` | owned, abstract | `models/midnight_recompute.py` |
| `ir.attachment`                | extended        | `models/ir_attachment.py`      |

## Runtime

- Crons: `ir_cron_midnight_recompute` (daily, `data/midnight_recompute_cron.xml`) and `ir_cron_cleanup_attachment_orphans` (daily, `data/attachment_maintenance_cron.xml`). Both are `active` true.
- `installable`, `application`, and `auto_install` are true.

## Boundaries

- No business models. Material, facility, intake, and transaction data live in higher layers.
- No matching, inference, or Gate setting is read here.
- Higher-layer modules may extend the midnight service; this module does not depend on them.

## Read next

- [`models/midnight_recompute.py`](models/midnight_recompute.py)
- [`hooks.py`](hooks.py)
- [`../plasticos_security_base/README.md`](../plasticos_security_base/README.md)

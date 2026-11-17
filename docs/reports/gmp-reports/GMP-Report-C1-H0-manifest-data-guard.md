# GMP Report C1-H0 — manifest data-file guard

Campaign C1, lane H0. Branch `ci/c1-manifest-data-guard` from `origin/Staging` `42db406`. Pure test only; no module, manifest, workflow or pre-commit change.

## Phase 0 — Plan

| # | File | Action | Expected behavior |
|---|---|---|---|
| 1 | `tests/test_manifest_data_files.py` (new) | Insert | For every `plasticos_*/__manifest__.py` (parsed with `ast.literal_eval`): every `*.xml` / `*.csv` under the module's `data/` (recursive) is in `data` or `demo`, unless an `ALLOWLIST` entry with a reason names it; every `data` / `demo` entry exists on disk; every `ALLOWLIST` entry still exists and is still unlisted. |

Why: `plasticos_facility_profile/data/company_role_tag_data.xml` was never in its manifest, so its records never loaded. PR #525 fixes that file.

## Phase 1 — Baseline (Staging `42db406`)

Unlisted data files found: exactly the six allowlisted ones. No manifest entry is missing on disk.

| Allowlisted file | Verified reason |
|---|---|
| `plasticos_crm_sync/data/approved_contact_crosswalk.csv` | `plasticos_crm_sync/services/approved_identity.py:21` `CROSSWALK_FILE`, read at `:132` |
| `plasticos_crm_sync/data/vanillasoft_material_mapping.csv` | `scripts/build_material_mapping.py:54` `PREVIOUS_MAP`, opened at `:359`. A repository script, not module code. |
| `plasticos_material_profile/data/ERP-Products.csv` | `plasticos_material_profile/models/material_normalizer.py:428` `_ERP_CATALOG_FILE`, loaded at `:449` |
| `plasticos_material_profile/data/material_mapping.csv` | `material_normalizer.py:71` `_MATRIX`, opened at `:116` |
| `plasticos_crm_bridge/data/utm_source_deactivate.xml` | `<odoo>` with one comment; 0 `record` / `function` / `delete` elements |
| `plasticos_facility_profile/data/company_role_tag_data.xml` | TEMPORARY: listed by PR #525. Remove the allowlist line once #525 merges; the stale-allowlist case then fails until it is removed. |

## Phase 2–4 — Implement / Validate

- `ruff 0.16.0` format + check: clean.
- `pytest tests/test_manifest_data_files.py`: 71 passed on Staging.
- Negative proof: a temporary unlisted `plasticos_base/data/_probe_unlisted.xml` made the `plasticos_base` case fail; the probe was removed.

## Phase 5 — Recursive verify

Only the new test and this report are added.

## Phase 6 — Finalize

Published with `make pr-nosmoke` into `Staging`.

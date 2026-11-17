# GMP Report — C1 lane G1: retire the material-taxonomy partner tags

- Campaign: C1 (PlasticOS contacts / ERP sync realignment), lane G1
- Branch: `chore/c1-g1-retire-material-tags` from `origin/Staging` `42db406`
- Module: `plasticos_base` `19.0.1.1.14` → `19.0.1.1.15` (operator-approved in the frozen campaign scope)
- Production usage: **0 partners on every one of the 108 tags** (CTO Production probe 2, 2026-11-17).
  This clears the merge gate.

## Phase 0 — Plan

`plasticos_base/data/material_taxonomy.xml` loaded 108 `res.partner.category`
records in six groups: Polymers, Material Types, Forms, Source Types, Colors and
Grades. They copy the material vocabulary that lives on material profiles
(`plasticos_material_profile`), and no code reads them. G1 removes them. It does
not touch `data/partner_tags.xml` (Operational and Material Focus are lane F2's).

## Phase 1 — Baseline (reference search)

I searched the whole repo for every external id and every name in the file.

| Reference | Where | Outcome |
|---|---|---|
| `plasticos_base.<id>` for any of the 108 ids | `plasticos_base/migrations/19.0.1.1.14/post-migrate.py` (`form_bale`, `raise_if_not_found=False`) only | Kept. It is safe once the tag is gone. |
| `data/material_taxonomy.xml` | `plasticos_base/__manifest__.py`, `plasticos_base/README.md` | Updated. |
| The file itself | `tests/test_bales_never_a_form.py:112` asserted `form_bale` inactive in it | Now asserts the file is gone. |
| Its tag names as known vocabulary | `tests/test_phantom_enum_values.py` (spot-check, polymer-case check, phantom registry) | Updated with CTO approval, see Phase 2. |
| Same ids in another module | `plasticos_material_profile.form_bale`, `form_film`, … | Not references: different records with the same id. |
| Tag lookups by name | `plasticos_crm_bridge` uses its own `categ_*`; the ERP import uses `legacy_erp_contact_role_*`; enrichment reads only Buyer/Customer | None read a material-taxonomy tag. |
| History | `filetree.md`, `tests/production-rehearsal/evidence/*` load logs | Left as they are. |

## Phase 2 — Implement

| File | Change |
|---|---|
| `plasticos_base/data/material_taxonomy.xml` | Deleted. |
| `plasticos_base/__manifest__.py` | File dropped from `data`; version `19.0.1.1.15`. |
| `plasticos_base/README.md` | Version line; the seed-data sentence now says the vocabulary lives on material profiles and names migration `19.0.1.1.15`. |
| `plasticos_base/migrations/19.0.1.1.15/post-migrate.py` | Finds the 108 tags only through `ir.model.data` (`module = plasticos_base`, `model = res.partner.category`, name in `RETIRED_TAG_XMLIDS`), archived tags included. Before removal it logs, for each tag, how many partners carried it. Then it unlinks the tags, which removes their partner links, and the leftover external ids. A second run finds nothing. |
| `tests/test_bales_never_a_form.py` | Asserts the taxonomy file no longer exists, instead of reading `form_bale` from it. |
| `tests/test_phantom_enum_values.py` | It no longer reads the deleted file (details below). |
| `tests/test_retire_material_taxonomy_tags.py` | New pure tests. |

`tests/test_phantom_enum_values.py` used the names in the deleted file as part
of its known vocabulary. Three changes, each keeping its check over a source
that still exists:

1. `test_known_forms_in_registry` now spot-checks the form master names
   (`Bales`, `Film`, `Flake`, `Pellets` from `material_form_data.xml`). It used
   to check the retired tag short codes (`BALE`, `PELL`).
2. `test_xml_polymer_names_are_uppercase` now checks the polymer master's codes
   (`polymer_data.xml`, `xml_code`). It also asserts that set is not empty,
   because the old filter silently matched nothing once the file was gone.
3. Deleting the file exposed 33 values in
   `plasticos_enrichment/models/enrichment_service.py` (and `'sweep'` in
   `enrichment_run.py`). They are the input words and intermediate short codes
   of `FORM_NORMALIZE`, `SOURCE_TYPE_NORMALIZE` and `POLYMER_NORMALIZE`, which
   `FORM_CODE_TO_MASTER` maps onto master codes. The scanner had been accepting
   them only because the tags carried the same names. They are now listed
   explicitly in `GLOBAL_ALLOWLIST` under their own heading, following the
   existing web-leads input-synonym section. No assertion was removed or
   weakened and nothing is skipped.

## Phase 3 — Enforce

- ruff 0.16.0: clean.
- Pre-commit ran on the commits, with no hook bypassed.

## Phase 4 — Validate

- `tests/test_retire_material_taxonomy_tags.py`: 6 passed. It covers:
  - the file is gone and not in the manifest;
  - the migration lists exactly 108 unique ids, including the six groups;
  - only `plasticos_base` `res.partner.category` external ids are removed;
  - usage is logged before the unlink;
  - `partner_tags.xml` is untouched and does not overlap;
  - no `plasticos_base.<retired id>` reference remains in tracked `.py`, `.xml` or `.csv` files.
- `tests/test_phantom_enum_values.py` and `tests/test_bales_never_a_form.py`: 63 passed.
- Not run: Odoo runtime (Cursor lane T). The migration's removal and the
  absence of a load error for `plasticos_base` are proven only there.

## Phase 5 — Recursive verify

- Changed outside `plasticos_base`: `tests/test_bales_never_a_form.py`,
  `tests/test_phantom_enum_values.py` (added to G1's scope by the CTO) and the
  new test file.
- Not touched: `partner_tags.xml` and every other module.

## Phase 6 — Finalize

Residual risk: none for Production data, since usage is 0. A database where
someone tagged partners with these tags loses those links; the migration logs
each count first.

# Validation summary

## Executed during package preparation

| Check | Actual result | Scope |
|---|---|---|
| Supplied case JSON Schema (Draft 2020-12) | PASS | Shape only |
| Intent -> effect -> proof coverage | PASS | Declared planning obligations |
| Combined dependency and effect order | PASS | 13 units, 29 effects |
| Prospective addon DAG | PASS | Baseline plus proposed optional leaf; installed native dependencies still unobserved |
| Original kernel byte preservation | PASS | All 24 original members unchanged |
| Original kernel manifest/integrity | PASS | Its 23 manifest-listed members plus manifest |
| Supplied kernel negative controls | PASS | Synthetic validator cases only |
| Package negative controls | PASS | 8 cases reject fake activation, fake proof, missing scope and broken graph |
| Generic planning validator local controls | PASS | 5 structural tests including negatives |
| Package prohibited-content/secret-pattern scan | PASS | Package files only, not the target repository's canonical git-index guard |

## Correctly refused gates

The supplied kernel's **plan gate returns FAIL** with:

- `TARGET_ENV_UNKNOWN`: actual installed Odoo/Enterprise runtime and data not inspected.
- `OPEN_OPERATOR_DECISIONS`: optional bridge necessity/admission and evidence-derived production calibration/spend policy are not silently selected as proven.
- `UNEXPLORED_DYNAMIC_CONSUMERS`: DB-defined actions/automations and installed consumers remain a required census.

The precode gate also rejects unadopted interfaces, open source limits, missing precode evidence and unauthenticated implementation grants. These are intentional, material blockers, not ignored tests. Raw receipts are included. No modification was made to the supplied validator to obtain a green result.

## Not executed or claimed

Product code tests; live migrations; native Enterprise install/upgrade; real Odoo/Gate/EIE/CEG integration; source-provider inference evaluation; independent reviewer acceptance; production enable. All 34 product proof obligations remain NOT_RUN.

The final ZIP is checked separately for member safety, CRC, checksums and caller-authored policy assertions. Its exact archive SHA and structural receipt are delivered as companion artifacts because embedding an archive's own checksum inside itself would invalidate that checksum.

## Reproduce local package checks

From the extracted package root, with Python and `jsonschema` already available:

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/validate_package.py
PYTHONDONTWRITEBYTECODE=1 python tools/test_package_negative_controls.py
PYTHONDONTWRITEBYTECODE=1 python PLANNING_KERNEL/tools/validate_pack.py
PYTHONDONTWRITEBYTECODE=1 python PLANNING_KERNEL/tools/test_negative_controls.py
PYTHONDONTWRITEBYTECODE=1 python PLANNING_KERNEL/tools/validate_case.py case.json --gate plan
PYTHONDONTWRITEBYTECODE=1 python PLANNING_KERNEL/tools/validate_case.py case.json --gate precode
```

The last two commands are expected to refuse this case until real missing evidence and authority are supplied. Do not change flags or erase frontiers to force them to pass. These commands operate on the package only; they do not inspect or mutate Odoo or GitHub.

# System State

Update this file when significant changes merge.

## Branches
- `staging` — active development, PRs target here
- `main` — production, merged from staging

## Module Status
| Status | Modules |
|--------|---------|
| Production | base, security_base, material_profile, product, facility_profile, intake, accounting, offer, order_lines, transaction, logistics, documents, claims, automation, partner_import, geolocalize |
| Beta | intake_normalizer, web_leads, enrichment, crm_bridge, commission |
| Dev-only | dev_tools (installable=False) |
| External | inference_engine (installable=False), matching (installable=False), documents_native (Enterprise only) |
| New | website, buyer_match_engine |

## Known Issues
- mypy type check runs as advisory (continue-on-error in CI)
- ruff excludes inference_engine, buyer_match_engine, matching from lint (pre-existing)
- Some pre-existing Odoo pattern violations tracked separately from new PRs

---
paths:
  - "plasticos_*/views/**/*.xml"
  - "plasticos_*/data/**/*.xml"
---
# XML View & Data Rules

## View Rules (Odoo 19)
- Use `<field>` with explicit `widget=` when needed
- XPath expressions must target stable anchors (not position-dependent)
- ❌ Never use `position="replace"` on base Odoo views without strong justification
- Prefer `position="after"` or `position="inside"` for extending views
- All custom views need unique `id` with `plasticos_module.` prefix

## Seed Data Rules (Deterministic Seed Doctrine)
- Wrap in `<odoo noupdate="1">` for reference data
- Every record needs external ID: `id="plasticos_module.record_name"`
- ❌ Never hardcode database IDs in `ref=""` — always use external IDs
- ❌ Never bootstrap data via CSV at runtime
- Partner tags, material taxonomy, payment terms, chart of accounts = XML seed

## Cron (ir.cron) Rules
- ❌ Never use `numbercall` → deprecated in Odoo 19
- Always include `interval_number` and `interval_type`
- Default: `active` eval="False" for new crons (enable via feature flag)
- Use advisory locks for crons that must not overlap: `SELECT pg_try_advisory_lock()`
- Run: `python3 tools/cron_invariant_check.py`

## Validation
- Run: `python3 ci/check_odoo19_xml.py`
- Run: `python3 ci/check_xpath_stability.py`
- All XML must pass `xmllint --noout` (checked in CI)

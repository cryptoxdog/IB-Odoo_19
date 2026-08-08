<!-- L9_META
skill_schema: 1
parent: plasticos-static-audit-kernel
layer: reference
role: command_map
tags: [plasticos, audit, make, ci, guards]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Static Audit Command Map

## Tier Composition

| Target | Includes |
|--------|----------|
| `make check` | lint + format check |
| `make audit-quick` | lint, format, XML, Odoo 19, wiring, deps, cron |
| `make audit` | audit-quick + semgrep + guards + ACL + integrity scripts |
| `make pr-check` | audit-quick + semgrep (+ pytest tier 3 in CI) |

## Individual Targets

- `make lint` / `make format`
- `make xml-check` → `ci/check_odoo19_xml.py` (via odoo19-check)
- `make odoo19-check`
- `make wiring` → `scripts/check_module_wiring.py`
- `make deps-check` → circular + orphan refs
- `make cron-check` → `tools/cron_invariant_check.py`
- `make semgrep`
- `make guards`
- `make acl-check`

## Guard Scripts

```bash
python3 ci/check_pipeline_v2_guard.py
python3 ci/check_dev_tools_fence.py
python3 ci/check_state_guard_bypass.py
python3 ci/check_acl_completeness.py
python3 ci/check_orm_integrity.py
python3 ci/check_field_integrity.py
python3 ci/check_orphan_model_refs.py
python3 ci/check_xpath_stability.py
python3 ci/check_constraint_patterns.py
python3 ci/check_automation_field_refs.py
```

## CI Baselines (HIGH severity)

From `AGENTS.md`:

| Audit | Baseline |
|-------|----------|
| `odoo_audit.py` HIGH | 0 |
| Extended audit HIGH | 4 (pre-existing) |
| XPath CRITICAL | 0 |
| XPath HIGH | 0 |

New HIGH findings above baseline = merge blocker.

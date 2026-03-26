---
name: audit-check
description: Run the full PlasticOS audit and CI check suite
disable-model-invocation: true
---

# Audit & CI Check Suite

## Quick Checks (run before every commit)
```bash
ruff check .
ruff format --check .
python3 scripts/check_module_wiring.py
python3 ci/check_circular_deps.py
```

## Full Audit (run before PRs)
```bash
# Odoo 19 compliance
./scripts/check_odoo_patterns.sh

# XML validation
find . -name "*.xml" -not -path "./.git/*" | xargs xmllint --noout
python3 ci/check_odoo19_xml.py

# Dependency integrity
python3 ci/check_circular_deps.py
python3 ci/check_orphan_model_refs.py
python3 ci/audit_cross_module_deps.py

# Field and ORM integrity
python3 ci/check_field_integrity.py
python3 ci/check_orm_integrity.py
python3 ci/check_model_inheritance.py

# State machine and automation
python3 ci/check_state_guard_bypass.py
python3 ci/check_automation_field_refs.py
python3 ci/check_disabled_actions.py

# Cron safety
python3 tools/cron_invariant_check.py

# View stability
python3 ci/check_xpath_stability.py

# Constraint patterns (Odoo 19)
python3 ci/check_constraint_patterns.py
```

## Semgrep (custom Odoo rules)
```bash
semgrep --config .semgrep/odoo-patterns.yml
```
Catches: hardcoded model strings, commented-out code, bare except

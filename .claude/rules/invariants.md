---
paths:
  - "plasticos_*/**/*.py"
  - "plasticos_*/**/*.xml"
---
# PlasticOS Invariants — Path-Scoped Pointer

**Authority:** `INVARIANTS.md` (repo root) — 18 CI-enforced invariants. If code violates an invariant, code is wrong.

**Quick gates before commit:**
```bash
make pr-check
python3 scripts/check_module_wiring.py
python3 ci/check_circular_deps.py
```

**Odoo 19 highlights:** `models.Constraint` not `_sql_constraints` · no `@api.depends("id")` · `<list>` not `<tree>` · no `category_id` on groups.

**Overlay rules:** `84-ci-odoo19-patterns.mdc` · `82-ci-module-wiring.mdc` · `81-ci-manifest-contract.mdc`

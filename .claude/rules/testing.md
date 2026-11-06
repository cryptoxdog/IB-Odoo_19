---
paths:
  - "tests/**/*.py"
---
# Testing — Path-Scoped Pointer

**Authority:** `80-plasticos-testing-rules.mdc` · `AGENTS.md` § Testing · global `95-test-fix-policy.mdc`

```bash
make test              # pure pytest (CI Tier 3)
make runtime-test m=X  # Odoo Docker runtime tests: pr-check smoke stage or l9-pr-integration-testing only
```

Odoo runtime tests (`make test-module` / `make test-odoo`) run only in the `make pr-check` smoke stage or when `l9-pr-integration-testing` is invoked (`make runtime-test m=<modules>`). Do not run them ad hoc.

**Rules:** `TransactionCase` · create fixtures in `setUpClass` (never `skipTest`) · `type='consu'` for storable products in Odoo 19 · do not mutate seed data.

**Layouts:** `tests/contracts/` · `tests/integration/` · `tests/test_*.py`

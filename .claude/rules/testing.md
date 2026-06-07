---
paths:
  - "tests/**/*.py"
---
# Testing — Path-Scoped Pointer

**Authority:** `80-plasticos-testing-rules.mdc` · `AGENTS.md` § Testing · global `95-test-fix-policy.mdc`

```bash
make test              # pure pytest (CI Tier 3)
make test-odoo         # Odoo Docker runtime tests
make test-module m=X   # single module
```

**Rules:** `TransactionCase` · create fixtures in `setUpClass` (never `skipTest`) · `type='consu'` for storable products in Odoo 19 · do not mutate seed data.

**Layouts:** `tests/contracts/` · `tests/integration/` · `tests/test_*.py`

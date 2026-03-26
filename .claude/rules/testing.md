---
paths:
  - "tests/**/*.py"
---
# Testing Rules

## Test Types
- **Contract tests** (`tests/contracts/`): 8 files — API signatures, bridge wiring, computed deps, CRM leads, intake, partner, selection, transaction
- **Integration tests** (`tests/integration/`): 10 files — account-move links, compliance, cron idempotency, graph hooks, intake cascade, match guards, offer state, polymer sync, sale-order autocreate, write/unlink guards
- **Unit tests** (`tests/test_*.py`): 20+ files — constraints, state machines, golden flows, security ACL, performance, Odoo 19 compat

## Rules
- Tests must not mutate seed data
- Use `tests/common.py` and `tests/conftest.py` for shared fixtures
- ❌ Never commit test data to production seed files
- Tag tests requiring seed data for CI exclusion
- New models/fields need at least one test
- Run `python -m pytest tests/ -v` to execute all

## Odoo Test Patterns
```python
# ✅ GOOD — use TransactionCase, proper setup, explicit assertions
from odoo.tests import TransactionCase

class TestPlasticosOffer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Supplier", "supplier_rank": 1})

    def test_offer_state_transition(self):
        offer = self.env["plasticos.offer"].create({"supplier_id": self.partner.id})
        self.assertEqual(offer.state, "draft")
```

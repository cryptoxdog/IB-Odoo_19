# PlastOS Test Pack — Odoo 19.0

> **Comprehensive test suite for `cryptoxdog/IB-Odoo_19` (`staging` branch)**
> **Updated:** 2026-03-05 · **Target:** Odoo 19.0

---

## Test Architecture

The test suite is organized into two categories:

1. **Odoo Tests** — Require Odoo runtime, use `TransactionCase`
2. **Pure Python Tests** — Run without Odoo, use AST/XML parsing for static analysis

All tests use a shared factory mixin (`common.py`) for consistent test data creation.

---

## Test Modules

### Odoo Tests (require Odoo runtime)

| File | Category | Tags | Models Covered |
|------|----------|------|----------------|
| `test_action_methods.py` | Action/Button Methods | `action` | 9 models, 67+ actions |
| `test_bridge_models.py` | Bridge Model Coverage | `bridge` | 7 bridge patterns |
| `test_constraints_material_profile.py` | Constraints | `constraint` | `plasticos.material.profile` |
| `test_constraints_onchanges.py` | Constraints & Onchanges | `constraint`, `onchange` | Transaction, Intake, Claim |
| `test_cron_batch_normalize.py` | Cron Jobs | `cron` | Intake normalizer |
| `test_cron_plasticos_base.py` | Cron Jobs | `cron` | Midnight recompute, attachments |
| `test_cron_runtime.py` | Cron Jobs | `cron` | Cron method validation |
| `test_depends_transaction_claims_bridge.py` | Dependencies | `depends` | Transaction ↔ Claim |
| `test_error_handling.py` | Error Handling | `error_handling` | API failures, validation, ACL |
| `test_golden_flows.py` | Golden Paths | `golden`, `critical` | Full business cycles |
| `test_integration_flows.py` | Integration Flows | `integration` | Cross-module flows |
| `test_onchange_purchase_order_line_plasticos.py` | Onchanges | `onchange` | Purchase order lines |
| `test_onchange_sale_order_line_plasticos.py` | Onchanges | `onchange` | Sale order lines |
| `test_performance.py` | Performance | `performance` | Bulk ops, search, cron |
| `test_security_acl.py` | Security/ACL | `security` | Permission enforcement |
| `test_state_machines.py` | State Machines | `state_machine` | Load, Transaction, Claim, Offer |

### Pure Python Tests (no Odoo required)

| File | Category | Purpose |
|------|----------|---------|
| `test_cron_invariants.py` | Static Analysis | Cron configuration validation |
| `test_cypher_schema_alignment.py` | Schema Validation | Cypher ↔ Neo4j alignment |
| `test_odoo19_compat.py` | Compatibility | Odoo 19 API patterns |
| `test_odoo_test_setup_validity.py` | Meta Testing | Test setup validation |
| `test_phantom_enum_values.py` | Registry Validation | Selection fields vs XML data |
| `test_process_enum_alignment.py` | Registry Validation | Process type alignment |
| `test_repo_dependency_integrity.py` | Module Validation | Manifest and dependency checks |

---

## Shared Test Utilities

### `common.py` — Factory Mixin

All test classes inherit from `PlastOSTestFactoryMixin` which provides:

```python
# Partner/Polymer/Form creation (with deduplication)
cls._create_partner(name, **kw)
cls._get_or_create_polymer(code)
cls._get_or_create_form(code)

# Model-specific factories
cls._create_intake(partner, polymer, form, **kw)
cls._create_transaction(name, **kw)
cls._create_claim(transaction, **kw)
cls._create_offer(buyer, intake, **kw)
cls._create_load(transaction, **kw)
cls._create_web_lead(lead_id, **kw)
cls._create_material_profile(partner, polymer, **kw)

# Skip helper
cls._skip_if_model_missing(*models)
```

### Assertion Helpers

```python
assert_action_result(test_case, result, expected_model, expected_type)
assert_state_transition(test_case, record, action_name, expected_state)
assert_message_posted(test_case, record, keyword)
```

---

## Running Tests

```bash
# All PlastOS tests
odoo-bin -d testdb --test-tags plasticos --stop-after-init

# By category
odoo-bin -d testdb --test-tags golden --stop-after-init      # Critical paths
odoo-bin -d testdb --test-tags integration --stop-after-init # Cross-module
odoo-bin -d testdb --test-tags action --stop-after-init      # Button methods
odoo-bin -d testdb --test-tags bridge --stop-after-init      # Bridge models
odoo-bin -d testdb --test-tags cron --stop-after-init        # Scheduled jobs
odoo-bin -d testdb --test-tags performance --stop-after-init # Benchmarks
odoo-bin -d testdb --test-tags error_handling --stop-after-init

# Pure Python tests (no Odoo required)
pytest tests/test_cypher_schema_alignment.py -v
pytest tests/test_phantom_enum_values.py -v
pytest tests/test_repo_dependency_integrity.py -v

# Meta tests (validate test suite structure)
pytest tests/tests_init.py -v
```

---

## Test Tags

| Tag | Purpose |
|-----|---------|
| `plasticos` | All PlastOS tests |
| `golden` | Critical business path tests (blocking) |
| `critical` | Must-pass tests for CI |
| `integration` | Cross-module flow tests |
| `action` | Action/button method tests |
| `bridge` | `_inherit` bridge model tests |
| `cron` | Scheduled job tests |
| `performance` | Performance benchmarks |
| `error_handling` | Error scenario tests |
| `security` | ACL and permission tests |
| `state_machine` | State transition tests |
| `constraint` | Constraint validation tests |
| `onchange` | Onchange method tests |

---

## Golden Flows (Critical Paths)

These tests represent the core business flows that must always work:

| Flow | Description | Test Class |
|------|-------------|------------|
| Lead → Delivery | Full sales cycle | `TestGoldenLeadToDelivery` |
| HOT Lead → Intake | Automated lead processing | `TestGoldenHotWebLeadToIntake` |
| Transaction → Claim | Quality management | `TestGoldenTransactionWithClaim` |
| Offer → Commission | Revenue recognition | `TestGoldenCommissionCalculation` |

---

## Coverage Map

### Models with State Machines

| Model | States | Transitions Tested |
|-------|--------|-------------------|
| `plasticos.load` | 10 | Valid + invalid + exception handling |
| `plasticos.transaction` | 10 | Valid + invalid + write guards |
| `plasticos.claim` | 5 | Valid + reopen scenarios |
| `plasticos.offer` | 7 | Valid + invalid + reset |

### Bridge Models Tested

| Bridge | Relationship |
|--------|--------------|
| Offer ↔ Transaction | Many2one ↔ One2many |
| Intake ↔ Transaction | Many2one ↔ One2many |
| Transaction ↔ Claim | Many2one ↔ One2many |
| Transaction ↔ Document | Many2one ↔ One2many |
| Load ↔ Document | Many2one ↔ One2many |
| Partner ↔ Intake | One2many + computed counts |
| Match Result ↔ Offer | Many2one links |

---

## Prerequisites

- Odoo 19.0 with `plasticos_*` modules installed
- Test database with demo data loaded
- For controller tests: Odoo HTTP server running
- For CRM bridge tests: `crm` module installed
- For pure Python tests: `pytest` installed

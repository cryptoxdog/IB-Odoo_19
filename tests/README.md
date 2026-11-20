# PlastOS Test Pack — Odoo 19.0

> **Comprehensive test suite for `cryptoxdog/IB-Odoo_19` (`staging` branch)**
> **Updated:** 2026-03-05 · **Target:** Odoo 19.0

---

## Test Architecture

The test suite is organized into two categories:

1. **Odoo Tests** — Require Odoo runtime, use `PlasticosTestCase` (`TransactionCase` under `--test-enable`).
   They live in the owning addon's `tests/` package (`plasticos_<addon>/tests/test_*.py`), **not** here.
2. **Pure Python Tests** — Run without Odoo, use AST/XML parsing for static analysis. They live in this
   `tests/` tree and run under pytest (`make test`, the PR-fast `pure-python-tests` lane, and the
   Staging nightly full Odoo-free suite). The nightly workflow does not run addon ORM tests.

Odoo-backed tests use the shared factory mixin in `plasticos_base/test_common.py`.

---

## Test Modules

### Odoo Tests (require Odoo runtime)

Odoo 19 collects tests only from `odoo.addons.<addon>.tests`, and only the `test_*` submodules that
package's `__init__.py` imports (`odoo/tests/loader.py`). `--test-file` / `--test-tags` filter that set;
they cannot add a file outside it. An Odoo test placed under this root `tests/` tree therefore runs
nowhere: `conftest.py` collect-ignores it under pytest, and Odoo never loads it.
`tests/test_odoo_test_discovery.py` enforces the placement.

Owner rule: the smallest addon whose dependency closure covers every PlasticOS model the file
exercises. Where no single closure covers it (the leaf addons `plasticos_matching` /
`plasticos_enrichment` have no dependants), the addon with the fewest uncovered models; those files are
`post_install` and run against a full install (Odoo.sh, or the pinned Docker fixture through `make runtime-test` in the `make pr-check` smoke stage).

| File | Owner addon | Tags |
|------|-------------|------|
| `test_crm_lead_contracts.py`, `test_partner_contracts.py`, `test_xpath_field_refs.py` | `plasticos_base` | `contract`, `xpath_field_refs` |
| `test_bridge_models.py`, `test_constraints_onchanges.py`, `test_cron_idempotency.py`, `test_cron_plasticos_base.py`, `test_cron_runtime.py`, `test_depends_transaction_claims_bridge.py`, `test_integration_flows.py`, `test_selection_contracts.py`, `test_state_machines.py` | `plasticos_claims` | `bridge`, `constraint`, `cron`, `integration`, `state_machine` |
| `test_api_signature_contracts.py`, `test_constraint_validation.py`, `test_golden_flows.py`, `test_security_acl.py` | `plasticos_commission` | `contract`, `golden`, `security` |
| `test_account_move_transaction_link.py`, `test_compliance_service.py` | `plasticos_documents` | `accounting`, `documents` |
| `test_computed_field_deps.py`, `test_intake_contracts.py`, `test_intake_onchange_cascade.py` | `plasticos_intake` | `contract`, `onchange` |
| `test_cron_batch_normalize.py` | `plasticos_intake_normalizer` | — |
| `test_linda_freight_models.py` | `plasticos_logistics` | `linda` |
| `test_match_result_guards.py`, `test_performance.py` | `plasticos_matching` | `matching`, `performance` |
| `test_constraints_material_profile.py`, `test_material_profile_intake_delta_contract.py`, `test_polymer_product_sync.py` | `plasticos_material_profile` | `contract`, `product` |
| `test_offer_state_machine.py`, `test_write_unlink_guards.py` | `plasticos_offer` | `offer`, `guards` |
| `test_onchange_purchase_order_line_plasticos.py`, `test_onchange_sale_order_line_plasticos.py` | `plasticos_order_lines` | — |
| `test_partner_import_csv_paths.py` | `plasticos_partner_import` | `partner_import` |
| `test_action_methods.py`, `test_bridge_contracts.py`, `test_error_handling.py` | `plasticos_security_base` | `action`, `contract`, `error_handling` |
| `test_bridge_wiring_contracts.py`, `test_sale_order_transaction_autocreate.py`, `test_transaction_contracts.py` | `plasticos_transaction` | `contract`, `transaction` |

### Pure Python Tests (no Odoo required)

| File | Category | Purpose |
|------|----------|---------|
| `test_cron_invariants.py` | Static Analysis | Cron configuration validation |
| `test_odoo19_compat.py` | Compatibility | Odoo 19 API patterns |
| `test_odoo_test_setup_validity.py` | Meta Testing | Test setup validation |
| `test_phantom_enum_values.py` | Registry Validation | Selection fields vs XML data |
| `test_process_enum_alignment.py` | Registry Validation | Process type alignment |
| `test_repo_dependency_integrity.py` | Module Validation | Manifest and dependency checks |

---

## Shared Test Utilities

### `plasticos_base/test_common.py` — Factory Mixin

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

`tests/common.py` (pure Python, importable without Odoo):

```python
assert_action_result(test_case, result, expected_model, expected_type)
assert_state_transition(test_case, record, action_name, expected_state)
assert_message_posted(test_case, record, keyword)
```

---

## Running Tests

```bash
# One addon's tests (Docker fixture DB; runs at_install + post_install of that addon)
make runtime-test m=plasticos_claims   # only under l9-pr-integration-testing; the smoke stage passes modules itself

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
pytest tests/test_phantom_enum_values.py -v
pytest tests/test_repo_dependency_integrity.py -v

# Meta tests (validate test suite structure)
pytest tests/test_suite_structure.py -v
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

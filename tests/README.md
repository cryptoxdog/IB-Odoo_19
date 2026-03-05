# PlastOS Test Pack — Odoo 19.0

> **Comprehensive test suite for `cryptoxdog/IB-Odoo_19` (`staging` branch)**
> **Generated:** 2026-03-05 · **Target:** Odoo 19.0

---

## Test Modules

| File | Category | Test Count | Models Covered |
|------|----------|------------|----------------|
| `test_controller_api.py` | Controller/API | 14 | `plasticos.web.lead`, `plasticos.web.lead.config` |
| `test_security_acl.py` | Security/ACL | 16 | `plasticos.transaction`, `plasticos.claim`, `account.move` |
| `test_constraints_onchanges.py` | Constraints & Onchanges | 28 | `plasticos.transaction`, `plasticos.intake`, `plasticos.claim` |
| `test_integration_flows.py` | Integration Flows | 12 | Web Lead → Intake, Transaction lifecycle, Claims, Offers, Docs |
| `test_state_machines.py` | State Machine Transitions | 42 | `plasticos.load`, `plasticos.transaction`, `plasticos.claim`, `plasticos.offer` |
| `test_bridge_models.py` | Bridge Model Coverage | 20 | All `_inherit` bridge files across 8 modules |
| **Total** | | **132** | |

---

## Installation

### Option A: Copy into existing module test directories

Each file is tagged with `@tagged("post_install", "-at_install", "plasticos", "<category>")`.
Copy files into the appropriate module's `tests/` directory and import in `tests/__init__.py`.

### Option B: Standalone test module

```
plasticos_test_pack/
├── __manifest__.py
├── __init__.py
└── tests/
    ├── __init__.py
    ├── test_controller_api.py
    ├── test_security_acl.py
    ├── test_constraints_onchanges.py
    ├── test_integration_flows.py
    ├── test_state_machines.py
    └── test_bridge_models.py
```

---

## Running Tests

```bash
# All test pack tests
odoo-bin -d testdb -i plasticos_test_pack --test-tags plasticos --stop-after-init

# By category
odoo-bin -d testdb --test-tags controller --stop-after-init
odoo-bin -d testdb --test-tags security --stop-after-init
odoo-bin -d testdb --test-tags constraint --stop-after-init
odoo-bin -d testdb --test-tags integration --stop-after-init
odoo-bin -d testdb --test-tags state_machine --stop-after-init
odoo-bin -d testdb --test-tags bridge --stop-after-init

# Single test class
odoo-bin -d testdb --test-tags TestLoadStateMachine --stop-after-init
```

---

## Test Tags

| Tag | Purpose |
|-----|---------|
| `plasticos` | All PlastOS tests |
| `controller` | HTTP endpoint / REST API tests |
| `security` | ACL, group, permission tests |
| `constraint` | `@api.constrains` + SQL constraint tests |
| `onchange` | `@api.onchange` auto-population tests |
| `compute` | Computed field edge-case tests |
| `integration` | End-to-end multi-module flows |
| `state_machine` | State transition valid/invalid tests |
| `bridge` | `_inherit` bridge model tests |

---

## Coverage Map

### Models with State Machines (exhaustive transition testing)

| Model | States | Transitions Tested | Exception Handling |
|-------|--------|-------------------|-------------------|
| `plasticos.load` | 10 | 9 valid + 6 invalid + exception from any | ✅ |
| `plasticos.transaction` | 10 | 7 valid + 2 invalid + write guards | ✅ |
| `plasticos.claim` | 5 | 6 valid + reopen from 2 states | ✅ |
| `plasticos.offer` | 7 | 7 valid + 5 invalid + reset | ✅ |

### Constraints Tested

| Model | Constraint | Type | Boundary Tests |
|-------|-----------|------|----------------|
| `plasticos.transaction` | `unique(name)` | SQL | ✅ |
| `plasticos.transaction` | `commission_override_pct` 0-100 | Python | 0, 100, -5, 150 |
| `plasticos.transaction` | Closed TX immutability | write() | Protected fields |
| `plasticos.transaction` | Bill exclusivity | write() | Vendor + freight |
| `plasticos.intake` | `quantity_per_load_lbs > 0` | Python | 0, -100, 25000 |
| `plasticos.intake` | `loads_per_month >= 0` | Python | -1, 0 |
| `plasticos.claim` | Resolution note required | Python | Empty, valid |
| `plasticos.claim` | `unique(name)` | SQL | ✅ |

### Security Tests

| Group | Model | R | W | C | U |
|-------|-------|---|---|---|---|
| `base.group_user` | `plasticos.transaction` | ✅ | ✅ | ✅ | ❌ |
| `base.group_user` | `plasticos.transaction.line` | ✅ | ❌ | ❌ | ❌ |
| `group_plasticos_manager` | `plasticos.transaction.line` | ✅ | ✅ | ✅ | ✅ |
| `base.group_system` | `plasticos.commission.rule` | ✅ | ✅ | ✅ | ✅ |
| `group_claims_user` | `plasticos.claim` | ✅ | ✅ | ✅ | ❌ |
| `group_claims_manager` | `plasticos.claim` | ✅ | ✅ | ✅ | ✅ |

---

## Prerequisites

- Odoo 19.0 with all `plasticos_*` modules installed
- Test database with demo data loaded
- For controller tests: `HttpCase` requires Odoo HTTP server running
- For CRM bridge tests: `crm` module must be installed

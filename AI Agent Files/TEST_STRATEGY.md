# TEST_STRATEGY.md — PlasticOS Testing Strategy

**Repository**: cryptoxdog/IB-Odoo_19
**Odoo Version**: 19.0
**Test Framework**: Odoo Native (unittest + TransactionCase)

## Overview

PlasticOS employs a layered testing strategy aligned with the 5-layer architecture. Tests are isolated, transactional, and run against a dedicated test database to prevent production data pollution.

## Test Database Configuration

**Test Database**: `odoo_test`

**Environment Variables**:
```bash
ODOO_TEST_DB=odoo_test
ODOO_TEST_MODULES=plasticos_transaction,plasticos_buyer_match_engine
```

**Database Lifecycle**:
- Created fresh for each test run
- Seed data loaded via module installation
- Transactional rollback after each test
- Dropped after test completion (optional)

## Test Execution

### Run All Tests
```bash
./scripts/run-odoo-tests.sh
```

### Run Specific Module
```bash
./scripts/run-odoo-tests.sh plasticos_transaction
```

### Run Single Test Class
```bash
odoo-bin -d odoo_test --test-enable --test-tags /plasticos_transaction/tests:TestTransaction --stop-after-init
```

## Test Coverage

### Current Coverage (2026-02-24)

**Total Tests**: 52 passing
**Modules Tested**:
- `plasticos_transaction`: 47 tests
- `plasticos_buyer_match_engine`: 5 tests

**Untested Modules** (requires seed data):
- `plasticos_enrichment` (KB dependency)
- `plasticos_dev_tools` (utility functions only)

### Coverage Goals

| Layer | Module | Target Coverage | Current |
|-------|--------|----------------|---------|
| 1 - Material | plasticos_material_profile | 80% | 0% |
| 1 - Material | plasticos_intake | 80% | 0% |
| 2 - Capability | plasticos_facility_profile | 80% | 0% |
| 2 - Capability | plasticos_buyer_match_engine | 80% | 100% |
| 3 - Commercial | plasticos_offer | 70% | 0% |
| 4 - Compliance | plasticos_documents | 70% | 0% |
| 5 - Transaction | plasticos_transaction | 90% | 100% |
| 5 - Transaction | plasticos_logistics | 80% | 0% |

## Test Types

### 1. Unit Tests
**Target**: Model methods, computed fields, constraints

**Example** (`test_transaction_commission.py`):
```python
from odoo.tests import TransactionCase

class TestTransactionCommission(TransactionCase):
    def setUp(self):
        super().setUp()
        self.transaction = self.env['plasticos.transaction'].create({
            'name': 'TEST-001',
            'supplier_id': self.env.ref('base.res_partner_1').id,
            'buyer_id': self.env.ref('base.res_partner_2').id,
            'quantity_lbs': 10000,
            'price_per_lb_supplier': 0.50,
            'price_per_lb_buyer': 0.60,
        })

    def test_commission_calculation(self):
        self.assertEqual(self.transaction.gross_profit, 1000.0)
        self.assertEqual(self.transaction.commission_amount, 100.0)
```

### 2. Integration Tests
**Target**: Cross-module workflows, external integrations

**Example** (`test_buyer_matching_integration.py`):
```python
from odoo.tests import TransactionCase
from unittest.mock import patch, MagicMock

class TestBuyerMatchingIntegration(TransactionCase):
    @patch('plasticos_buyer_match_engine.services.graph_service.GraphDatabase')
    def test_match_to_buyers_with_neo4j_fallback(self, mock_graph_db):
        # Mock Neo4j failure
        mock_graph_db.driver.return_value = None

        intake = self.env['plasticos.intake'].create({
            'polymer_id': self.env.ref('plasticos_material_profile.polymer_hdpe').id,
            'quantity_lbs': 20000,
        })

        intake.action_match_to_buyers()

        # Verify fallback to Python-only matching
        self.assertTrue(intake.intake_match_ids)
```

### 3. End-to-End Tests
**Target**: Full transaction lifecycle

**Example** (`test_intake_to_settlement_e2e.py`):
```python
from odoo.tests import TransactionCase

class TestIntakeToSettlement(TransactionCase):
    def test_complete_transaction_flow(self):
        # 1. Create intake
        intake = self.env['plasticos.intake'].create({...})

        # 2. Match to buyers
        intake.action_match_to_buyers()
        self.assertTrue(intake.intake_match_ids)

        # 3. Create offer
        offer = self.env['plasticos.offer'].create({
            'intake_id': intake.id,
            'buyer_id': intake.intake_match_ids.buyer_id.id,
        })

        # 4. Accept offer → Transaction
        offer.action_accept()
        transaction = intake.transaction_id
        self.assertIsNotNone(transaction)

        # 5. Assign load
        load = self.env['plasticos.load'].create({
            'transaction_id': transaction.id,
        })

        # 6. Complete load
        load.action_complete()
        self.assertEqual(transaction.state, 'load_complete')

        # 7. Generate invoice
        transaction.action_create_invoice()
        self.assertIsNotNone(transaction.invoice_id)
```

## Test Isolation Strategy

### Database Isolation
- Each test runs in a transaction
- Rollback after test completion
- No cross-test data pollution

### External Service Mocking

**Neo4j**:
```python
@patch('plasticos_buyer_match_engine.services.graph_service.GraphService')
def test_with_mocked_neo4j(self, mock_graph):
    mock_graph.return_value.execute_query.return_value = [
        {'buyer_id': 1, 'score': 0.95}
    ]
    # Test code
```

**OpenAI**:
```python
@patch('plasticos_web_leads.models.web_lead.openai.Client')
def test_with_mocked_openai(self, mock_openai):
    mock_openai.return_value.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='HOT'))]
    )
    # Test code
```

## Seed Data Strategy

### Test Fixtures
- Located in `tests/fixtures/`
- Loaded via `setUpClass` or `setUp`
- XML-based for referential integrity

**Example**:
```xml
<!-- tests/fixtures/test_partners.xml -->
<odoo>
    <record id="test_supplier" model="res.partner">
        <field name="name">Test Supplier Inc</field>
        <field name="company_type">company</field>
        <field name="supplier_rank">1</field>
    </record>
</odoo>
```

### Seed Data Exclusion

**Modules Disabled for CI** (require production seed data):
```python
# plasticos_enrichment/tests/__init__.py
# from . import test_enrichment  # Disabled for Odoo.sh CI

# plasticos_dev_tools/tests/__init__.py
# from . import test_tools  # Disabled for Odoo.sh CI
```

**Reason**: Knowledge base YAML files not deployed to CI environment.

## CI/CD Integration

### Pre-Commit Tests
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: odoo-tests
      name: Odoo unit tests
      entry: ./scripts/run-odoo-tests.sh
      language: script
      pass_filenames: false
      always_run: true
      stages: [pre-push]
```

### GitHub Actions (Optional)
```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: odoo
          POSTGRES_PASSWORD: odoo
          POSTGRES_DB: odoo_test
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: ./scripts/run-odoo-tests.sh
```

### Odoo.sh CI
- Automatic test run on push to staging
- Seed data loaded from installed modules
- 52/52 tests passing (as of 2026-02-24)

## Test Organization

### Directory Structure
```
plasticos_<module>/
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── test_partners.xml
│   │   └── test_materials.xml
│   ├── test_model_name.py
│   ├── test_integration_workflow.py
│   └── test_e2e_scenario.py
```

### Naming Conventions
- Test files: `test_*.py`
- Test classes: `Test<ModelName>` or `Test<Feature>`
- Test methods: `test_<scenario>_<expected_result>`

## Test Data Management

### Partner Test Data
```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.supplier = cls.env['res.partner'].create({
        'name': 'Test Supplier',
        'company_type': 'company',
        'supplier_rank': 1,
    })
    cls.buyer = cls.env['res.partner'].create({
        'name': 'Test Buyer',
        'company_type': 'company',
        'customer_rank': 1,
    })
```

### Material Test Data
```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.polymer_hdpe = cls.env.ref('plasticos_material_profile.polymer_hdpe')
    cls.form_bales = cls.env.ref('plasticos_material_profile.form_bales')
```

## Performance Testing

### Load Testing (Manual)
```bash
# Create 1000 test intakes
python3 scripts/generate_test_intakes.py --count 1000

# Run matching engine
python3 scripts/benchmark_matching_engine.py
```

**Expected Performance**:
- 10-gate filtering: < 50ms per intake
- Neo4j scoring: < 200ms per intake
- Total matching time: < 250ms per intake

### Stress Testing Neo4j
```bash
# Run concurrent matching requests
./scripts/stress_test_neo4j.sh --concurrent 10 --duration 60
```

## Test Reporting

### Coverage Report
```bash
# Generate coverage report
coverage run --source=plasticos_* odoo-bin -d odoo_test --test-enable --stop-after-init
coverage report
coverage html
```

### Test Results
```bash
# Parse test output
./scripts/run-odoo-tests.sh | tee test_results.log
grep -E "PASS|FAIL" test_results.log
```

## Known Test Limitations

1. **Neo4j Integration Tests**: Require local Neo4j instance
2. **OpenAI Integration Tests**: Require API key (use mocks in CI)
3. **Partner Import Tests**: Require CSV fixtures
4. **Enrichment Tests**: Require knowledge base YAML files

## Test Maintenance

### Adding New Tests
1. Create test file in `tests/`
2. Import in `tests/__init__.py`
3. Follow naming conventions
4. Use fixtures for seed data
5. Mock external services
6. Run locally before commit

### Updating Existing Tests
1. Verify test still covers intended scenario
2. Update fixtures if model changes
3. Re-run full test suite
4. Update documentation if behavior changes

## Test Exclusion Policy

**Exclude from CI**:
- Tests requiring production seed data
- Tests requiring external API keys
- Performance/stress tests
- Manual integration tests

**Include in CI**:
- Unit tests with mocked dependencies
- Integration tests with test fixtures
- Critical path E2E tests

---

**Test Strategy Version**: 1.0.0
**Last Updated**: 2026-02-24
**Maintained By**: PlasticOS QA Team

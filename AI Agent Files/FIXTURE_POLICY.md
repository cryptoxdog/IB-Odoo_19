# FIXTURE_POLICY.md — PlasticOS Test Fixture Policy

**Purpose**: Define rules for test data creation and management.

## Core Principles

1. **Tests never mutate seed data**
2. **Fixtures are isolated and transactional**
3. **External IDs used for stable references**
4. **No production data in test fixtures**

## Fixture Types

### 1. Seed Data References
**Use Odoo external IDs to reference production seed data.**

```python
# ✅ CORRECT: Reference seed data via external ID
polymer = self.env.ref('plasticos_material_profile.polymer_hdpe')
form = self.env.ref('plasticos_material_profile.form_bales')
```

```python
# ❌ WRONG: Search for seed data (brittle)
polymer = self.env['plasticos.polymer'].search([('code', '=', 'HDPE')], limit=1)
```

### 2. Test-Specific Records
**Create test records in setUp or setUpClass.**

```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.test_supplier = cls.env['res.partner'].create({
        'name': 'TEST-SUPPLIER-001',
        'company_type': 'company',
        'supplier_rank': 1,
    })
```

### 3. XML Fixtures
**For complex test data, use XML fixtures.**

```xml
<!-- tests/fixtures/test_partners.xml -->
<odoo noupdate="0">
    <record id="test_supplier_facility" model="res.partner">
        <field name="name">Test Facility XYZ</field>
        <field name="company_type">company</field>
        <field name="supplier_rank">1</field>
    </record>

    <record id="test_facility_profile" model="plasticos.facility.profile">
        <field name="partner_id" ref="test_supplier_facility"/>
        <field name="accepted_polymer_ids" eval="[(6, 0, [ref('plasticos_material_profile.polymer_hdpe')])]"/>
        <field name="volume_minimum">5000</field>
    </record>
</odoo>
```

**Load in test**:
```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.env['ir.model.data'].load_data('plasticos_facility_profile', 'tests/fixtures/test_partners.xml')
```

## Naming Conventions

### Test Record Names
- Prefix with `TEST-` or `FIXTURE-`
- Use descriptive names: `TEST-SUPPLIER-HDPE-BALES`
- Never use names that could collide with production

### External IDs for Test Data
- Format: `test_<model>_<descriptor>`
- Example: `test_partner_supplier_hdpe`, `test_intake_hot_lead`

## Fixture Lifecycle

### Setup Phase
```python
def setUp(self):
    super().setUp()
    # Create test records
    self.test_intake = self.env['plasticos.intake'].create({...})
```

### Teardown Phase
- **Automatic**: Odoo's TransactionCase rolls back after each test
- **Manual teardown not required** (unless explicit cleanup needed)

## External Service Fixtures

### Neo4j Mock Data
```python
@patch('plasticos_buyer_match_engine.services.graph_service.GraphService.execute_query')
def test_matching_with_neo4j(self, mock_query):
    mock_query.return_value = [
        {'buyer_id': 1, 'score': 0.95, 'distance': 50},
        {'buyer_id': 2, 'score': 0.85, 'distance': 100},
    ]
    # Test code
```

### OpenAI Mock Responses
```python
@patch('openai.Client')
def test_web_lead_triage(self, mock_openai):
    mock_openai.return_value.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({
            'classification': 'HOT',
            'confidence': 0.95,
            'polymer': 'HDPE',
        })))]
    )
    # Test code
```

## Fixture Data Volume

### Unit Tests
- **Minimal data**: 1-3 records per test
- **Fast execution**: < 1 second per test

### Integration Tests
- **Moderate data**: 10-50 records
- **Acceptable execution**: < 5 seconds per test

### E2E Tests
- **Realistic data**: 100+ records
- **Acceptable execution**: < 30 seconds per test

## Fixture Maintenance

### Adding New Fixtures
1. Create fixture file in `tests/fixtures/`
2. Use `noupdate="0"` for test data
3. Document fixture purpose in comments
4. Reference in test setUp

### Deprecated Fixtures
- Remove unused fixture files
- Update tests referencing removed fixtures
- Document changes in commit message

## Anti-Patterns

### ❌ Don't Mutate Seed Data
```python
# WRONG: Modifying seed data
polymer = self.env.ref('plasticos_material_profile.polymer_hdpe')
polymer.name = 'Modified HDPE'  # Breaks other tests!
```

### ❌ Don't Use Production Database
```python
# WRONG: Running tests against production DB
# Always use dedicated test database (odoo_test)
```

### ❌ Don't Hardcode Database IDs
```python
# WRONG: Hardcoded IDs (brittle)
partner = self.env['res.partner'].browse(42)

# CORRECT: Use external IDs
partner = self.env.ref('base.res_partner_1')
```

### ❌ Don't Create Fixtures in Test Methods
```python
# WRONG: Creating fixtures in test (slow)
def test_transaction(self):
    supplier = self.env['res.partner'].create({...})  # Repeated for each test

# CORRECT: Create in setUp or setUpClass
@classmethod
def setUpClass(cls):
    cls.supplier = cls.env['res.partner'].create({...})
```

## Fixture Best Practices

### ✅ Use Factories for Complex Objects
```python
def _create_intake(self, **kwargs):
    values = {
        'partner_id': self.test_supplier.id,
        'polymer_id': self.polymer_hdpe.id,
        'quantity_lbs': 10000,
    }
    values.update(kwargs)
    return self.env['plasticos.intake'].create(values)

def test_intake_matching(self):
    intake = self._create_intake(quantity_lbs=20000)
    # Test code
```

### ✅ Use setUpClass for Shared Data
```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    # Shared across all test methods in this class
    cls.polymer_hdpe = cls.env.ref('plasticos_material_profile.polymer_hdpe')
    cls.form_bales = cls.env.ref('plasticos_material_profile.form_bales')
```

### ✅ Document Fixture Dependencies
```python
# test_buyer_matching.py
"""
Test buyer matching engine.

Fixtures Required:
- plasticos_material_profile seed data (polymers, forms, colors)
- plasticos_facility_profile seed data (equipment types)
- test_partners.xml (buyer facilities with profiles)
"""
```

---

**Fixture Policy Version**: 1.0.0
**Last Updated**: 2026-02-24

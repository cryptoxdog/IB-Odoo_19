# CONTRIBUTING.md — PlasticOS Contribution Guide

Thank you for your interest in contributing to PlasticOS! This guide will help you get started.

---

## 📋 Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Code Standards](#code-standards)
5. [Testing Requirements](#testing-requirements)
6. [Commit Message Format](#commit-message-format)
7. [Pull Request Process](#pull-request-process)
8. [Module Development](#module-development)
9. [Documentation](#documentation)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:
- Experience level
- Background
- Identity
- Personal characteristics

### Expected Behavior

- Use welcoming and inclusive language
- Respect differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what's best for the project
- Show empathy towards other contributors

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Trolling or personal attacks
- Publishing others' private information without permission
- Other conduct inappropriate in a professional setting

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.12+ installed
- Docker 24.0+ and Docker Compose 2.0+
- Git configured with your identity
- GitHub account with SSH keys configured
- PostgreSQL 15+ (or use Docker)
- Neo4j 5.15+ (optional)

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone git@github.com:YOUR_USERNAME/IB-Odoo_19.git
   cd IB-Odoo_19
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream git@github.com:cryptoxdog/IB-Odoo_19.git
   ```

### Local Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Start Docker services
docker compose -p plasticos_dev up -d

# Initialize test database
odoo-bin -d odoo_test --init=plasticos_base --stop-after-init
```

---

## Development Workflow

### 1. Create Feature Branch

```bash
# Sync with upstream
git checkout staging
git pull upstream staging

# Create feature branch
git checkout -b feature/my-feature-name
```

**Branch Naming**:
- `feature/` — New features
- `fix/` — Bug fixes
- `refactor/` — Code refactoring
- `docs/` — Documentation changes
- `test/` — Test additions

### 2. Make Changes

- Edit code in appropriate module directory
- Add/update tests
- Update documentation

### 3. Run Quality Checks

```bash
# Run linters
ruff check .
ruff format .

# Run pattern checks
./scripts/check_odoo_patterns.sh

# Run module wiring check
./scripts/check_module_wiring.py

# Run tests
./scripts/run-odoo-tests.sh
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat(intake): add lazy partner creation"
```

### 5. Push and Create PR

```bash
git push origin feature/my-feature-name
# Create PR via GitHub UI
```

---

## Code Standards

### Python Style

**Tool**: Ruff (configured in `pyproject.toml`)

**Key Rules**:
- Line length: 120 characters
- Target Python: 3.12
- Import order: `isort` standard
- Exclude: `__init__.py` from unused import checks (Odoo pattern)

**Run Linter**:
```bash
ruff check .
ruff format .
```

### Odoo-Specific Patterns

**Follow OCA Guidelines**: [OCA Maintainer Guidelines](https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst)

**Key Patterns**:
- Use `@api.model` for class methods
- Use `@api.depends()` for computed fields
- Use `fields.Many2one` (not string writes)
- Always inherit `mail.thread` for chatter
- Use `sudo()` sparingly

**Anti-Patterns** (caught by `check_odoo_patterns.sh`):
- ❌ Direct SQL without parameterization
- ❌ String writes to Many2one fields
- ❌ Missing `@api.model_create_multi` (Odoo 19+)
- ❌ `@api.multi` decorator (deprecated in Odoo 13+)
- ❌ Hardcoded IDs in Python

**Check Patterns**:
```bash
./scripts/check_odoo_patterns.sh
```

### File Structure

**Module Layout**:
```
plasticos_my_module/
├── __init__.py          # Register models
├── __manifest__.py      # Module metadata
├── README.rst           # Module documentation
├── models/
│   ├── __init__.py
│   ├── my_model.py      # Primary model
│   └── my_inherit.py    # Inherited models
├── views/
│   ├── my_model_views.xml
│   └── menus.xml
├── data/
│   └── seed_data.xml
├── security/
│   ├── ir.model.access.csv
│   └── security.xml     # Record rules
├── tests/
│   ├── __init__.py
│   └── test_my_model.py
└── wizards/             # Optional
    ├── __init__.py
    └── my_wizard.py
```

---

## Testing Requirements

### Test Coverage Targets

| Module Type | Target Coverage | Required |
|------------|----------------|----------|
| Core (Layer 5) | 90% | Yes |
| Commercial (Layer 3) | 80% | Yes |
| Material (Layer 1) | 80% | Yes |
| Utilities | 70% | Recommended |

### Writing Tests

**Test File**: `tests/test_<feature>.py`

**Template**:
```python
from odoo.tests import TransactionCase

class TestMyFeature(TransactionCase):
    def setUp(self):
        super().setUp()
        # Set up test data
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'supplier_rank': 1,
        })

    def test_my_feature(self):
        # Arrange
        intake = self.env['plasticos.intake'].create({
            'partner_id': self.partner.id,
            'quantity_lbs': 10000,
        })

        # Act
        intake.action_match_to_buyers()

        # Assert
        self.assertTrue(intake.intake_match_ids)
        self.assertGreater(len(intake.intake_match_ids), 0)
```

**Run Tests**:
```bash
# All tests
./scripts/run-odoo-tests.sh

# Specific module
odoo-bin -d odoo_test --test-enable --test-tags /plasticos_intake/tests --stop-after-init
```

---

## Commit Message Format

### Conventional Commits

**Format**: `<type>(<scope>): <description>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring (no functional change)
- `docs`: Documentation changes
- `test`: Test additions or modifications
- `chore`: Build/tooling changes
- `perf`: Performance improvements
- `style`: Code formatting (no logic change)

**Scopes** (module names):
- `intake`
- `transaction`
- `matching`
- `logistics`
- `documents`
- `web_leads`
- `automation`
- etc.

**Examples**:
```bash
git commit -m "feat(intake): add lazy partner creation for web leads"
git commit -m "fix(matching): correct field names in match_result_views.xml"
git commit -m "refactor(transaction): remove circular dependency on material_profile"
git commit -m "docs: add DEPLOYMENT.md with Docker instructions"
git commit -m "test(transaction): add commission calculation tests"
```

**Breaking Changes**:
```bash
git commit -m "feat(matching)!: implement two-stage orchestrator

BREAKING CHANGE: match_buyers() now requires facility_ids parameter
from Stage 1 Capability Matcher."
```

---

## Pull Request Process

### PR Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines (Ruff passes)
- [ ] All pattern checks pass (`check_odoo_patterns.sh`)
- [ ] Module wiring verified (`check_module_wiring.py`)
- [ ] Tests added for new features
- [ ] All tests passing (`run-odoo-tests.sh`)
- [ ] Documentation updated (README, docstrings)
- [ ] Commit messages follow Conventional Commits
- [ ] No merge conflicts with `staging` branch
- [ ] ACL files updated if new models added
- [ ] `__manifest__.py` version incremented

### PR Template

**Title**: Use Conventional Commits format

**Description**:
```markdown
## What does this PR do?
Brief description of changes.

## Why is this change needed?
Context and motivation.

## Related Issues
Fixes #123
Relates to #456

## Testing
How to test these changes:
1. Step one
2. Step two

## Screenshots (if applicable)
[Add screenshots for UI changes]

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] ACL updated (if new models)
```

### Review Process

1. **Automated Checks**:
   - Ruff linting
   - Pattern checks
   - Test suite
   - Build verification

2. **Code Review**:
   - Maintainer reviews code
   - Requests changes if needed
   - Approves when ready

3. **Merge**:
   - Squash and merge to `staging`
   - Delete feature branch
   - Deploy to staging environment

---

## Module Development

### Creating a New Module

```bash
# Use Odoo scaffold
odoo-bin scaffold plasticos_my_module addons/

# Or manually create structure (see File Structure above)
```

### Module Manifest (`__manifest__.py`)

```python
{
    'name': 'PlasticOS: My Module',
    'version': '19.0.1.0.0',
    'category': 'PlasticOS',
    'summary': 'Short description (< 80 chars)',
    'description': """
Long description with details.
    """,
    'author': 'PlasticOS',
    'depends': [
        'base',
        'plasticos_base',  # Always depend on plasticos_base
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/seed_data.xml',
        'views/my_model_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

### Model Development

**Template**:
```python
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class MyModel(models.Model):
    _name = 'plasticos.my.model'
    _description = 'My Model Description'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], default='draft', tracking=True)

    @api.depends('partner_id')
    def _compute_partner_name(self):
        for record in self:
            record.partner_name = record.partner_id.name or ''

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_('Quantity must be positive.'))

    def action_confirm(self):
        self.ensure_one()
        self.state = 'confirmed'
```

---

## Documentation

### Required Documentation

**Module README** (`README.rst`):
- What the module does
- Dependencies
- Configuration steps
- Usage examples
- Known limitations

**Model Docstrings**:
```python
class MyModel(models.Model):
    """
    My Model manages XYZ functionality.

    Key features:
    - Feature 1
    - Feature 2

    Related models:
    - plasticos.intake
    - res.partner
    """
    _name = 'plasticos.my.model'
```

**Method Docstrings**:
```python
def my_method(self, param1, param2):
    """
    Brief description of what method does.

    Args:
        param1 (str): Description of param1
        param2 (int): Description of param2

    Returns:
        dict: Description of return value

    Raises:
        ValidationError: When validation fails
    """
```

### Documentation Updates

When making changes, update:
- Module README (if behavior changes)
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) (if architecture changes)
- [API_REFERENCE.md](docs/API_REFERENCE.md) (if public API changes)
- [CHANGELOG.md](docs/CHANGELOG.md) (for all changes)

---

## Questions?

- **Technical Questions**: Open a [GitHub Discussion](https://github.com/cryptoxdog/IB-Odoo_19/discussions)
- **Bug Reports**: Open a [GitHub Issue](https://github.com/cryptoxdog/IB-Odoo_19/issues)
- **Security Issues**: Email ib718@icloud.com directly (do not open public issue)

---

**Thank you for contributing to PlasticOS!** 🙏

*Last Updated: 2026-02-24*

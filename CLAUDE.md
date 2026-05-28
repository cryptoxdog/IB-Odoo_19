# CLAUDE.md — PlasticOS (Odoo 19)

@AGENTS.md

**Repo metrics** (module count, line counts, test layout, shell commands): keep **`AGENTS.md`** as the canonical, maintained snapshot; update that file when the addon set or tooling changes.

## Design Principles

1. **Deterministic Seed Doctrine** — all reference data versioned in XML with `noupdate="1"`. No CSV runtime bootstrap. No hardcoded database IDs.
2. **Layer Isolation** — 5 layers (Material → Capability → Commercial → Compliance → Transaction). Higher layers depend on lower, never reverse.
3. **Graph Augmentation** — Neo4j for scoring/matching, Odoo for transactions. Graph failures never block Odoo.
4. **Partner Hierarchy** — native Odoo fields (`customer_rank`, `supplier_rank`) + facility capability profiles. No custom partner booleans.
5. **Intake-First Flow** — supplier intake drives buyer matching. Material profile → intake → match → offer → transaction.
6. **Odoo 19 Strict** — zero deprecated patterns. `models.Constraint` not `_sql_constraints`. No `@api.one`. No `category_id` on groups.

## Code Style Examples

```python
# ✅ GOOD — model constant, proper field declaration, tracking, help text
RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"

class PlasticosOffer(models.Model):
    _name = "plasticos.offer"
    _description = "Plasticos Offer"
    _inherit = ["mail.thread"]

    supplier_id = fields.Many2one(
        RES_PARTNER,
        string="Supplier",
        domain=[("is_company", "=", True), ("supplier_rank", ">", 0)],
        tracking=True,
        index=True,
        help="Supplier partner for this offer.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("sent", "Sent"), ("accepted", "Accepted"), ("cancelled", "Cancelled")],
        default="draft",
        tracking=True,
    )

# 🚫 BAD — hardcoded model string, no tracking, no help, deprecated pattern
class PlasticosOffer(models.Model):
    _name = "plasticos.offer"
    _sql_constraints = [("name_uniq", "unique(name)", "Name must be unique!")]  # ❌ Odoo 19: use models.Constraint

    supplier_id = fields.Many2one("res.partner")  # ❌ hardcoded string, no domain/tracking/help
    is_supplier = fields.Boolean()  # ❌ custom partner boolean — use supplier_rank
```

```xml
<!-- ✅ GOOD — seed data with noupdate, external ID, proper ref -->
<odoo noupdate="1">
  <record id="plasticos_base.partner_tag_buyer" model="res.partner.category">
    <field name="name">Buyer</field>
    <field name="active" eval="True"/>
  </record>
</odoo>

<!-- 🚫 BAD — no noupdate, no external ID prefix, hardcoded ID -->
<odoo>
  <record id="tag_buyer" model="res.partner.category">
    <field name="name">Buyer</field>
  </record>
</odoo>
```

```python
# ✅ GOOD — Odoo 19 constraint pattern
from odoo.models import Constraint, UniqueConstraint

class PlasticosMaterialProfile(models.Model):
    _name = "plasticos.material.profile"
    _constraints = [
        UniqueConstraint("polymer_code", "form_code", name="unique_polymer_form"),
    ]

# 🚫 BAD — deprecated _sql_constraints (Odoo 19 removes this)
class PlasticosMaterialProfile(models.Model):
    _name = "plasticos.material.profile"
    _sql_constraints = [("unique_polymer_form", "unique(polymer_code, form_code)", "Must be unique")]
```

## Boundaries

### ✅ Always
- Declare `__manifest__.py` dependencies before importing from other modules
- Add `security/ir.model.access.csv` for every new model
- Add `from . import <file>` to `__init__.py` for every new Python file (models, controllers, wizards)
- Use `plasticos_` namespace for modules, `plasticos.` for models, `Plasticos` for class names
- `_name` MUST be a string literal — NEVER `_name = SOME_CONSTANT`
- Every `fields.Many2one` MUST have `ondelete=` parameter
- Cross-addon imports MUST be inside functions (lazy loading), never at module top level
- Run `pre-commit run --all-files` before committing (runs all 31 hooks)
- Run `ruff check --fix . && ruff format .` before committing (line length = **120**, not 100)
- Run `python3 scripts/check_module_wiring.py` before committing
- Follow the **CI Compliance Checklist** in `AGENTS.md` — CI will reject PRs that skip these steps
- Check `INVARIANTS.md` for full invariant list (18 invariants, all CI-enforced)

### ⚠️ Ask Before
- Creating new modules (affects dependency graph + install order)
- Modifying `plasticos_base` or `plasticos_security_base`
- Adding/changing `ir.cron` scheduled actions
- Schema changes to `res.partner`
- Neo4j integration changes

### 🚫 Never
- `_sql_constraints` → `models.Constraint` / `UniqueConstraint`
- `@api.one` / `@api.multi` → removed
- `@api.depends("id")` → remove "id"
- `category_id` on `res.groups` → removed in Odoo 19
- `<tree>` in views → use `<list>`
- `attrs="{...}"` on fields → use `invisible=`, `readonly=`, `required=` directly
- `states=` on fields → use direct attribute expressions
- `string=` on `<search>` views → remove it
- `t-esc=` in templates → use `t-out=`
- `numbercall` on `ir.cron` → deprecated
- `self.env.get("model.name")` → use `self.env["model.name"]`
- `x_` prefixed fields
- Circular module dependencies
- `sudo()` without justification
- Hardcoded database IDs → use external IDs
- Top-level `from odoo.addons.plasticos_*` imports in model files

## Imports

```python
@AI Agent Files/AGENT.md
@ARCHITECTURE.md
@INVARIANTS.md
```

## References

Detailed reference material loads from `.claude/rules/` when editing relevant files:
- **Invariants & Contracts** → `.claude/rules/invariants.md`
- **Module Architecture** → `.claude/rules/architecture.md`
- **Security Model** → `.claude/rules/security.md`
- **Testing** → `.claude/rules/testing.md`
- **XML Views** → `.claude/rules/xml-views.md`
- **Neo4j Boundary** → `.claude/rules/neo4j.md`
- **System State** → `.claude/rules/system-state.md`
- **CI Pipeline** → `AGENTS.md` § CI Compliance Checklist (authoritative CI reference)
- **System Invariants** → `INVARIANTS.md` (18 invariants with CI enforcement map)

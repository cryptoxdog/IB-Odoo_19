# CLAUDE.md — PlasticOS (Odoo 19)

@AGENTS.md

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
- Use `plasticos_` namespace for modules, `plasticos.` for models
- Run `pre-commit run --all-files` before committing
- Check `AI Agent Files/INVARIANTS.md` for full invariant list

### ⚠️ Ask Before
- Creating new modules (affects dependency graph + install order)
- Modifying `plasticos_base` or `plasticos_security_base`
- Adding/changing `ir.cron` scheduled actions
- Schema changes to `res.partner`
- Neo4j integration changes

### 🚫 Never
- `_sql_constraints` → `models.Constraint`
- `@api.one` / `@api.multi` → removed
- `@api.depends("id")` → remove "id"
- `category_id` on `res.groups` → removed in Odoo 19
- Circular module dependencies
- `sudo()` without justification
- Hardcoded database IDs → use external IDs

## Imports

```python
@AI Agent Files/AGENT.md
@AI Agent Files/ARCHITECTURE.md
@AI Agent Files/INVARIANTS.md
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

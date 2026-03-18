# ADR-001: Master Data Field Architecture

**Status:** Accepted
**Date:** 2026-03-04
**Deciders:** Igor Beylin
**Scope:** All PlasticOS modules

## Context

PlasticOS manages scrap plastic trading operations with complex material specifications. Materials are described by multiple dimensions (polymer, color, form, packaging, source type, etc.) that need to be:

1. **Consistent** — Same terminology across all modules
2. **Normalizable** — External data (CSV imports, web forms) maps to canonical values
3. **Extensible** — Users can add new values via Odoo UI without code changes
4. **Searchable** — Efficient filtering and grouping in lists/reports

The question: Should these dimensions be **Selection fields** (hardcoded in Python) or **Many2one fields** (referencing master data models)?

## Decision

**Use Many2one fields referencing master data models for all categorical dimensions.**

Each master data model follows this canonical structure:

### Model Structure

```python
class PlasticosXxx(models.Model):
    _name = "plasticos.xxx"
    _description = "Xxx Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. hdpe, post_industrial).",
    )
    description = fields.Text()  # Optional
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "unique(code)",
        "Xxx code must be unique.",
    )
```

### Field Naming Convention

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Human-readable display name | "High-Density Polyethylene" |
| `code` | Canonical lowercase identifier | "hdpe" |
| `sequence` | Sort order in dropdowns | 10, 20, 30... |
| `active` | Soft-delete flag | True/False |
| `description` | Optional extended description | "Includes milk jugs, detergent bottles..." |

### Code Format Rules

- **Lowercase only** — `post_industrial` not `Post_Industrial`
- **Underscores for spaces** — `post_consumer` not `post-consumer` or `postconsumer`
- **Short and mnemonic** — `hdpe` not `high_density_polyethylene`
- **No special characters** — alphanumeric + underscore only

### Reference Field Naming

When referencing master data from other models:

```python
# Pattern: {dimension}_id
polymer_id = fields.Many2one("plasticos.polymer", ...)
color_id = fields.Many2one("plasticos.material.color", ...)
form_id = fields.Many2one("plasticos.material.form", ...)
source_type_id = fields.Many2one("plasticos.source.type", ...)
lead_source_id = fields.Many2one("plasticos.lead.source", ...)
```

### Helper Methods

Each master model SHOULD provide:

```python
@api.model
def get_by_code(self, code):
    """Get record by code, or False if not found."""
    return self.search([("code", "=", code)], limit=1)
```

For models with import normalization needs:

```python
# Module-level mapping dict
XXX_MAPPING = {
    "Raw Value 1": "canonical_code",
    "Raw Value 2": "canonical_code",
    ...
}

@api.model
def normalize_raw_value(self, raw_value):
    """Convert raw import value to canonical record."""
    if not raw_value:
        return False
    code = XXX_MAPPING.get(raw_value.strip(), "other")
    return self.get_by_code(code)
```

## Master Data Models

| Model | Module | Purpose |
|-------|--------|---------|
| `plasticos.polymer` | `plasticos_material_profile` | Polymer types (HDPE, PP, etc.) |
| `plasticos.material.color` | `plasticos_material_profile` | Material colors |
| `plasticos.material.form` | `plasticos_material_profile` | Forms (regrind, pellet, bales) |
| `plasticos.source.type` | `plasticos_material_profile` | Post-industrial, post-consumer |
| `plasticos.packaging.type` | `plasticos_material_profile` | Gaylords, super sacks, etc. |
| `plasticos.filler.type` | `plasticos_material_profile` | Glass filled, talc filled, etc. |
| `plasticos.material.attribute` | `plasticos_material_profile` | Clean, contaminated, etc. |
| `plasticos.lead.source` | `plasticos_facility_profile` | How leads were acquired |

## Data Files

Master data is seeded via XML data files:

```xml
<record id="xxx_code_name" model="plasticos.xxx">
    <field name="name">Display Name</field>
    <field name="code">code_name</field>
    <field name="sequence">10</field>
    <field name="description">Optional description.</field>
</record>
```

**XML ID convention:** `{model_suffix}_{code}` (e.g., `polymer_hdpe`, `lead_source_web_lead`)

## Consequences

### Positive

- **User-extensible** — New values added via UI, no code deployment needed
- **Consistent normalization** — Import wizards map raw data to canonical codes
- **Relational integrity** — Foreign keys prevent orphaned references
- **Audit trail** — Odoo tracks who changed master data and when
- **Reporting** — Group by any dimension in pivot tables and reports
- **Translation-ready** — `name` field can be translated per language

### Negative

- **More models** — Each dimension requires a model, views, security, menu
- **Migration complexity** — Changing from Selection to Many2one requires data migration
- **Lookup overhead** — `get_by_code()` queries vs direct Selection value

### Neutral

- **Sequence-based ordering** — Alphabetical order achieved via sequence values, not automatic

## Alternatives Considered

### Selection Fields (Rejected)

```python
lead_source = fields.Selection([
    ("web_lead", "Web Lead"),
    ("internal", "Internal Research"),
    ...
])
```

**Rejected because:**
- Adding new values requires code change + deployment
- No normalization mapping for imports
- No description/metadata per value
- Harder to report on (string comparison vs relational join)

### Enum + Selection (Rejected)

```python
class LeadSource(Enum):
    WEB_LEAD = "web_lead"
    INTERNAL = "internal"
```

**Rejected because:**
- Same limitations as Selection
- Extra complexity without benefit
- Not Odoo-native pattern

## Compliance

All new categorical fields MUST:

1. Use Many2one to a `plasticos.*` master model
2. Follow the `{dimension}_id` naming convention
3. Include `index=True` for performance
4. Use `ondelete="restrict"` or `"set null"` (never `"cascade"`)

## References

- `plasticos_material_profile/models/` — Canonical implementations
- `plasticos_facility_profile/models/lead_source.py` — Example with normalization mapping
- `plasticos_order_lines/models/purchase_order_line.py` — Example consumer of master data

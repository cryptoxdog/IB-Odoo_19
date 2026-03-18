# ADR-0001: Odoo Action Methods Pattern

**Status:** Accepted
**Date:** 2026-03-04

## Context

Odoo uses action dictionaries to navigate between views. Button clicks on forms need to open related records (e.g., supplier from invoice).

## Decision

Use `ir.actions.act_window` pattern for navigation actions:

```python
def action_view_supplier(self):
    """Open the supplier partner form."""
    self.ensure_one()
    return {
        "type": "ir.actions.act_window",
        "res_model": "res.partner",
        "res_id": self.supplier_id.id,
        "view_mode": "form",
        "target": "current",
    }
```

## Key Parameters

| Parameter | Purpose | Values |
|-----------|---------|--------|
| `type` | Action type | `ir.actions.act_window` |
| `res_model` | Target model | Model technical name |
| `res_id` | Record ID | Single record to open |
| `view_mode` | View type | `form`, `tree`, `kanban` |
| `target` | Window behavior | `current` (replace), `new` (popup) |

## Rules

1. Always call `self.ensure_one()` before accessing `self.field.id`
2. Method name prefix: `action_` for button-triggered methods
3. Return the action dict (don't assign to variable)

## Consequences

- Consistent navigation UX across modules
- Predictable button behavior
- Easy to extend with `domain`, `context`, `views` keys

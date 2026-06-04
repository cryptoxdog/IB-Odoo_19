# ADR-008: Odoo Action Methods Pattern

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Igor Beylin  
**Scope:** All PlasticOS modules with form buttons and navigation actions

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
| `view_mode` | View type | `form`, `list`, `kanban` (Odoo 19: use `list` not `tree`) |
| `target` | Window behavior | `current` (replace), `new` (popup) |

## Rules

1. Always call `self.ensure_one()` before accessing `self.field.id`
2. Method name prefix: `action_` for button-triggered methods
3. Return the action dict (don't assign to variable unless extending)

## Consequences

- Consistent navigation UX across modules
- Predictable button behavior
- Easy to extend with `domain`, `context`, `views` keys

## References

- `tests/test_action_methods.py` — action method coverage
- [84-ci-odoo19-patterns](../../.cursor/rules/84-ci-odoo19-patterns.mdc) — `view_mode` uses `list`

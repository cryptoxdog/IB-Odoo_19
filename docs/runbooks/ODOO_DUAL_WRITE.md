# Runbook: Odoo dual-write controls (TASK-032)

## Flag
| Key | Default | Meaning |
|-----|---------|---------|
| `plasticos.gate.dual_write_enabled` | `0` | Opt-in projection/audit mirror of Gate results |

## Enable
```python
env['ir.config_parameter'].sudo().set_param('plasticos.gate.dual_write_enabled', '1')
```

## Disable / recovery
```python
env['ir.config_parameter'].sudo().set_param('plasticos.gate.dual_write_enabled', '0')
```
Disabling stops new projection mirrors immediately. Reverse generated projection links if needed; do not drop business audit rows.

## Failure modes
| Mode | Behavior |
|------|----------|
| Flag off (default) | No dual-write; Gate path unchanged |
| Flag on | Plan/record projection audit entries only |
| Gate unavailable | Fail closed — no local matcher substitute |
| Attempted local authority | Rejected (`local_intelligence_authority` must stay false) |

## Related
- ADR-125, ADR-003-single-external-intelligence-authority
- Partner writeback remains `plasticos.gate.auto_writeback` (separate control)

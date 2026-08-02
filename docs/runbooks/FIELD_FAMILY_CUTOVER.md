# Runbook: Field-family cutover (TASK-035)

## Scope
| Item | Value |
|------|-------|
| Approved family | `specification` (`plasticos.material.profile` → `plasticos.material.specification`) |
| Blocked | `supply`, `demand` |

## Flags
| Key | Default | Meaning |
|-----|---------|---------|
| `plasticos.gate.field_family_cutover_enabled` | `0` | Opt-in cutover arming |
| `plasticos.gate.field_family_cutover_operator_approved` | `0` | Explicit operator approval gate |
| `plasticos.gate.field_family_cutover_family` | `specification` | Family lock |

Both enable + operator-approved must be `1` to arm. Observation metrics must already be defined in code.

## Observation metrics (required before enable)
- `gate_path_success_rate`
- `gate_path_latency_p95_ms`
- `parity_mismatch_count`
- `local_authority_attempt_count` (must remain 0)

## Arm (not production cutover)
```python
env['ir.config_parameter'].sudo().set_param('plasticos.gate.field_family_cutover_family', 'specification')
env['ir.config_parameter'].sudo().set_param('plasticos.gate.field_family_cutover_enabled', '1')
env['ir.config_parameter'].sudo().set_param('plasticos.gate.field_family_cutover_operator_approved', '1')
```

## Disable / recovery
```python
env['ir.config_parameter'].sudo().set_param('plasticos.gate.field_family_cutover_enabled', '0')
env['ir.config_parameter'].sudo().set_param('plasticos.gate.field_family_cutover_operator_approved', '0')
```
Restores prior field authority. Does **not** re-enable local intelligence / matcher.

## Failure modes
| Mode | Behavior |
|------|----------|
| Flags off (default) | Prior field authority; Gate matching path unchanged |
| Enable without operator approval | Remains `off` |
| Wrong / blocked family | `blocked` — no arm |
| Local authority attempt | Rejected |

## Related
- ADR-127-field-family-cutover, ADR-003-single-external-intelligence-authority, ADR-124
- Dual-write remains a separate control (`plasticos.gate.dual_write_enabled`)

# Runbook: Odoo outcome-replay input (TASK-057)

## Purpose
Produce deterministic JSON fixtures for CEG outcome replay (TASK-033) and cross-service verification (TASK-058).

## Schema (consumer contract)
| Field | Required | Notes |
|-------|----------|-------|
| `schema` | yes | `l9.odoo.outcome_replay_input.v1` |
| `schema_version` | yes | `1.0.0` |
| `producer` / `producer_task` | yes | Identifies Odoo exporter / TASK-057 |
| `gate_mutation` | yes | Always `false` |
| `events[]` | yes | Sorted; each needs `tenant`, `action`, `packet_id` |
| `content_hash` | yes | `sha256:` + hex of canonical body |

## Export
```bash
python3.12 scripts/outcome_replay_export.py \
  --fixture-path /path/to/events.json \
  --output-path /tmp/odoo-replay-input.json
```

Fixture may be a JSON list of events or `{"events":[...]}`.

## Idempotency
Running twice on the same fixture yields the same `content_hash` and identical file bytes (sorted keys).

## Failure modes
| Mode | Behavior |
|------|----------|
| Missing required event fields | Exporter exits non-zero |
| Accidental Gate call | Not implemented — exporter never imports Gate client |
| Bad fixture shape | ValueError |

## Recovery
Delete generated replay JSON. Revert exporter commits if needed. No live system state to roll back.

# Forbidden Scripts — Quarantine Zone

These scripts have been archived from the original `scripts.zip` pack because they violate one or more production safety rules defined in the PlasticOS refactor specification.

## Why They Are Here

Each script in this directory was evaluated against the following hard rules and found to be non-compliant for production deployment.

| Script | Violation | Detail |
|:-------|:----------|:-------|
| `buyer_matching_runtime_v6.0C.py` | Probabilistic scoring / AI matching | Computes match scores between offers and buyers using weighted algorithms. References non-existent `mack.offer.card` and `mack.buyer.card` models. |
| `trust_index_calculator_v6.0C.py` | Probabilistic scoring | Calculates composite trust scores using weighted formulas. References non-existent `mack.buyer.card` model. |
| `mack_offer_handler.py` | Transaction state mutation | Creates and dispatches offers, modifies sale orders. Direct accounting-adjacent mutation. |
| `error_recovery_daemon_v6.0C.py` | Runtime state mutation | Self-healing daemon that restarts modules and modifies system state at runtime. |
| `governance_edit_lock_v6.0.py` | Hardcoded user whitelist | Restricts edits to specific email addresses. Not a proper RBAC pattern. |
| `agent_health_monitor_v6.0C.py` | AI subsystem monitoring | Monitors AI agent health with adaptive baselines. References non-existent agent infrastructure. |
| `system_state_registry_v6.0C.py` | State mutation / rollback | Maintains state snapshots with temporal rollback capabilities. Direct state override. |
| `plastos_module_init_v6.0.py` | Runtime mutation | Bootstrap initializer that writes to `ir.logging` during init hooks. |
| `plastos_event_logger_v6.0.py` | References non-existent models | Depends on `plastos.decision_ledger` which does not exist in the repo. Uses `mack.*` namespace. |

## What To Do With Them

These scripts contain valuable **design patterns and business logic** that can be refactored into production-safe implementations. The recommended path is to extract the deterministic, read-only portions and integrate them into the appropriate PlasticOS modules using `_inherit` patterns and proper ORM methods.

**Do not install or execute these scripts in production.**

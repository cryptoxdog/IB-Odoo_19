# ADR-125: Odoo dual-write controls (Gate projection/audit)

## Status
Accepted (TASK-032)

## Context
Wave-8 needs an explicit, opt-in path to mirror Gate-mediated intelligence results into local projection/audit storage for observability — without restoring local matching or inference as authority.

## Decision
- ICP flag `plasticos.gate.dual_write_enabled` defaults to **off** (`0`).
- When enabled, Odoo may record projection/audit mirrors of Gate results only.
- Gate remains the sole intelligence authority (`gate_authority=true`, `local_intelligence_authority=false`).
- Forbidden: reintroducing `buyer.matcher`, local inference, or any local engine as architectural authority.
- Distinct from `plasticos.gate.auto_writeback` (partner field merge from converge).

## Consequences
Operators must explicitly enable dual-write. Disable instantly by setting the ICP to `0`. TASK-056 consumes dual-write evidence alongside CEG shadow outputs.

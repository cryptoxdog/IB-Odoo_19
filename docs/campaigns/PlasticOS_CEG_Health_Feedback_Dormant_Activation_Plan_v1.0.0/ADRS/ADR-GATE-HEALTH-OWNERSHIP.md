# Proposed Gate ADR amendment: health-assess belongs to CEG

**Status: PROPOSED. Owner: Quantum-L9/Constellation.Gate; existing accepted ADR-action-ownership is authority.**

## Drift to fix

Gate current `CANONICAL_ACTION_OWNERS`/`SEAM_ACTIONS` and `node_registry.yaml` omit `health-assess`. CEG's spec advertises it and has a handler. The existing readiness suite only covers the older seam set, so readiness may pass while health-assess is unroutable.

## Proposed narrow change

- Add canonical `health-assess:ceg`, include it in required action/readiness taxonomy and static graph supported_actions. Keep `enrich` and `graph-inference-result` EIE-only; no `admin` routing.
- Prove correct signed CEG registration, same-owner replicas, cross-owner action collisions, unhealthy/unregistered node, wrong tenant/action claim and exact `health_assess` subaction surface.
- Keep default Gate whole-operation replay OFF (especially any paid `enrich` or mutating feedback). Any new idempotency/retry contract must belong to the domain worker and have durable test proof.
- Update source `tests/architecture/test_seam_route_contract.py` and `tests/runtime/test_routing_readiness.py` with spec/caller parity. Do not authorize auto-enrichment consumer traffic merely by registering a read-only action.

## Activation

No Gate deployment or current action grant is changed in this planning package. Later source-owner ADR acceptance, PR, real route readiness and authorized staging run are prerequisites.

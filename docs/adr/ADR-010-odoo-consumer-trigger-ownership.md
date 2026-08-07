# ADR-010: Odoo Consumer Trigger Ownership (When to Call Gate)

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** Igor Beylin  
**Scope:** Who decides when PlasticOS Odoo emits Gate `TransportPacket`s for match/converge  
**Related:**
[ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md),
[ADR-009-enrichment-selection-ranking-not-in-odoo.md](ADR-009-enrichment-selection-ranking-not-in-odoo.md),
[ADR-011-intelligence-action-topology.md](ADR-011-intelligence-action-topology.md),
[`docs/track_b/04_odoo_gate_consumer_wiring.md`](../track_b/04_odoo_gate_consumer_wiring.md)

## Context

CEG and EIE execute intelligence when requests arrive. Operators and agents need a clear rule for **who opens those requests**. Confusion arose when enrichment cron was retired: some assumed workers would self-schedule work; others assumed Odoo still batch-selected partners.

## Decision

### 1. Odoo alone owns the consumer trigger

Only IB-Odoo_19 (via `plasticos_gate` + calling modules) may decide **whether and when** to emit:

- `action=match` (from intake / match orchestrator)
- `action=converge` (from enrichment run execute/retry)

Allowed trigger classes (all Odoo-side):

| Trigger | Current status |
|---------|----------------|
| Explicit UI / RPC action | **Active** — e.g. Match to Buyers, enrichment `action_execute` |
| Operator retry | **Active** — retryable/failed/degraded runs |
| Future event hooks / automations | Allowed if they call the same Gate seams |
| Consumer of an external ranked queue | Allowed later — Odoo still emits the packet (see ADR-017) |
| EIE or CEG deciding Odoo CRM writes | **Forbidden** |

### 2. Enrichment cron is not authority

`plasticos_enrichment` daily/inference crons are `active=False` and no-op (M4). They must not be treated as the product scheduler. Restoring a cron is an Odoo **consumer** choice and must not reimplement CEG ranking (ADR-009).

### 3. Workers never own Odoo write timing

EIE/CEG must not push unsolicited CRM mutations into Odoo outside a Gate response to an Odoo-initiated packet (or a later explicitly accepted consumer contract).

## Consequences

### Positive

- Clear split: Odoo triggers → Gate routes → worker executes → Odoo maps.
- Prevents “the engine will enrich everyone overnight” assumptions inside this repo.

### Negative / constraints

- Until an external queue consumer is wired, enrichment volume is operator/manual driven.
- Agents must not move scheduling into EIE “for convenience.”

### Implementation rules (agents)

1. New batch enrichment must call existing Gate client seams from Odoo (or document a new consumer ADR).
2. Do not add CEG/EIE callbacks that write `res.partner` without an Odoo-initiated request/response path.
3. Cite this ADR with ADR-009 when discussing schedules vs ranking.

## References

- `plasticos_matching/models/match_orchestrator.py`
- `plasticos_enrichment/models/enrichment_run.py` (`action_execute`, cron no-ops)
- `plasticos_gate/services/gate_client.py`

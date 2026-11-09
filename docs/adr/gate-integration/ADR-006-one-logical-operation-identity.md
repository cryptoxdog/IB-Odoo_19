# ADR-006: One logical operation identity spans replay boundaries

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Transport replay prevention and domain persistence idempotency operate at
different layers and are implemented by different owners (Gate_SDK and EIE
respectively). They must remain separate mechanisms, but when they refer to the
same business operation they must agree on *which* operation that is.

Independently generated values — for example a transport key derived from a
payload digest and a domain key derived from a run id — describe the same
execution with two different names. Nothing downstream can then correlate a
transport replay with the durable run it belongs to.

## Options Considered

### Option A: One logical identity, reused at both boundaries (chosen)
- Pros: transport replay and domain persistence agree on operation identity;
  a retry of one durable run is recognisable as such at every layer; audit can
  join transport records to Odoo run records.
- Cons: a retry of the same run after the source record changed carries the
  same identity, so a deduplicating downstream may serve the earlier answer.
  That is the accepted trade-off, and it is what "same run" is defined to mean
  (see Consequences).

### Option B: Payload-digest transport key, separate domain key
- Pros: a retry after the partner was edited is treated as a materially
  different request and cannot receive a stale answer.
- Cons: two unrelated names for one logical operation; "same operation" ceases
  to be a business fact and becomes a serialization fact — dict ordering or an
  unrelated field edit changes identity. **Rejected**: it makes replay identity
  undecidable from Odoo's own state.

### Option C: Random key per attempt
- Pros: trivially unique.
- Cons: defeats replay prevention entirely.

## Decision

Every durable Odoo enrichment run has one stable logical operation identity,
preferred semantic form:

```
odoo:enrichment:<durable-run-id>
```

Generate this identity **once**. Use that same logical value wherever required
by the EnrichRequest domain idempotency field, the `TransportPacket` header
idempotency field, and Odoo execution audit state.

Transport idempotency and domain persistence idempotency remain **different
mechanisms**. They share a logical identity; they do not become one subsystem.

Required behavior:

| Situation | Operation ID |
|---|---|
| same durable run, retried | same |
| same partner, new enrichment run | different |
| different partner | different |

## Consequences

- Re-running converge on the same durable run is, by definition, the same
  logical operation. An operator who needs a materially new request creates a
  new run — which is the business act that means "ask again".
- Odoo generates the identity; Gate_SDK owns its transport representation; EIE
  owns its durable domain semantics.

## Invariant

```yaml
id: INV-ONE-LOGICAL-OPERATION-ID
statement: >
  One durable Odoo enrichment execution has one stable logical
  operation identity reused consistently across the domain and
  transport replay boundaries.
severity: release_blocking
```

## Amendment 2026-11-08 — an operator retry is a new attempt identity

**Status:** Accepted. Aligns this ADR with the code. It does not change behaviour.

The Required behavior table's first row ("same durable run, retried → same")
and the first Consequence ("re-running converge on the same durable run is,
by definition, the same logical operation") are superseded. The code already
gives each operator retry a new identity:

- `plasticos.enrichment.run.gate_attempt` starts at 1.
  `action_retry_enrichment()` increments it before calling `action_execute()`
  again.
- `plasticos_gate/services/gate_builders.py::build_operation_id(odoo_ctx,
  attempt=n)` returns `odoo:enrichment:<db>:<model>:<record-id>` for attempt 1
  and appends `:attempt-<n>` for a retry.

**Why.** Gate caches the response to a logical operation under its identity,
and that includes an EIE domain failure (`state="failed"`). A retry under the
failed attempt's identity was answered from that cache for the lifetime of the
Gate process and never reached EIE again. A retry is the business act meaning
"ask again", so it is a new operation.

Replacement table:

| Situation | Operation ID |
|---|---|
| same attempt of the same durable run (transport replay) | same |
| same durable run, operator retry | different (`:attempt-<n>`) |
| same partner, new enrichment run | different |
| different partner | different |

**Unchanged.** One identity per attempt, generated once and reused at both
replay boundaries (the EnrichRequest `idempotency_key` and the TransportPacket
header). No payload digest, timestamp or randomness (Option B and Option C stay
rejected). A retry stays correlatable with its run: same prefix, explicit
attempt suffix.

The invariant reads, from this date:

```yaml
id: INV-ONE-LOGICAL-OPERATION-ID
statement: >
  One attempt of a durable Odoo enrichment execution has one stable
  logical operation identity, reused consistently across the domain and
  transport replay boundaries. An operator retry is a new attempt.
severity: release_blocking
```

Enforced by `tests/test_gate_canonical_contract.py`
(`test_operation_id_is_stable_for_the_same_attempt_of_the_same_run`,
`test_operator_retry_is_a_new_operation_id`) and
`plasticos_enrichment/tests/test_gate_enrichment_fallback.py`
(`test_operator_retry_advances_the_operation_attempt`).

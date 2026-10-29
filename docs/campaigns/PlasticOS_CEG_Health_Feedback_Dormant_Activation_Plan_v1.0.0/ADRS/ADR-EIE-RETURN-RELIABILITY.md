# Proposed EIE ADR: durable graph return reception and bounded convergence

**Status: PROPOSED. Owner: Quantum-L9/Enrichment.Inference.Engine.**

## Context

`GraphReturnChannel` currently stores target instructions in per-process `asyncio.Queue`, silently discards when full while returning accepted count, and waits for a separate future convergence pass to consume. The existing graph sync/idempotency infrastructure does not by itself establish durable return-channel semantics.

## Proposed decision

1. Preserve `graph-inference-result` as an EIE-owned, signed Gate action using packet tenant and explicit entity identity, rule/field/confidence/provenance. Missing/invalid outputs fail closed.
2. Distinguish genuinely durable accepted targets from partially accepted/rejected/full/unknown and actual convergence consumed. Never return overall success for a silently dropped or unpersisted target.
3. Reuse existing EIE persistent result/inbox primitives after owner proof. If none can guarantee restart-safe receipt, introduce the smallest source-owned durable target work record and a migration/recovery plan; no new general event platform.
4. On a properly admitted target, trigger/arrange only a bounded authorized next convergence operation. Prevent strong source facts being overwritten and cap repeat feedback per source version/tenant/field; no infinite CEG/EIE ping-pong or uncontrolled provider costs.
5. Full EIE convergence and CEG graph sync acknowledgement remain distinct. Consumer ack must be correlated to the original return target and graph revision.

## Acceptance

P10-P16, P17, P19-P20 with actual process restart, replica routing, queue-full, replay, cross-tenant, stronger-source precedence, non-convergent/timeout and loop prevention witnesses. Current process-local channel is not sufficient to claim production-grade full loop.

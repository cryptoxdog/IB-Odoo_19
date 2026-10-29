# Two live circuit paths and required wiring

## Path A: health -> actual enrichment

```
CEG tenant-scoped graph (existing GraphDriver)
    -> due entity loader (missing)
    -> health assessment / missing fields (exists)
    -> ROI ranking (exists, heuristic)
    -> authorized budget and durable job selection (missing)
    -> scheduled dispatcher (missing)
    -> CEG GateSDK -> Gate action=enrich (exists)
    -> EIE enrich and persistence (exists as broader pipeline)
    -> EIE Gate -> CEG graph sync acknowledgment (exists in separate pipeline)
    -> CEG health re-assessment / outcome recording (not proven wired)
```

**Current broken links:** no loader, no running scheduled owner, no queue consumption, read-only assessment currently capable of accidental provider spending, cost estimates not hard budget, end-to-end outcome not verified.

| Wire | Producer -> Consumer | Required scope, fields, identity | Acknowledge only when | Failure classification |
|---|---|---|---|---|
| W01 | GraphDriver -> health scanner | Signed tenant/domain/DB, stable due entities, node label and actual fields | Known bounded entities loaded or explicit genuine empty set | No loader is UNAVAILABLE, not empty-success |
| W02 | scanner -> ROI and decision | Missing/gating fields, source revisions, due policy, estimated tokens and explicit verified budget | Deterministic ranked work and reason per entity | Unknown data/heuristic confidence = abstain |
| W03 | durable operation -> worker | Tenant, entity, field-set, health/source revision, budget lease, due time | Durable admission and server-side allowlist | Double leader/expired operation cannot dispatch |
| W04 | CEG -> Gate enrich | SDK signed packet, EIE-owned action, stable key, permitted fields/tenant | Gate+EIE worker returns correctly correlated accepted result | HTTP200/failure packet or wrong tenant is failure |
| W05 | EIE result -> CEG sync | Persisted evidence and target endpoint, exact revision and graph relation | CEG sync ack for intended identity and exact source revision | Pending graph sync never reported complete |
| W06 | graph change -> CEG reassessment | Refreshed field values and source provenance | Measured before/after health + no stale revision | No change/timeout must be recorded honestly |

## Path B: graph inference -> EIE feedback

```
CEG authorized graph rule results
    -> NON-admin production event producer (missing)
    -> graph output list with confidence/rule provenance (exists)
    -> CEG GateSDK -> Gate graph-inference-result (exists)
    -> EIE GraphReturnChannel receiver (exists, process-local)
    -> durable queue/receipt (missing)
    -> authorized next convergence pass (currently only opportunistically consumes)
    -> updated evidence -> Graph sync -> health re-assessment (not yet proven)
```

| Wire | Producer -> Consumer | Required behavior | Prohibited shortcut |
|---|---|---|---|
| W07 | Graph rules -> CEG feedback producer | Only domain-authorized rules and new source-backed revisions, output floor + provenance, bounded recursion | Never route arbitrary admin emit subaction via Gate |
| W08 | CEG -> Gate -> EIE | EIE owns graph-inference-result, one SDK route; idempotent output identity | Never call peer directly or alter canonical owner |
| W09 | EIE receiver -> recoverable inbox | Tenant/entity scoped, dedup, immutable packet provenance, capacity/partial/full/error receipt | Queue-full drop reported as accepted is not convergence success |
| W10 | pending result -> authorized EIE convergence | Re-enter for same tenant/entity only, preserve strong original source, loop budget, no perpetual recursions | Cannot overwrite operator evidence or auto-start unlimited provider calls |
| W11 | EIE -> Gate -> CEG graph -> health | Acknowledged graph write, source version and measured improvement | Receipt-only or queued-only not a closed loop |

## Canonical Gate action registry

CEG's `engine/spec.yaml` **already advertises** `health-assess`, but Gate `CANONICAL_ACTION_OWNERS`, `SEAM_ACTIONS` and its static node registry omit it. Source owner Gate must admit an exact owner and test runtime readiness. Preserve `enrich` and `graph-inference-result` as EIE actions. The Gate SDK signs transport; node registration/health alone is not permission for paid dispatch.

## Read-only action purity

Today CEG `handle_health_assess()` may call `trigger_reenrichment_v2()` when flags are on. The plan deliberately changes that behavior: inbound assess/report/batch remain introspection, while a server-controlled scheduled work operation alone initiates paid enrichment. Do not relabel `health-assess` as a generic paid action to avoid the separation.

## Cost and dedup contracts

- Existing `HEALTH_BATCH_COST_CEILING_USD` defaults $10 (estimated), nightly scan default is $50 (estimated), and priority ROI uses assumed $1,000 deal value if the domain description doesn't say otherwise. None is verified spend. Configure actual authoritative budget as an owner-approved ceiling; no spending before that approval.
- Dedup includes packet tenant, entity, fields, source health/input revision, operation and domain policy/rule version. A time window alone is insufficient and reused keys must not cache stale results across revisions.
- Actual provider spend/calls/latency are observed separately from estimates; reject changes that simply report estimates as actual payments.
- Graph return accepted != EIE durable != converge performed != CEG graph synced != improved readiness. Each state needs exact receipt.

## Evidence and provenance

Each result includes input graph revision, target fields, evidence provenance, domain/rule version, confidence source, denial/skip reason, operation/packet IDs and source tenant. Graph data cannot elevate an inferred value to verified fact by recirculation. Source values outrank loop guesses. No Odoo entity identity or partner creation needed.

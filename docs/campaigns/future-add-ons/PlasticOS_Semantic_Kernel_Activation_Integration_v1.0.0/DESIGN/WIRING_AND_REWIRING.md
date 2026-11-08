# Wiring and rewiring contract

These are required integration obligations, not evidence that connections already exist. Every row has a source owner, data/effect boundary and positive/negative proof. Exact network payload shapes are admitted at U01, never inferred from the names below.

| Seam | Producer -> consumer | Required mapping / behavior | Denial or failure | Proof |
|---|---|---|---|---|
| W01 | Source evidence -> EIE through Gate | Exact entity/facility, permitted source fields, evidence references, request scope, rule/domain version | Missing source access, wrong tenant, cost not authorized, stale evidence | P06/P12/P33 |
| W02 | EIE rule execution -> durable evidence | Output remains inferred; rationale, provenance, prerequisites, conflicts, confidence method, expiry | Unattributed result, rule failure or persistence failure cannot report completed commercial truth | P06/P32 |
| W03 | EIE evidence -> Odoo review | Existing signed result path mapped to native read-only views; preserve evidence owner and reference | Public/portal access or unauthorized company refused; no partner/PO/email writes | P19/P20/P32 |
| W04 | Native approved opportunity -> derived supply | Reuse material profile and exact approved load snapshot; stable source identity, revision, availability | No opportunity, no profile, missing approval, unknown marketability or wrong owner blocks publication | P04/P07/P10 |
| W05 | Confirmed buyer inquiry -> derived demand | Typed verified requirement, not capability; source link and need window | Inferred need, nominal capacity or missing evidence cannot enter confirmed demand | P05/P07 |
| W06 | Native commit -> projection operation | Durable operation created atomically with approved source transition; dispatch only after source commit | Source rollback leaves no externally visible publication; crash is recoverable without duplicate identity | P08/P21/P27 |
| W07 | Projection operation -> plasticos_gate -> Gate | Only single existing SDK seam; exact tenant/source/action scope and stable idempotency key | Unadmitted sync/gap permission remains denied; no worker impersonation | P03/P12/P31 |
| W08 | Gate -> CEG source sync | Owner-admitted node AND edge projection, source revision ordering and typed identity | Valid HTTP without valid worker result/ack is failure; partial graph update cannot count as complete | P12/P13 |
| W09 | CEG materialization -> acknowledgement | Confirm expected entity IDs, revision/digest, node/edge outcomes; operator readback witness | Count-only acknowledgement, wrong endpoint or different content cannot close operation | P13/P26 |
| W10 | Opportunity Run Matching -> CEG | Current approved snapshot, correct commercial role/direction, tenant policy/exclusions | Closed/unapproved opportunity, unsupported contract or missing capability fails closed | P14/P16/P30 |
| W11 | Confirmed demand -> current graph supply | Correct compatible current supply only; no capability substitution | Hypothesis, expired/withdrawn/reserved quantity or unknown allocation excluded | P15/P18 |
| W12 | CEG candidates -> single Odoo review | Exact resolvable identities, scores/scale, reasons/evidence, source/run revision | Duplicate result authorities and guessed partner/name mapping forbidden | P16/P22 |
| W13 | Confirmed facts + eligible matching -> CEG gap report | Scoped coverage, allocation, uncertainty, missing-evidence distinction | Empty data or provider failure is information gap/unknown, not confirmed shortage | P17/P18 |
| W14 | Gap/research result -> native CRM handoff | Explicit human qualification; reuse/create lead or link existing opportunity with source refs | No inference-driven active offer, supplier creation or second pipeline | P19/P20 |
| W15 | Native PO/Lost/archive/expiry/reopen -> listing state | Consume source-owned event, preserve history, revalidate on reopen; explicit remaining quantity and owner | Won at procurement cannot be treated blindly as resale; old approvals cannot revive listing | P21 |
| W16 | Disable/recovery -> every mutation/dispatch consumer | Recheck gate at execution, pause queued jobs, retain evidence, safe projected stale state | Cached enable, restart, cron or retry cannot bypass disable | P03/P27/P29 |
| W17 | Material identity reconciliation -> semantic/graph references | Preserve original source, UUID and historical refs; explicit redirects if necessary | Cascade delete, unrelated material merge or guessed partner rejected | P09/P10 |
| W18 | Confirmed outcomes -> future evaluation | Typed offer, opportunity, PO, fulfillment meanings; idempotent outcomes | PO mistaken for delivery/revenue; buyer rejection mistaken for supplier failure | P21/P32/P33 |

## Rewiring of existing surfaces

1. `semantic_payloads.py` becomes an owner-approved source mapper, not an assumed live client. Its `direction`/nested-facts wrappers must be reconciled with live `MatchRequest.match_direction` and CEG handler shape. Preserve peer supply/demand protocols and explicitly version any change.
2. `field_family_cutover.py` remains a distinct read-authority control. Add real consumers only for admitted operations. It is not a backfill enable flag and not permission to infer current supply/demand from old records.
3. `semantic_kernel_backfill.py` remains explicit/offline by default. The optional authorized adapter reads actual scoped sources and records committed effects. Removing a blocked-family constant cannot be the implementation.
4. `plasticos.supply.opportunity` and `plasticos.buyer.demand` remain data representations. Independent trading screens/actions are removed or restricted without destroying records. The CRM opportunity owns commercial state.
5. The commercial campaign owns the legacy dual match-review consolidation and partnerless offer/matching guards. Consume one accepted result interface. Do not bridge both old mechanisms as permanent authorities.
6. Current `supplier_partner_id` requirements cannot be bypassed by fabricated partners or broadened sudo. Use existing prospect-owned facility/material identities and explicit versioned mapping.
7. EIE sync is for its owned evidence. Native facts do not transit EIE just to acquire write privilege. Gate must admit an actual legitimate projection operation.
8. Required graph edges such as `FULFILLS_POLYMER`, `OFFERS` and facility capability relations must exist and be maintained with revisions. Creating a SupplyOpportunity node alone is not working matching.
9. Every registered handler/capability, action owner, client builder, schema/example, result mapper and test fixture must agree on the same active contract version. A detached schema passing validation is not live consumer reachability.
10. All timers/expiry/publishing remain disabled by default and require separate operation scope. An upgrade must never auto-enable schedules or paid enrichment.

## Inbound/outbound distinction

Multiple origins may create native opportunities. There is one commercial execution owner. Technical egress remains appropriate to its concern: intelligence through Gate; approved commercial email through the separate native mail workflow. This package adds no alternate offer sender.

## Requested source/contract proof before coding

Inspect actual command owners and call graphs for EIE durable results, CEG sync/edge writes, Gap route admission, Gate caller policy, Odoo dual_write and native PO/CRM events. Source identified by search is not an implemented API guarantee. F02-F04 explicitly block guesses.

# Every unblock is a scoped replacement, not a switch removal

| Gate / missing connection | Owner and current source | Required safe change | Evidence before allowing use |
|---|---|---|---|
| Automatic supply/demand denial | Backfill engine; ADR-124 | Keep default blocked. Admit only verified source contracts and reviewed batches; ambiguous conversions stay blocked | P04/P05/P08/P09 |
| Fixture-only / forced dry-run CLI | Backfill CLI | Real read adapter plus authorized ORM persistence behind explicit execute boundary; ordinary path remains dry-run | P01/P03/P08 |
| In-memory created counter | Backfill engine | Commit-bound counts and durable stable business identity; no created label from set insertion | P08/P09 |
| Specification-only authority | Field-family cutover + ADR-127 | Separate source-authority admission from migration; guard actual consumers and preserve specification behavior | P02/P03/P27/P29 |
| Optional addon excluded | Manifest/install-order/test owners | Keep default exclusion; isolated opt-in install/test lane; business enable remains separate | P23/P24/P28 |
| Native source absent/ambiguous | Semantic supply/demand and optional bridge | Type and bind authoritative source, material profile, approved snapshot, company, evidence and validity | P04/P05/P10 |
| Partner required before Won | Current semantic/matching guards | Reuse lead-owned facility/material identity; contract-correct prospect source refs; no placeholder partner | P10/P30 and external commercial gate |
| Mapper and live contract mismatch | Odoo Gate + CEG contracts | Version/admit producer/consumer shape together; no direct connection of stale direction wrapper | P02/P07/P12/P16 |
| Missing dispatch / durable lifecycle | Optional integration + existing Gate seam | Source commit -> durable operation -> governed publisher -> acknowledged graph revision | P08/P12/P13/P21/P27 |
| Node-only graph | CEG sync/traversal owners | Required typed edges and lifecycle deletion/revision ordering, proven by readback and match | P13/P15/P26 |
| Caller scope denied/unknown | Gate owner/operator | Verify current deployed grants; narrowly admit required source projection/gap action; no worker role theft | P12/P31 |
| Industrial rule set incomplete | EIE domain/rule owners | Source-backed rules and explicit hypotheses, negative cases, actual runtime invocation and calibration | P06/P32/P33/P34 |
| Gap application missing | CEG | Scoped gap operation with quantity allocation/coverage, unknown outcomes and clear source boundaries | P17/P18 |
| Broad manual writes/standalone workflow | Odoo ACL/UI/admission owner | Read-only derived records, checked approval actions, company rules and single native commercial handoff | P19/P20/P22 |
| Stale listing after disable/closure | Projection + native lifecycle owners | Revision-bound expiry/withdrawal and dispatch-time disable; no PO/sold conflation | P21/P27 |
| No full system receipt | Release-set/E2E owner | Actual registry, workers, graph, IDs, source revisions, persisted Odoo result and negative paths | P24-P28 |
| No operator activation | Operator | Fresh authorization for exact release, tenant, operations, limits and recovery | P29/P34 |

**Never unblock by:** deleting deny lists alone; auto-installing into the primary database; weakening tests; marking an in-memory plan as committed; treating a signed empty response as business success; granting generic sync privileges; or promoting inferred information to active inventory.

The locks are intentionally removed or narrowed last, after their replacement controls and call-site consumers are implemented and proven. Runtime unknowns F01/F04/F08 are not solved by changing a configuration constant.

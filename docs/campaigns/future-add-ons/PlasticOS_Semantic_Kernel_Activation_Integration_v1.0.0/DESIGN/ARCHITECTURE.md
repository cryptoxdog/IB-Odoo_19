# Architecture and minimum realization

## 1. The outcome

Give a salesperson two different kinds of useful answers without confusing them:

- **Research answer:** this facility may need a material, or may generate a saleable scrap stream, because of cited capabilities, products, processes and evidence. The answer includes uncertainty and what must be verified.
- **Commercial answer:** this verified, currently available material matches a confirmed buying requirement under the correct material, timing, quantity, geography and counterparty constraints.

A gap assessment can then distinguish known unmet requirements, currently unmatched supply and missing information. It must never turn an empty graph or an unavailable service into a claim about the whole market.

## 2. Existing foundation, not an already working application

Odoo's accepted ADR-122 places persistence in `plasticos_semantic_kernel` while keeping matching in Gate/CEG (S01). Six records cover material specifications, observations, facility rules, capacity observations, supply and demand (S09-S15). EIE owns evidence/inference (S31-S36); CEG has two domain match directions and active-supply primitives (S37-S43). The backfill CLI and cutover classifier are not proven publishers or side-effect guards (S06-S08).

The optional addon is excluded from the default Staging critical installation path (S26). Whether it is actually installed in any live database is F01, not an inference from a manifest.

## 3. Concern ownership

| Concern | Authoritative owner | What it must not own |
|---|---|---|
| Raw submission and source documents | Original Web Lead/source record and attachments | Automatic commercial truth or new supplier identity |
| Commercial attempt and outcome | Native CRM opportunity; accepted commercial campaign | Inference algorithms or a parallel semantic sales pipeline |
| Reusable material identity | Existing material/facility profile ownership | Current inventory, negotiated terms or per-offer lifecycle |
| Current offered lot/contract | Opportunity-linked material snapshot | Silent updates from a reusable profile after approval |
| Attributed observations and semantic facts | Existing passive semantic models, where justified | Direct Gate calls, scoring or independent trading |
| Rule execution and industrial hypotheses | EIE domain/rule/evidence owners | Confirmed orders, PO issuance, financial or supplier writes |
| Graph projection, matching and scoped gaps | CEG domain/graph owners | Odoo business-record authority |
| Transport, signatures, routes, caller policy | Gate_SDK + Constellation.Gate | Business evidence promotion |
| Odoo integration and operator review | Proposed optional `plasticos_semantic_bridge`, after F05 | A second transport SDK, local intelligence engine or outbound offer sender |

## 4. Selected candidate and alternatives

**Candidate for acceptance:** preserve passive semantic models and their existing IDs; use one optional integration bridge for native-source admission, durable projection operations and native operator review. Published supply/demand rows are derived representations, not independently editable opportunities. EIE and CEG retain their existing domains. No new repository or general event platform is planned.

**Alternative A: install unchanged. Rejected.** It exposes manual forms and broad writes but supplies no tested publisher, industrial inference or lifecycle integration. It creates an apparent second pipeline.

**Alternative B: direct CRM/intake -> graph projection only. Retained as the strongest contraction alternative.** It may be sufficient for one-off matching and should win if existing evidence/run stores can also satisfy full hypothesis provenance, confirmed fact retention, migration and recovery. F05 requires demonstrating why existing owners cannot satisfy these needs before adding any bridge or journal. The current package does not claim that comparison was executed against the installed registry.

**Alternative C: put Gate/client execution inside the passive kernel. Rejected under current ADR-120.** It mixes storage and transport authority. An amendment for passive model maturity is not permission to reintroduce intelligence there.

**Alternative D: hard-depend on the kernel from mandatory CRM/Intake/Gate addons. Rejected.** That would install or activate optional features in the primary operational path and break the dormancy boundary.

### Why a narrow bridge can be justified

The existing mandatory CRM bridge has no dependency on the optional kernel. The kernel expressly forbids client/matching/inference execution. The low-level Gate client must not own the commercial lifecycle. An optional bridge depending on both can join them without pulling the kernel into the mandatory install path. This is a concrete dependency/ownership problem, not a preference for another layer.

A durable projection-operation record is justified only if existing `dual_write` or run/evidence persistence cannot already provide it. The discriminating failure case is: native source transaction commits, graph dispatch times out, then the process restarts. The system must recover the exact source revision and operation identity without fabricating graph success or reissuing a different commercial action. Reuse an existing adequate owner first.

## 5. Logical flow

```
Authoritative source facts and documents
            |
            +--> Gate --> EIE --> attributed hypotheses / missing-evidence requests
            |                              |
            |                         operator review
            |                              |
            +--> qualified material/profile + native source evidence
                                           |
                                  approved CRM opportunity snapshot
                                           |
                             durable admitted semantic projection
                                           |
                                      Gate --> CEG
                                           |
                     materialized nodes + edges + current availability
                                           |
                   Match / reverse match / scoped gap assessment
                                           |
                        read-only result + evidence in Odoo
                                           |
              explicit native CRM lead/opportunity handoff only
```

Authoritative source synchronization does **not** require running inference. Do not funnel verified Odoo facts through EIE merely to borrow a worker's write permission. A permitted projection caller must be explicitly admitted through Gate; consumer identity must not be elevated to a worker.

## 6. No second commercial source of truth

All matching and commercial offer selection remains reachable from native opportunities. The optional bridge may show observations and diagnostics through read-only related screens. It cannot set supplier/contact master data, mark Won, issue PO, send email or negotiate. It may propose a new research lead; an explicit qualification step creates/reuses an actionable opportunity only when material evidence and commercial scope support it.

The semantic model name is preserved for compatibility. Its independent commercial entry and editable lifecycle are superseded by the native opportunity owner. Historical records and UUIDs are not deleted just to simplify that ownership change.

## 7. Domain-neutral engines

Plastics process/product knowledge belongs in the versioned PlasticOS domain pack and approved rules. Generic EIE and CEG code may implement reusable evidence, traversal, matching, unit and gap mechanisms, but must not contain Odoo-specific partner guesses or PlasticOS hardcoding. Provider field names and tenant identities must come from their admitted contracts.

## 8. Architectural status

Business intent: operator locked. Source design candidate: formalized. Full runtime/source closure and optional-bridge necessity: not proven. No claim of canonical L9 projection consumption, global architecture admission or independent acceptance is made by this pack. F01-F10 define the remaining gates without moving the goalposts.

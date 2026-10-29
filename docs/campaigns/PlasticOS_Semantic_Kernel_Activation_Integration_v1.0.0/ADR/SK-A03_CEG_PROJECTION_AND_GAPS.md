# Proposed ADR SK-A03: authoritative source projections and scoped gap assessment

**Status:** Proposed. No action registration, graph migration or production activation authorized.
**Proposed owner/path:** Quantum-L9/Cognitive.Engine.Graphs, docs/adr/PROPOSED-source-projection-and-gap-assessment.md.
**Baseline:** main 0d84ec8531baf604383c5ddc012f40aa84fc4b76.

## Context

The domain distinguishes facility capability from active supply and declares two matching directions. Source identity, unit/time semantics, graph edges and current availability must agree with native Odoo facts. The first direction's label and historical prose are inconsistent. A full supply/demand-gap application has not been proven.

## Decision

1. CEG consumes rebuildable, versioned projections of authoritative source facts. Odoo remains the business record owner. Preserve source refs/UUIDs, tenant/company, revision, evidence class, validity and explicit quantity state.
2. A successful projection materializes both required nodes and edges. Version ordering prevents stale updates or replays from resurrecting withdrawn facts. Typed acknowledgement plus readback proves the intended representation.
3. Supplier-offered material -> eligible buying facilities is the first commercial direction. Confirmed buyer requirement -> current compatible supply is the reverse. Capability alone is not intent, stock or open supply.
4. Every result carries identity, score semantics, gate/evidence meaning and the source/policy revision needed for truthful consumer rendering. Detached schema validity does not prove active handler parity.
5. Gap assessment is scoped to a named dataset/tenant/company, as-of time/window, material compatibility, policy and coverage. It distinguishes confirmed deficit, unmatched current supply, potential inferred fit and information gaps.
6. Quantity coverage cannot count the same lot twice. Unknown/ranged supply propagates uncertainty; incompatible units, stale evidence, pending commitments and recurring throughput cannot masquerade as exact available stock.
7. Proposed `assess-gaps` is a candidate canonical CEG action only. Reuse an admitted equivalent if one exists; otherwise admit handler, payload/result version, spec advertisement, Gate ownership/caller policy and consumer mapping together. No admin escape route or direct peer endpoint.
8. All generic code remains domain-neutral; PlasticOS roles/process rules and units are supplied by domain configuration. No Odoo-specific ID guessing in generic engine logic.
9. PO issuance, commercial Won, inventory procurement, buyer allocation and fulfillment are different facts. CEG cannot derive resale or remaining availability solely from Won. Ambiguous residual material is ineligible until its owner supplies disposition.

## Contract and security impact

Exact identity mapping and live request/result shapes must be accepted before implementation. A consumer must not gain generic graph write power to publish one bounded source family. Hypotheses retain their class and cannot occupy confirmed marketable supply/demand sets.

## Migration and recovery

Retain native source UUID/reference compatibility; reconcile existing nodes and relations under explicit migration identities. Use monotonic revisions and acknowledged tombstones/withdrawals. Pause use on stale authority during disable; no silent local fallback.

## Acceptance

P07/P12-P18/P21/P26/P27/P30-P34. Required witnesses include a nonempty correct match, an incompatible negative, a missing-edge failure, replay/reordering, a failed transport case that is not a shortage, and two demands competing for one lot.

## Related ADR changes

Narrowly amend ADR-104 and ADR-105 as specified in AMENDMENTS.md. Preserve the distinction between active supply and capability; do not globally rename public direction identifiers without a separately versioned compatibility decision.

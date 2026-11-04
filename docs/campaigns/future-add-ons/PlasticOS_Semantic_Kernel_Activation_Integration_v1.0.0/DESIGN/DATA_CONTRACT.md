# Data ownership, evidence, identity and lifecycle contract

This is the proposed domain contract for acceptance, not a claim that its future fields already exist. Reuse existing field definitions at their source owner; any new field named below must be explicitly admitted in the versioned implementation contract before code.

## 1. Three evidence levels

| Level | Meaning | Permitted use | Prohibited promotion |
|---|---|---|---|
| Hypothesis | A source-backed inference about potential inputs, outputs or market fit | Research prioritization, questions to verify, read-only intelligence | Inventory, confirmed buying requirement, tradable listing or financial action |
| Verified fact | A documented/operator-confirmed material stream or capability, with source and validity | Capability profiles and qualification | A current lot or open demand without separate availability/need evidence |
| Current commercial fact | Explicitly confirmed lot/contract availability or buyer need, scoped in time and quantity | Policy-gated matching and confirmed gap coverage | Overcommitting quantity or keeping expired/withdrawn facts active |

These are meanings, not a new duplicate state enum to scatter across models. Existing observation/rule states should express them where sufficient. Preserve original evidence state through projection; do not replace an unknown value with zero, or turn confidence into confirmation.

## 2. Source mapping and hard gates

| Semantic family | Authoritative source | Admission minimum | Refused source |
|---|---|---|---|
| Specification | Reviewed reusable material specification or approved opportunity material snapshot | Canonical polymer/form and scoped spec identity/version | Free-text guess silently normalized as truth |
| Material observation | Evidence/measurement/report/inference with exact source | Feature, value state, unit when numeric, source/time/method/version, conflicts and expiry | Unattributed value or overwritten approved evidence |
| Facility rule | Capability evidence or EIE hypothesis | Facility identity, accept/reject/prefer/require meaning, basis and evidence state | A rule treated as confirmed purchasing demand |
| Capacity observation | Dated facility measurement/report/estimate | Capacity kind, unit and period | Nominal equipment throughput treated as available buying budget or stock |
| Supply | Approved native opportunity and current material snapshot | Profile; source lineage; current marketability; quantity state; pickup geography; validity; operator admission | General profile, previous transaction, old import, inferred scrap or non-HOT form alone |
| Demand | Explicit confirmed buyer requirement or inquiry tied to a native source | Required material, need window, quantity state, scope, buyer/facility identity, evidence | Capable processing line, industry classification or inferred need alone |

A buyer inquiry may remain a CRM lead/requirement until material exists to offer. It is not a second supplier-side opportunity or permission to send offers. Non-HOT Cognito policy remains deferred.

## 3. Identity/cardinality

- Preserve existing semantic `canonical_uuid`, historical external refs and Odoo record IDs. A new native projection must carry a typed native source reference and company/tenant scope; do not manufacture a `res.partner` ID for a prospect.
- Reuse lead-owned facility/material profiles from the CRM bridge (S23/S24). A native `crm.lead` can be a lead or opportunity; a relation label saying lead does not prove only `type=lead` is supported. Verify installed constraints and search domains.
- One material profile may support many commercial opportunities. One independently marketable lot/contract has one commercial opportunity, with multiple per-buyer offers. A source revision changes the representation of that same lot, not its business identity.
- Deduplicate by authoritative source identity and material scope, not company name, shared phone or matching polymer alone.
- Separate business identity from mapping version. A mapping-version upgrade must not create another lot just because the original backfill identity string included that version.
- One current derived supply representation per admitted native source/lot. Preserve past snapshots and operation receipts; do not make multiple independently editable supply rows for the same load.
- Native-source link fields live in the optional integration extension when they would otherwise introduce upper-layer dependencies into passive semantic models. The exact field names and constraints require source-owner admission.

## 4. Snapshot and approval binding

Each approved source snapshot must bind source model/ID/company, immutable material data or digest, source revision, approver, approval time, evidence references and applicable validity. Edits to quantity, material, location, availability, commercial role or relevant evidence invalidate or supersede that approval. Approval is server-derived, not accepted from arbitrary RPC context flags.

Matching reads the approved opportunity-specific snapshot, not the mutable current material-profile fields. Historic offer/email evidence must remain historically accurate if the reusable profile changes. The kernel consumes existing approval owners where adequate; it does not mint a separate Web Lead approval or bypass the commercial campaign's broker gate.

## 5. Units, uncertainty and money

- Normalize unit codes explicitly. Pounds, metric tonnes and US short tons are not interchangeable. The existing CEG property names ending in `tons` are an integration question, not a unit specification.
- Preserve the quantity state (exact/estimated/range/unknown) and bounds. Test Odoo Float defaults: a missing float often reads as zero. Checking `is False` or truthiness is not enough to preserve a genuine zero or absence.
- Confirm supply lower/upper quantity, minimum lot and current remaining quantity separately. An estimated range cannot support a guaranteed numeric shortage claim without propagating the bounds.
- Price requires currency, unit, basis and as-of time. Unknown price must not become a zero/free offer. No FX inference without an explicit approved source.
- Only compare compatible material specs, locations/terms and overlapping time windows. Cadence is not a one-time lot. Do not sum monthly throughput and a one-time inventory balance.
- Confidence is model/rule evidence, not a calibrated probability unless calibration is demonstrated. No arbitrary 0.85 threshold is declared authoritative by this plan.

## 6. State and current listing consequences

| Authoritative event | Commercial owner | Required semantic consequence |
|---|---|---|
| Opportunity draft/unqualified | Native CRM | No marketable supply publication |
| Material-readiness approval | Native CRM approval owner | Eligible for a scoped current projection if all other gates pass |
| Material/quantity/time changes | Native source | New revision; prior result/approval can be stale; old graph eligibility cannot persist silently |
| Explicit withdrawal or expiry | Native source | Invalidate availability and publish bounded withdrawal/tombstone with ordering |
| Lost with reason | Native CRM | Preserve lost history and follow-up lead; close/withdraw this attempt's listing, not the reusable stream |
| Archive without commercial outcome | Native CRM | Not automatically Lost; pause eligibility unless source policy explicitly proves ongoing availability |
| Restore/reopen | Native CRM | Revalidate current evidence; no automatic resurrection of an expired listing |
| Confirmed PO issued | Native Purchase + native opportunity | Record Won only via accepted commercial owner; update procurement/commitment evidence, not an invented resale |
| Post-PO residual material | Explicit commercial/inventory source | No blind rule that Won means sold out or that purchased stock remains available. Require explicit allocation and active commercial owner/successor; otherwise pause listing |
| Supplier identity linked at issuance | Verified partner owner | Reconcile source refs without new business identity or lost provenance |
| Merge/deduplication | Authoritative merge owner | Preserve source mapping and idempotent redirect; block ambiguous merge of different lots |
| Deletion request | Source retention owner | Block destructive loss after evidence/publication or issue explicit audited withdrawal; retain historical provenance |

**Won-at-PO is locked.** The distinction between procurement commitment, buyer allocation and physical availability does not reopen that rule. It prevents a graph error caused by collapsing those different facts.

## 7. Contract migration boundaries

Current peer supply/demand schemas remain distinct (ADR-125). Detached payload examples are not assumed to be accepted by live handlers. Optional supplier refs in a schema do not override required ORM identity guards. Any shape change is a versioned owner-admitted revision with compatibility tests; transport fields stay in TransportPacket, not the domain payload.

## 8. Existing-row policy

Unbound historical semantic supply/demand is retained read-only and nonmarketable until its real source/evidence is reconciled. Do not attach rows to the first matching company, create placeholder profiles, or infer current quantities from archived imports. A rejected/quarantined row remains counted with a reason; it never vanishes from a migration report.

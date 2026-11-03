# Industrial inference and gap intelligence

## 1. What EIE is being developed to infer

Two rule families are required:

1. **Capability/product/process -> potential input need.** Identify material families/forms/spec ranges a facility might consume. The result is potential demand/fit, not a confirmed purchase requirement.
2. **Product/process/material input -> potential generated stream.** Identify plausible scrap or residual-material streams and the evidence needed to qualify them. The result is a supply hypothesis, not a listed lot.

Illustrative testing situations include product manufacturers, processing facilities and recurring material streams. They are synthetic cases until supported by real site/process evidence; the package makes no claim that a specific company produces a specific scrap volume.

## 2. Rule contract

Every admitted rule needs: stable rule ID and version, domain scope, prerequisites, source evidence classes, material/process constraints, contraindications, output evidence state, rationale, confidence method, validity/expiry, missing-field requests and abstention behavior. Rule output must cite its observed inputs and must not cite its own earlier inference as independent corroboration.

Use EIE's existing domain rule loader and inference adapters. First census the actual execution path: rules in `kb/plastics_recycling.yaml` and `domains/plasticos/spec.yaml` are not interchangeable merely because both exist. Establish which registry executes, how strict parsing is enabled, how rejected rules are reported, and how output reaches durable evidence storage. Do not implement inference in Odoo.

### Discriminating examples

| Hypothesis | Required counterexample |
|---|---|
| A manufacturing process may generate reusable offcuts | Internal closed-loop reuse leaves no externally available stream |
| A molding process may generate runners/purges | Tooling/process configuration disproves the assumed scrap type or quantity |
| Extrusion capability suggests polymer input fit | Wrong polymer/form/grade, prohibited contamination or incompatible process |
| Installed capacity suggests possible demand | Captive feedstock or no current buying requirement |
| Material appears on a company website | Evidence is stale, refers to another facility or only a distributor relationship |

The successful result may be **abstention plus a precise question to verify**. That is not an inference failure.

## 3. Verification and admission

Hypotheses remain in evidence/research surfaces. A review can accept that the inference is plausible without confirming inventory. Commercial admission separately verifies existence, material identity, quantity state, timing, availability/need and who may act. The approver must be authorized for that company and current source revision.

A confirmed stream does not automatically create an opportunity. A particular independently marketable load/contract can become a native opportunity under the existing material gate. Buyer inquiries are captured as confirmed requirements without duplicating the supplier-side sales pipeline.

## 4. CEG gap meanings

The system must distinguish at least four result meanings using the smallest suitable existing result representation:

- **Confirmed scoped demand deficit:** documented demand not covered by compatible, current, uncommitted supply in the declared dataset and time window.
- **Confirmed scoped supply without a current match:** valid current supply with no eligible confirmed demand/buyer candidate under declared policies.
- **Potential fit or discovery lead:** inferred compatible inputs/outputs requiring verification.
- **Information/coverage gap:** the system cannot establish coverage because data, required fields, evidence freshness or service availability are insufficient.

A zero-match response is not proof of a global shortage. Every report states dataset/tenant/company scope, source watermark, as-of time, validity, policy version, coverage limits and unavailable dependencies.

## 5. Quantity logic

A numeric deficit is valid only after applying material/time/location/terms compatibility and an allocation that counts each available unit once. Conceptually:

`uncovered confirmed requirement = requirement - compatible allocatable supply`

This is not permission to implement a naive independent sum per buyer. If two buyers each need 40,000 lb and only one uncommitted 40,000 lb lot exists, it cannot satisfy both simultaneously. Show allocation assumptions and unresolved competition. For ranges, propagate bounds; for unknown quantities, return qualitative/unknown coverage rather than a fabricated number. Capacity, forecast yield and expected recurring generation do not enter confirmed current inventory sums.

## 6. Matching direction correction

CEG's first direction label currently conflicts with parts of its ADR/prose. The frozen target meaning is supplier-offered material -> eligible buying facility. The reverse is confirmed buyer requirement -> eligible current supply. Facility capability is supporting evidence for fit; it is not purchasing intent. Add fixtures distinguishing supplier-only, buyer-only, dual-role, unknown-role and excluded facilities.

The exact candidate identity must resolve to a native record or stable external prospect identity under admitted policy. Never use name search to fabricate a partner mapping. Preserve score semantics and scale, policy gates, rejected candidates and evidence. CEG remains the match authority.

## 7. Gap route and generic engine boundary

`assess-gaps` is a **proposed** canonical CEG operation for this plan, not an existing API. U00 must inspect whether an admitted equivalent already exists; reuse it if sufficient. Otherwise its request/result contract, handler registration, capability advertisement, Gate action ownership, caller policy and SDK consumption are admitted together in U01/U06/U07. Do not hide it under an admin escape hatch or add an unregistered HTTP endpoint.

The engine stays domain-neutral. PlasticOS supplies domain entities, rules, units, source roles and policy. No hardcoded Odoo database IDs or plastics taxonomy is added to generic traversal/scoring/routing code.

## 8. Learning and follow-up

Offer responses, opportunity loss reasons, verified PO issuance and physical outcomes may improve subsequent rule evaluation and matching only via their admitted owner/versioned outcome contracts. PO issuance is not delivery or revenue. Do not conflate match rejection with opportunity loss. Historical outcomes used for calibration need source completeness and known timestamps, not merely a status field.

Autonomous sending, negotiation, partner promotion, financial writes and automatic confidence-threshold relaxation are outside this kernel. Future agents use the same native opportunity and human approval gates as people.

## 9. Evaluation before use

Every industrial rule has both a positive witness and a counterexample, plus missing/conflicting/stale-input tests. A domain reviewer labels a held-out real-evidence set and approves inference confidence/abstention policy. The full deterministic suite must have zero false promotions of inferred data to confirmed commercial facts and zero unauthorized writes. That safety bar is distinct from a measured usefulness/precision target, which cannot be invented without the evaluation corpus.

Synthetic passes prove control behavior, not commercial accuracy. Run a bounded authorized shadow pilot, report evidence-backed useful leads and false positives, and stop on unsupported conclusions or unapproved spend. Activation remains a separate decision even after acceptable accuracy.

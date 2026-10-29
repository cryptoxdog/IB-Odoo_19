# Proposed ADR SK-A02: evidence-bound industrial inference

**Status:** Proposed. No rule-set deployment or provider spend authorized.
**Proposed owner/path:** Quantum-L9/Enrichment.Inference.Engine, docs/adr/PROPOSED-industrial-inference-evidence-admission.md.
**Baseline:** main 3f96eda98240789963b0e6534aa2151aed12658e.

## Context

Existing rule infrastructure can derive fields and preserve provenance. The operator requires richer industrial hypotheses: what materials a facility may need given its capabilities, and what material streams it may generate given its products/processes. Existing grading/tier rules and knowledge files are not proof of this application.

## Decision

- Implement domain-specific rules in the approved PlasticOS rule/domain source; keep generic runtime domain-neutral.
- Every rule declares prerequisite evidence, applicability, contraindications, output state, rule/version, rationale, confidence method, source refs, validity and abstention behavior.
- Outputs are attributed hypotheses. They may guide research and review, not directly create available inventory, confirmed demand, partners, POs or offers.
- Verified evidence remains distinguishable from inferred evidence. Missing/conflicting/stale inputs cause an explicit unknown, conflict or request for further evidence, not fabricated fact completion.
- Preserve durable-before-completed behavior and existing tenant-bound Gate result/sync acknowledgements. Native Odoo source facts are not routed through inference to bypass projection permissions.
- Rule registration and invocation must be traced to actual runtime consumers. Unused knowledge files or synthetic fixtures do not establish feature availability.
- Domain-reviewed held-out examples and negative counterexamples precede any business use. Calibrated thresholds are approved from evidence; no universal confidence cutoff is invented here.

## Security and cost

Only authorized sources/tenants are used. Provider calls have explicit budget and operation scope. No prompt/source content may alter activation permissions, ownership or approval. Results retain evidence access restrictions and do not leak private source data into broader graph/CRM views.

## Wiring

Align domain spec -> actual rule loader/adapters -> invocation -> durable result -> side-effect coordinator/packet router -> Gate -> approved consumer. Add no Odoo inference implementation. Reuse current evidence stores and result schemas where sufficient; version any necessary contract additions before dispatch.

## Acceptance

P06/P12/P13/P32/P33/P34. For each rule, require a valid positive case, a genuine defeating case and missing/conflicting/stale input cases. End-to-end use must preserve the inferred evidence class and must not create a confirmed supply/demand record without separate admission.

## Rollout

Offline/isolated evaluation first, then source-authorized shadow review, then separately approved use. Production remains disabled until operator activation even if evaluation passes. No automated approval-threshold relaxation.

# Evaluation and measurable commercial value plan

The 18 proposed acceptance cases in `evaluation/adversarial_acceptance_cases.jsonl` are **specifications only**, not tests that have been run against Odoo, a live model, or the new addon. Source examples are synthetic, so no claimed baseline or percentage gain is established here.

## Ranked, lowest-change value experiments

| Priority | Consumer | Specific hypothesis | Baseline/evidence required | Measured outcome | Required negative controls |
| --- | --- | --- | --- | --- | --- |
| 1 | `plasticos_web_leads` shadow | Approved knowledge-backed questions improve broker clarity without overrejecting valuable leads | Current broker-labelled HOT/REVIEW/COLD corpus and existing economic assessment results | False-COLD rate, appropriate REVIEW rate, evidence-citation validity, missing-info recall | No fabricated weight or polymer, no false negative from unknown |
| 2 | Mack read-only advisor | Cited technical playbooks reduce broker time to a qualified next step | Timed review of real, anonymized inquiries; previous manual workflow | Time to evidence-complete review, human acceptance of next action, rework count | Unknown price -> abstain; no unauthorized action or cross-company disclosure |
| 3 | Offer/match rejection explanation | A normalized, reviewed reason with recovery suggestion reduces lost context | Real rejection narrative + evidence + actual later outcome | Meaningful reason coverage, inter-reviewer agreement, recovery review-to-requote rate | No permanent exclusion from one refusal; no auto-resend |
| 4 | Material inspection | Context-specific questions reduce polymer/contamination ambiguity | Real sample reports and broker correction traces | Inspection-question utility, attribution completeness, fewer conflicting facts | Photo is not lab test; missing facts stay missing |
| 5 | Coach/evaluation library | 20 distinct cases provide useful coverage beyond repeated Q/A pairs | SME-labeled source tests; genuine SOP references | Distinct decision-boundary coverage; mistake prevention and review consistency | SOP missing -> don't treat as policy; no invented finance/price rules |

## Required release evidence

- A frozen, source-verified evaluation corpus with broker-labeled outcomes and splits by supplier/lot/time to avoid near-duplicate leakage.
- Separate measurement for factual errors, decision routing errors, hallucinated commercial numbers, authority violations, unsupported SOP claims, and permission leaks.
- An independent baseline and candidate comparison, not the old generator's self-reported count.
- Real Odoo 19 installation/upgrade and selected user tests for any new addon. Lint/JSON checks do not prove ORM ACLs, views or live behavior.
- Explicit approval for any change to live lead-routing defaults or outbound correspondence. No private mail, PO/SO, offers or payments from this pack.

## Why not fine-tune yet?

The corpus has 699 CSV prompt/response rows but substantial templating and unsupported commercial claims; the 56 coaching rows contain only 20 distinct patterns. Use it first to find questions and negative cases. Model weights can be reconsidered only after reviewed labels prove an improvement over the existing provider/knowledge workflow.

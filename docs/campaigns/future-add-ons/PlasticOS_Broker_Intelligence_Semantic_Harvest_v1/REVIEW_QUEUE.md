# Review queue: explicit dispositions before promotion

This is a **curation queue**, not a release checklist, or an approval authorization. Each candidate remains non-operational until independently adjudicated against current source owners.

| Order | Decision to make | Evidence available | Acceptance evidence | If unresolved |
| --- | --- | --- | --- | --- |
| 1 | Choose which of 12 rejection meanings genuinely belong in a reusable vocabulary and which are buyer/time-specific | `candidates/12_rejection_meanings.jsonl` and 59 extension examples | Broker-reviewed meaning, scope, examples and no duplicate with native exclusion reason | Keep candidate, no automatic code mapping |
| 2 | Reconcile 28 observed `R-*` aliases, including numeric `R-01...R-09` | `comparisons/rejection_namespace_conflicts.jsonl` | Exact approved alias table with negative collision cases | Alias unresolved, never auto-map |
| 3 | Verify 20 claimed `SP-/QA-/SAL-/LOG-/OPS-/FIN-` SOP identities | `candidates/20_unique_coaching_patterns.jsonl` plus all 56 original prompts | Current approved SOP owner/revision and safe scope or explicit rejection | Keep scenario as synthetic evaluation only |
| 4 | Select core inspection questions by material, process and evidence status | `candidates/material_inspection_requirements.jsonl`, 32 concerns | Tested Odoo field mappings; unknown/null/unit behavior | Only show generic question, no test/threshold claim |
| 5 | Review all stale prices, live buyers and regulatory assertions | 867 source scenario index and PP KB crosswalk | Dated external evidence and qualified legal/business review | Quarantine as untrusted historical text |
| 6 | Validate additive value to web-lead triage | `evaluation/adversarial_acceptance_cases.jsonl` + current `qualification_mode=shadow` | Broker-labelled holdout with better metrics and zero critical violations | No change to live routing |
| 7 | Validate Mack's use of approved knowledge | Standalone addon source and native consultation receipt design | Real Odoo DB installation, permissions and source-message receipts | No production Mack activation |
| 8 | Determine whether real rejection outcomes justify a structured native reason selector | Existing `offer.rejection_reason`, `match_result.rejection_reason`, `match.exclusion.reason` | Independent approved requirement and backward compatible owner proposal | Retain text and advisory suggestion, no new field |
| 9 | Verify rights and confidentiality of 116 media files | SHA/path-only inventory | Rights and labeling, EXIF removal and per-image joins | Do not ship image bytes or use for tuning |

## Confidence rules

- Original donor data + byte/hash: **confirmed source presence and text**, not correctness.
- Current repository model/ADR source at a pinned commit: **confirmed source interface**, not current installed runtime.
- Proposed semantic contract/gap: **inference/recommendation**, pending owner adjudication.
- Vendor prices, real processor distance, market rate, outdated customs rules and unsupported compliance: **not verified**.
- Native L9 global admission: **not attempted**; this is a PlasticOS-local candidate.

## Out-of-scope changes deliberately deferred

A new matching service; a new economic recommender; a new database schema for every candidate; automatic quality-based exclusion; a new pricing engine; direct EIE/CEG SDK clients; activation of the dormant semantic kernel; migration of the old Mack WIP; direct email/PO/offer work; and fine-tuning on synthetic training answers.

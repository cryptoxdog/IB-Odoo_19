> **v2.7.4 entrypoint:** `INTEROP/SOURCE_BOUND_CHANGE_PLAN_v2.7.4.md`, machine ledger and technical module-owner boundary matrix. Source target pinned at 78476ddb74861d900992f7f5ec3ec2cc2a63e8bf. No fabricated human signoffs are required; material source and Enterprise/data proofs remain open and no code is authorized. POS-INV-26 draft remains unchanged.

> **v2.7.2 current pre-code gate:** `INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md` + `INTEROP/UPSTREAM_FILE_CHANGE_MAP_v2.7.md`. POS-INV-26 in `../GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md` now requires the **complete documented blast radius and full change plan** before project code is written. Status OPEN/BLOCKED; v2.7.1 references below are historical. No constitutional admission is asserted.

> **Mandatory v2.7.1 pre-code gate:** `INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md` + `INTEROP/UPSTREAM_FILE_CHANGE_MAP_v2.7.md`, under the operator rule **No code gets written until every ripple effect is accounted for**. The latest *draft* invariant is `../GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r1.md` POS-INV-26. These are mandatory working-pack reading/closure constraints, not admitted repository constitutional law or code permission. Existing v2.7 and v3.3 references below are historical.

# PlasticOS Export BRS v2.0.0

## Where to begin

**Current handoff v2.7:** Read `MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md` first for selected working-pack technical identity, field/command contracts, owner-adoption gates, migrations and Enterprise proof, then `MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json` for a derived machine-readable index. The v2.5 `IMPLEMENTATION_READINESS_CONTRACT.md` and v2.6 `INTEROP/CROSS_MODULE_INTEGRATION_CONTRACTS.md` remain historical candidate evidence; their tentative technical alternatives do not overrule v2.7. `RULE_REALIZATION_MATRIX.csv` preserves each stable BRS/AC mapping. **Owner adoption, code and runtime proof remain pending.** Use `../GOVERNANCE/ODOO_INVARIANTS_v3.3.0_DRAFT_r1.md` as the latest *draft* work constraint; repository v2.2.0 remains constitutional. Earlier v3.2 references below are historical.

This is the **frozen Phase 1 product-design specification**, now with a proposed minimal module file tree, a **hand-authored module README**, and a seven-part refined reading set. The actual `plasticos_export` addon is not installed or implemented on the inspected Odoo Staging revision.

Start with `MODULE_DESIGN/plasticos_export/README.md` (the intended README for the future addon), then `MODULE_DESIGN/PROPOSED_FILETREE.md` (proposed placement, not generated implementation). Read `REFINED_BRS/README.md` for the concise seven-concern workflow and `REFINED_BRS/EXACT_RULE_CROSSWALK.csv` for the unambiguous mapping of **all 120 existing stable rule IDs**.

**Normative identity remains unchanged:** 120 canonical requirements in `RULES/BRS-EXP-01.md` through `BRS-EXP-14.md`, mirrored in `REGISTRY/rules.json`, with 120 `ACCEPTANCE` cases. None of their rule statements or original acceptance criteria has been silently rewritten in this release. The refined set is a curated, non-normative reading projection, not a duplicate BRS authority. All tests are still NOT_RUN.

## Frozen business choices

- One booking can cover multiple physical containers and multiple supplier POs; a real SO or PO may produce multiple independent partial shipments.
- The physical delivery site may be a port/rail ramp, not the commercial buyer. Buyer-optional purchase/custody is legitimate with valid source authority.
- Export owns booking identity, current sourced terms, allocation context, export views and report layouts. It does not own freight execution, legal document verification, inventory or accounting.
- Original messages/PDFs stay in native Documents. Native AI may extract proposals; only exact owner-controlled actions accept facts and change states. Linda remains the external sender.
- Phase 1 needs a dashboard that summarizes and drills into all six native reports. Phase 2 adds international selling plus optional FindTEU and ACE AESDirect assistance.

## Why this is a refinement, not another feature release

Exploration created 14 coherent chapters with overlapping descriptive language. The seven reading briefs separate **fact owners**, **their export-specific consumer**, and **acceptance demonstrations** without deleting historical protections or inventing new source-of-truth rules. The file tree is a minimal **design hypothesis**; the installed Enterprise module graph, current field owners and data migration shape must still be verified by the implementation owner before creating code.

**Authority:** repository `INVARIANTS.md` v2.2.0 remains constitutional at the inspected source. Candidate POS-INV-21..24 are not admitted. `CONVERGENCE/OPERATOR_DESIGN_FREEZE.md` preserves the operator's design lock, but does not grant code change, PR publication or deployment authority. The existing Logistics and Documents BRSs retain their own owners. 

## Privacy and verification

`SOURCES/` includes private supplier correspondence, booking revisions and historical reports for internal design evidence. **Do not commit the full ZIP or source fixtures to a public repository.** The package's structural verification checks are not Odoo 19 Enterprise installation proof, live email proof or independent architecture admission.

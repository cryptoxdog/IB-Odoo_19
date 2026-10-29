# Refined Export BRS: implementation reading set

**Status:** Non-normative, lossless reading projection of the **120 existing stable `BRS-EXP-*` rules** in `RULES/` and `REGISTRY/rules.json`; it is NOT a second requirements authority. Every rule ID maps to exactly one primary concern in `EXACT_RULE_CROSSWALK.csv`. The source chapter remains the governing rule, the corresponding `ACCEPTANCE` case remains its test, and the operator-frozen architecture remains protected. There are **no new rule IDs or new business capabilities** in this release.

This refinement solves the organization problem created by incremental exploration. Some existing chapters repeat words about Documents, booking dates, AI matching and reporting because they are different surfaces of the same business operation. The seven reading briefs below distinguish **the fact owner**, **the consuming interface**, and **the conformance demonstration**, avoiding competing decisions while retaining all original controls. They are safe to read in order and unsafe to commit as replacement BRS authority without an explicit supersession.

## Seven briefs

| Read | Concern | Primary named owner |
| --- | --- | --- |
| `RB-01_COMMERCIAL_AND_AUTHORITY.md` | Native-first orders, real movements, commercial permissions and buyer optionality | Purchase / Sales / Stock / Accounting, Transaction |
| `RB-02_BOOKING_IDENTITY_AND_REVISIONS.md` | Ocean reservations, sources, changed cutoffs and carrier terms | Export |
| `RB-03_EQUIPMENT_AND_ALLOCATION.md` | Equipment vocabulary, confirmed capacity and booked slots | Export requirement + Logistics actual equipment |
| `RB-04_DOCUMENTS_AND_AI.md` | Original correspondence, extraction, exact matching and evidence verdict | Native Documents / PlasticOS Documents |
| `RB-05_LOGISTICS_AND_HANDOFF.md` | FAS/FOB, truck assignment, supplier/carrier packets, terminal milestones | Logistics / Linda |
| `RB-06_DASHBOARD_AND_REPORTS.md` | Six native reports, at-a-glance projections and exact drilldown | Export presentation over source owners |
| `RB-07_PHASE2_EXTENSION.md` | International selling, ocean tracking and export filing support | Export, accepted external providers, official filer |

The groupings are **editorial**, not new model classes, files, scheduling workers, or authorization boundaries. Consult `MODULE_DESIGN/plasticos_export/README.md` for the hand-authored product description and `MODULE_DESIGN/PROPOSED_FILETREE.md` for the proposed Odoo placement.

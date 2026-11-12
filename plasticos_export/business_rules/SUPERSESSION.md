# Export BRS | supersession register

The 14 chapters and `rules.json` in this folder are copies of Export BRS v2.0.0 (identical except for one terminal newline, see `REGISTRY.json`). That pack already carries every supersession below **in place**: the rule keeps its stable ID and its current text is the effective one. This file records which IDs changed, when, and where the dated note lives, so no one reads an older wording as current.

Business policy changes from now on are made **only** by adding a dated section here. Never edit a `BRS-EXP-NN.md`, `rules.json` or `ACCEPTANCE.json` copy; `tests/contracts/test_export_brs_registry.py` fails if any of them changes.

The dated source notes are kept as provenance in the campaign pack: `docs/campaigns/future-add-ons/PlasticOS_Export/EXPORT_BRS/SUPERSESSION_v1_2.md` through `SUPERSESSION_v1_9.md`.

## Rule-level supersessions

| Rule | Version | Change | Source note |
| --- | --- | --- | --- |
| `BRS-EXP-01-R003` | v1.2.0 | Exact, non-fictitious links became exact associations without a mandatory early buyer. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-01-R004` | v1.2.0 | No cross-owner consequential transitions became: evidence proposals are not unauthorized business transitions. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-02-R001` | v1.2.0 | One contextual booking became booking-to-order and shipment cardinality independent. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-03-R001` | v1.2.0 | One intake/original became native intake, AI-proposed extraction and exact document attribution. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-04-R003` | v1.2.0 | Factual handoff became: physical handoff and commercial allocation are independent. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-05-R001` | v1.2.0 | Extending Phase 1 identities became: an in-transit sale reuses the original shipment and evidence. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-06-R003` | v1.2.0 | Independent operational and financial states became order, shipment, evidence and transaction states remain scoped. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-07-R004` | v1.2.0 | Equipment request, count and actual units became booking equipment count and per-week physical units. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-09-R002` | v1.3.0 | Multi-input extraction with field-level unknowns. | `SUPERSESSION_v1_3.md` |
| `BRS-EXP-09-R003` | v1.3.0 | Exact booking / PO / shipment / ticket matching. | `SUPERSESSION_v1_3.md` |
| `BRS-EXP-09-R005` | v1.3.0 | Same versus replacement booking, rolls, same-name changed files. | `SUPERSESSION_v1_3.md` |
| `BRS-EXP-09-R007` | v1.3.0 | Evidence-to-business-event transitions and incomplete milestones. | `SUPERSESSION_v1_3.md` |
| `BRS-EXP-10-R002` | v1.6.0 | An approved supplier PO is issuable independently; each later booking notice is its own source-revision obligation. Supersedes mandatory PO + booking issuance at first release. | `SUPERSESSION_v1_6.md` |
| `BRS-EXP-11-R005` | v1.6.0 | Same-number booking revisions handled with the observed 3/4/5 x 40HC variants, cutoffs and terminal ERDs; file order is not proof of precedence. | `SUPERSESSION_v1_6.md` |
| `BRS-EXP-14-R017` | v1.9.0 | Dashboard carries on-screen vital summaries and one-click links to all six core reports. | `SUPERSESSION_v1_9.md` |
| `BRS-EXP-14-R021` | v1.9.0 | The six operational reports are named consistently; Missing Export Documents replaces the optional Export Economics. | `SUPERSESSION_v1_9.md` |

## Chapter additions (no prior rule removed)

| Rule | Version | Addition | Source note |
| --- | --- | --- | --- |
| `BRS-EXP-08-R001` | v1.2.0 | Chapter BRS-EXP-08: commercial orders, buyer-optional cargo, many loads per order. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-09-R001` | v1.2.0 | Chapter BRS-EXP-09: native AI booking extraction, exact linking, guarded state actions. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-10-R001` | v1.2.0 | Chapter BRS-EXP-10: Logistics/Linda work orders, supplier/carrier packets, movement eligibility. | `SUPERSESSION_v1_2.md` |
| `BRS-EXP-11-R001` | v1.3.0 | Chapter BRS-EXP-11 (R001..R012): scenario-level AI interpretation. | `SUPERSESSION_v1_3.md` |
| `BRS-EXP-12-R001` | v1.4.0 | Chapter BRS-EXP-12: FindTEU (R001..R005) and ACE AESDirect (R006..R010), Phase 2 only. | `SUPERSESSION_v1_4.md` |
| `BRS-EXP-13-R001` | v1.5.0 | Chapter BRS-EXP-13 (R001..R010): booking form fields. | `SUPERSESSION_v1_5.md` |
| `BRS-EXP-14-R001` | v1.5.0 | Chapter BRS-EXP-14 (R001..R013): one-container-per-row report, pivots, exports. | `SUPERSESSION_v1_5.md` |
| `BRS-EXP-14-R022` | v1.9.0 | Six-report coverage and filter-preserving dashboard, report and record navigation. | `SUPERSESSION_v1_9.md` |

## Withdrawn global predicates (v1.2.0)

Kept as rulings, not rules: buyer-always-required and buyer-never-required are withdrawn as global predicates; eligibility depends on movement purpose and actual sale state. One SO = one load, one PO = one load, one booking = one PO, and a mandatory PO reissue on every weekly booking are rejected.

## Cross-owner limit

This register cannot supersede Logistics, Documents, native Purchase/Sales/Stock or the Native-First `BRS-POS-*` rules. A change those owners must make is proposed to them (`EXPORT_BRS/INTEROP/TARGET_OWNER_BRS_AMENDMENTS.md`) and lands in their own `business_rules/` folder.

## Reading projection

`EXPORT_BRS/REFINED_BRS/` regroups the same 120 IDs into seven briefs (RB-01 to RB-07). It is non-normative; `BUSINESS_RULE_TRACEABILITY.csv` column `refined_brief` gives each rule's brief from `EXACT_RULE_CROSSWALK.csv`.

## Operator decision 2026-11-12: Sales Rep allocation visibility

Recorded from the operator chat instruction of 2026-11-12: "sales reps must see all loads allocated to all bookings so they can plan accordingly if they see only their loads they may overbook a booking - sales just can't open or modify other loads but they can see them". It clarifies the audience of the rules below and replaces no rule text.

| Rule | Version | Clarification | Source note |
| --- | --- | --- | --- |
| `BRS-EXP-14-R012` | 2026-11-12 | Same-company Sales Reps are an allowed audience for cargo allocation rows: every link of every booking in their companies, read only. A row shows the booking, slot, container, supplier, source names, physical source kind and planned quantity; it carries no economics (`BRS-EXP-06-R001` stays locked). The loads, sale orders and purchase orders behind another rep's row stay owner-scoped: their records cannot be opened, read or modified from Export. Company isolation is unchanged. | operator chat 2026-11-12 |
| `BRS-EXP-14-R017` | 2026-11-12 | The Bookings control center drilldowns open the underlying load, sale order or purchase order only for a reader entitled to that record; for any other reader the reference is shown as text or a non-opening reference. | operator chat 2026-11-12 |
| `BRS-EXP-14-R022` | 2026-11-12 | Report and record navigation, the container manifest and exports render allocation rows for a same-company Sales Rep from the link's own name fields, never by reading the source records in that reader's access. | operator chat 2026-11-12 |

This supersedes the PR #479 review scoping that limited a Sales Rep to links on sale orders they own. Slots, bookings and links still change only through the Logistics-owned Export commands.

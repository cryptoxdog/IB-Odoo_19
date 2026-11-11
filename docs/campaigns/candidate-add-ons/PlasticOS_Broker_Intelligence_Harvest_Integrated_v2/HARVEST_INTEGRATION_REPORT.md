# Semantic Harvest Integration and Dispositions

**Exact inputs:** only the supplied semantic harvest ZIP and `cryptoxdog/IB-Odoo_19@Staging`, SHA `c2c72bc36d6201d4114531a8f666c411db612f64`. GitHub returned **zero open PRs** during this inspection; no separate v1 implementation ZIP was used or presumed.

## Source coverage

| Harvest asset | Source inventory | Implementation/disposition | Approved |
|---|---:|---|---:|
| Broker capabilities | 18 | 18 source-bound `BI-CAP-*` draft knowledge records and owner mappings | 0 |
| Rejection-code meanings | 12 | 12 `BI-REJ-*` draft meanings; exact-code proposal service for Offer/Match | 0 |
| Coaching scenarios | 56 | All 56 original records retained in `source_catalog`; pattern lineage retained | 0 |
| Distinct coaching patterns | 20 | 20 `BI-COACH-*` draft knowledge records | 0 |
| Material inspection concerns | 32 | 32 `BI-INSPECT-*` draft knowledge records, conditional clarification only | 0 |
| Proposed decision sequences | 12 | 12 `BI-SEQ-*` draft records; no automated procedure execution | 0 |
| Source text scenarios | 867 | All 867 in source-scenario evidence index; **not** turned into authoritative facts | 0 |
| Rejection aliases with namespace conflicts | 28 | All 28 retained as **unresolved**, no guessed crosswalk or approved mapping | 0 |
| PP v8 technical crosswalk | 12 sections | 12 `BI-PPKB-*` candidate draft records; technical/numeric support required | 0 |
| Adversarial evaluation cases | 18 | Retained in original evaluation file; relevant failure modes used for offline regression tests | 0 |
| Original standalone seed knowledge | 38 claimed in request | **Unavailable** because there is no second ZIP and no broker addon on `Staging`; not represented as present | Unknown |

**Loaded candidate draft total: 106 = 18 + 12 + 20 + 32 + 12 + 12.** All 106 are initial state `draft`. No automatic import approval, new buyer classification, commercial terms, financial posting, or material property measurement.

## Provenance and identity

`source_catalog/candidate_admission_register.json` enumerates each stable key, candidate disposition, stated source reference, original source SHA-256 and selector, and current proposed owner. `plasticos_broker_intelligence/data/knowledge_drafts.xml` provides stable external IDs under `noupdate="1"`; the model enforces a `(stable_key, version, company-scope)` unique index and one approved revision per `(stable_key, company-scope)`. A new revision preserves its source identity, increments version, clears approval evidence, and starts in draft. XML load/upgrade survival remains an Odoo runtime gate.

The original ZIP's `FILE_MANIFEST.sha256` is retained unchanged. All listed source-catalog file hashes were checked after extraction. Source-file references to original raw training files are **source assertions present in the harvest**, not proof that those raw donor files were separately retrieved or verified here. The complete input-harvest ZIP digest is recorded in `BUILD_RECEIPT.md`.

## Owner placement and non-duplication

- `plasticos.intake`: factual material snapshot; quantity is an unverified Odoo default until independently confirmed. Advice is a read-only interpretation and escalation.
- `plasticos.web.lead`: qualification and routing retained by current `plasticos_web_leads`; the optional bridge uses `_qualification_signals` as an advisory context seam only when native mode is `shadow`.
- `plasticos.offer` and `plasticos.match.result`: original rejection statements and commercial states remain owner records. The rejection wizard does not write them or create permanent exclusions.
- Odoo Mail, matching and external scoring, Accounts, Logistics, Documents: unchanged. Advisory snapshots and candidate feedback are not substitutes for these owners.
- Core knowledge versions/review events are **local advisory metadata**, not master buyer/material specification writes.

## The two unproven historical obligations

1. **The unavailable standalone v1:** preserve/reconcile the original 38 drafts and verify exact v1 callable compatibility against real original code after it becomes a separately authorized input. Neither restoration nor API equivalence is asserted.
2. **Enterprise registry:** install/upgrade, actual SQL index behavior, attachments, view inheritance, source permissions, workflow shadow equivalence and multi-company data isolation must be observed on Odoo 19 before a release or Production recommendation.

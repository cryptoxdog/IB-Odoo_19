# v1.2.0 additive scope lock: PlasticOS Export

**Operator lock:** `plasticos_export` is one **small, two-phase** Odoo-native extension. Its principal value is **incoming and outgoing documents, report templates, and useful views**, with only the export-specific data fields and orchestration Odoo genuinely lacks. **Do not overengineer it.**

**Version relationship:** additive refinement of RecycleOS operational idea expansion v1.1.0. All twelve non-manifest v1.1.0 members are retained **byte for byte**. Nothing in this addendum replaces or reinterprets the earlier QR, mobile, scale, manufacturing, container, or booking requirements; it simply scopes the exporter implementation path and defines the operator's industry vocabulary. The attached `PlasticOS_Native_First_BRS_v1.0.0_2026-10-25` is a **separately frozen working BRS**: this pack references it by exact archive hash and rule IDs; it does not absorb, rename, supersede, mutate, or claim to admit it.

## Decisions now locked at product-intent level

1. **One module, two phases.** Phase 1 serves the operator's existing **FAS delivered-to-port/rail** business, and also understands the operator's **FOB pickup** workflow. Phase 2 extends the same foundation to sellers arranging ocean carriage and other international obligations, including CNF/CFR and potentially CIF. No rewrite or parallel export stack between phases.
2. **Industry usage is preserved.** In this recycling operation, `FOB` means **buyer pickup** and `FAS` means **seller's delivered/inland-freight-included price to the agreed port or rail point**. This is a **commercial operational vocabulary**, not an assertion that the official Incoterms 2020 rules mean the same. Keep a distinct explicit formal Incoterm/named place when contractually agreed; never auto-map or rewrite either; do not infer legal risk/title/filing responsibility from an industry shorthand.
3. **Native-first minimal addition.** Odoo owns original source documents (where appropriate native Documents is installed), attachments, mail, Sales/Purchase/Accounting, stock and packages, reports and UI substrate. Existing `plasticos_documents`, Linda/logistics and transaction modules retain their proven business ownership. `plasticos_export` is a thin **projection/coordinator** for export-specific booking, document applicability, timeline, reporting and views; no duplicate engines or ledgers.
4. **Documents are the main workflow.** File comes in through authorized native channels -> exact party/order/booking/load/container association -> existing business evidence verification -> appropriate recipient-safe outward document/report using the existing mail authority. Unknown, missing, contradictory or superseded evidence stays visible and unresolved, not silently approved.
5. **Six export-critical fields remain first-class**: **Booking No.**, **Steamship Line**, **Port of Loading**, **Port of Discharge**, **Cut Off**, **Earliest Return Date**. Keep booking revisions/time-zone precision and source attribution; no duplicate field if an equivalent authoritative one already exists.
6. **No premature ocean complexity in Phase 1.** Do not require ocean booking purchase, destination import customs workflows, vessel tracking, letters of credit, or carrier integrations to ship FAS origin-side use cases. Regulatory duties actually attributable to the party still apply; avoid treating FAS as an exemption.
7. **No changes authorized.** Idea/spec scope lock only. Neither this archive nor attached BRS authorizes Odoo code, repository PR, test, external mail, live booking, regulatory filing, or financial posting. Any implementation requires separate repository-revision and BRS admission/conflict review.

## Semantic placement

Candidate addition under the **existing** RecycleOS operational/export capability branch and Odoo addon `plasticos_export`, dependent on actual Odoo/PlasticOS interfaces. Do not create a new company-level strategy branch, rebrand technical `plasticos.*`, add a new Documents platform, or let this product expansion supersede the Frozen Native-First BRS.

## New v1.2.0 members

- `11_PLASTICOS_EXPORT_NATIVE_FIRST_TWO_PHASE_SPEC.md`: bounded phase scope, native ownership and practical records/documents/views.
- `12_PLASTICOS_EXPORT_ACCEPTANCE_AND_GAPS.md`: positive/negative scenario checks, dependencies, proof gaps and anti-overbuilding controls.
- `13_PLASTICOS_EXPORT_ADDITIVE_SCOPE.json`: machine-readable candidate; no imposed host graph schema.
- `MANIFEST.json`: regenerated complete checksum ledger with predecessor checks.

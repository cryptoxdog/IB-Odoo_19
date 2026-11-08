# Operator-frozen Export architecture baseline (2026-10-28)

**Status:** OPERATOR DESIGN BASELINE FROZEN, NOT repository/constitutional admission or Enterprise runtime proof. **Predecessor:** RecycleOS v2.1.0 / Export BRS companion v1.7.0. The user explicitly instructed: "Freeze that." No Git repository mutation is authorized by this frozen working-pack status.

## Frozen decisions

1. `plasticos_export` is thin: owns ocean booking identity, revisions, current carrier-sourced terms and constraints, booking-space assignment, export requirement applicability, screens and report templates. It MUST NOT own inventory ledger, logistics state machine, document originals/verification, outbound mail, commercial approval or accounting.
2. Exact physical execution continues to use existing `plasticos.transaction` and `plasticos.load` semantics, with one transaction/load per physical shipment when that representation is valid. Multiple shipment transactions may share a single real SO or PO; one real ocean booking may cover multiple loads and suppliers. Do not use arbitrary first transaction for an SO.
3. Company identity and movement eligibility are independent from the presence of buyer/SO. Legitimate buyer-unassigned and on-water sale operations are supported without fictional counterparties, movement or stock. The actual Logistics owner must resolve current sale-derived company limitation.
4. Native Documents stores original bytes; PlasticOS Documents owns exact association/business verification; only the authorized Odoo domain action accepts AI-extracted facts and state changes. Linda in Logistics is the only external commercial/operational sender.
5. FAS supplier-delivered shipments do not require a fictitious Linda trucking booking; Logistics owns actual carrier dispatch only where its operator is responsible. Physical destination (port/rail terminal) is distinct from buyer and commercial terms.
6. Native Odoo list/search/pivot/dashboard/spreadsheet and QWeb are the reporting framework. No alternative engine, second allocation-to-fulfillment ledger, or general custom logistics app is authorized.
7. Phase 2 preserves FindTEU and AESDirect assistance as optional interfaces, not Phase 1 core dependencies.

## What this freeze does and does not mean

The operator-approved design is now protected against silent functional or semantic drift. Proposed UX/report refinements in BRS-EXP-14-R014..R021 fit within the frozen owner boundaries and are **DESIGN candidates**, not a new authority or permission to change an owner contract. Exact implementation placement, verified source-owner adoption, Odoo Enterprise validation and constitutional admission are separate pending gates; use `GOVERNANCE/EXPORT_ARCHITECTURE_CONVERGENCE_CANDIDATE.md` for the predecessor evidence.

Current repository `INVARIANTS.md` v2.2.0 remains authoritative. v3.1.0 remains a draft; BAN001 remains binding without waiver. All new acceptance cases are NOT_RUN.

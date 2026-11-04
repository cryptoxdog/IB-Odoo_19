# BRS-EXP-05: Phase 2: international sale and ocean obligations

**Class:** additive design rules; distinct from existing `BRS-POS-*` chapters.
**Primary semantic owner:** plasticos_export contextual extension, no shadow subsystems
**Authority:** previously operator-locked scope is LOCKED; unapproved technical recommendations are DESIGN. This is an unadmitted planning artifact.
**Phases:** P1 = recycler FOB/FAS; P2 = actual international seller; BOTH = shared.
**Runtime and independent acceptance:** NOT_RUN.

## Rules

### BRS-EXP-05-R001: In-transit sale reuses original shipment and evidence

**LOCKED · P2 · owner: `native commercial sale and inventory owner; Export link/projection`.** Phase 2 SHALL support a genuine buyer purchasing material already on the water, including later sale-order allocation to existing identified cargo while preserving original purchase, container, booking, stock custody, delivery, and documents. The seller/buyer, title terms, Incoterm, approval and pricing SHALL be governed by the real native commercial owner and contract. No new parallel shipment/stock ledger or retroactive falsification of historic transport facts is permitted.

- **Positive:** A container already sailed without a buyer is later allocated to an approved international SO with a traceable effective date and unchanged carrier documents.
- **Negative:** A late sale rewrites the original booking party or shipping date, automatically assumes customs clearance, or creates a second stock quant.
- **Related existing BRS:** BRS-EXP-08-R007,R008; BRS-POS-05,R006.
- **Acceptance:** `AC-EXP-05-001` / NOT_RUN.

### BRS-EXP-05-R002: Freight-inclusive price/role semantics

**LOCKED · P2 · owner: `native commercial order + `plasticos_logistics``.** Phase 2 SHALL support recycler `CNF/C&F` trade shorthand, and explicit contractual CFR/CIF terms where agreed, while preserving booking arranger, freight payer, ocean carrier/forwarder, insurer when applicable, seller obligations and agreed destination separately. Freight quotes/actuals remain with existing logistics/accounting owners; terms SHALL NOT alone infer title transfer or risk at destination.

- **Positive:** A CFR shipment shows seller ocean freight responsibility and risk recorded separately from arrival.
- **Negative:** CNF label automatically posts freight bill or treats arrival at POD as first transfer of risk.
- **Related existing BRS:** Operator quoted CNF; BRS-POS-06-R001; BRS-POS-10-R008.
- **Acceptance:** `AC-EXP-05-002` / NOT_RUN.

### BRS-EXP-05-R003: Ocean milestones are sourced facts

**DESIGN · P2 · owner: ``plasticos_export` contextual projection / third-party evidence`.** Phase 2 MAY expose verified vessel/voyage, container loading, port departure, discharge, delivery and exception information where carrier/forwarder data is actually supplied; each observation SHALL retain source and revision, and SHALL NOT overwrite native stock, freight or customer delivery authority.

- **Positive:** Ocean B/L and carrier departure notice can be correlated to a booking/container and displayed as source-backed milestones.
- **Negative:** An ETD estimate automatically marks vessel sailed, invoice paid or cargo received.
- **Related existing BRS:** BRS-POS-01-R011; BRS-POS-10-R013.
- **Acceptance:** `AC-EXP-05-003` / NOT_RUN.

### BRS-EXP-05-R004: Ocean B/L, shipping instructions and VGM

**DESIGN · P2 · owner: `native Documents + document compliance + export applicability`.** Phase 2 SHALL coordinate applicable shipping instructions, issued ocean B/L (carrier/forwarder original), required VGM evidence and export packet documents using native original custody and shared verification. Export SHALL NOT forge or issue a carrier B/L, assert VGM compliance from package-net sum alone, or add a separate document verifier.

- **Positive:** A third-party-issued B/L is linked and verified for the exact ocean container; VGM proof names its method and signer when required.
- **Negative:** An export PDF labels itself carrier-issued B/L or treats QR weights alone as verified gross mass.
- **Related existing BRS:** BRS-POS-02-R001; BRS-POS-03-R004.
- **Acceptance:** `AC-EXP-05-004` / NOT_RUN.

### BRS-EXP-05-R005: Applicable regulated filings and filing actors

**DESIGN · P2 · owner: `external filing authority + native Documents evidence`.** Where material, destination, transit, and law require export filings, permits, consents or jurisdiction-specific documents, Phase 2 SHALL record the applicable decision, responsible exporter/filer, authority and evidence/status with explicit attribution. It SHALL NOT auto-approve material legality, submit AES/customs filings or claim a compliance clearance without authorized integration and verified real result.

- **Positive:** Shipment needing an export filing retains the filer, authority acceptance reference and approved evidence.
- **Negative:** Shipment is marked compliant because the upload filename contains the word approved.
- **Related existing BRS:** BRS-POS-01-R011; BRS-POS-03-R007.
- **Acceptance:** `AC-EXP-05-005` / NOT_RUN.

### BRS-EXP-05-R006: Phase 2 operations remain native-first

**LOCKED · P2 · owner: `native Odoo + Linda + Documents`.** Export SHALL reuse native multi-currency orders, accounting, payments, stock, existing freight/dispatch and document operations for international selling; destination-milestone and report requirements SHALL not cause duplicate finance, carrier mail, scheduler, stock or new payment state machine.

- **Positive:** A CIF invoice remains Odoo accounting, with separate marine insurance evidence and native financial posting approval.
- **Negative:** Ocean release triggers a new export cash ledger or duplicates Linda scheduled reminders.
- **Related existing BRS:** BRS-POS-01-R001..R003,R009.
- **Acceptance:** `AC-EXP-05-006` / NOT_RUN.

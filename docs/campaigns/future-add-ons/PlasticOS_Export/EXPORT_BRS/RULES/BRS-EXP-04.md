# BRS-EXP-04: Phase 1: recycler FOB pickup and FAS port/rail

**Class:** additive design rules; distinct from existing `BRS-POS-*` chapters.
**Primary semantic owner:** plasticos_export contextual UX; native logistics/stock owners
**Authority:** previously operator-locked scope is LOCKED; unapproved technical recommendations are DESIGN. This is an unadmitted planning artifact.
**Phases:** P1 = recycler FOB/FAS; P2 = actual international seller; BOTH = shared.
**Runtime and independent acceptance:** NOT_RUN.

## Rules

### BRS-EXP-04-R001: FOB buyer pickup as industry operation

**LOCKED · P1 · owner: `commercial order + `plasticos_logistics``.** Phase 1 SHALL support `FOB pickup` in the operator’s recycling trade meaning: buyer/agent arranges pickup at the agreed origin. Export MAY display linked booking evidence when supplied but SHALL NOT require ocean booking data or seller-arranged freight for every FOB pickup. Pickup, carrier and physical dispatch remain existing logistics/stock operations.

- **Positive:** A buyer-arranged truck pickup completes with actual pickup evidence and no ocean booking.
- **Negative:** FOB pickup refuses to operate until Steamship Line and Port of Discharge are populated.
- **Related existing BRS:** Operator locked v1.2.0; BRS-POS-10-R007,R014.
- **Acceptance:** `AC-EXP-04-001` / NOT_RUN.

### BRS-EXP-04-R002: FAS inland freight-included delivery

**LOCKED · P1 · owner: `commercial order + `plasticos_logistics``.** Phase 1 SHALL support `FAS delivered port/rail` in the operator’s established recycling trade meaning: seller includes the agreed inland transportation to the identified port/rail destination. It SHALL expose booking details and timing when relevant, reusing existing carrier/freight/load authority; it SHALL NOT infer seller ocean freight or substitute the formal ICC FAS risk-transfer point.

- **Positive:** A seller-arranged drayage load reaches specified rail/port handoff, with separately verified gate/delivery evidence.
- **Negative:** A truck is scheduled, and Export marks ocean freight paid or formal alongside-vessel legal delivery proven.
- **Related existing BRS:** Operator locked v1.2.0; BRS-POS-10-R008,R009.
- **Acceptance:** `AC-EXP-04-002` / NOT_RUN.

### BRS-EXP-04-R003: Physical handoff and commercial allocation are independent

**DESIGN · P1 · owner: `Logistics and native Stock; Documents verification; Export projection`.** Each Phase 1 movement SHALL preserve actual pickup, gate/rail acceptance, named handoff place and source evidence independently of whether a buyer is already allocated. An owned supplier-backed movement with no assigned buyer is an eligible commercial scenario only when its separate authorization and destination/booking requirements are satisfied. Sale order fulfillment or invoicing may occur later under its own native authority; terminal arrival, gate acceptance and legal transfer are distinct.

- **Positive:** An authorized FAS-style shipment reaches the rail ramp with buyer allocation pending; physical evidence is retained and no customer invoice is posted until a genuine sale permits it.
- **Negative:** Gate-in retroactively creates a customer sale, or the load is marked delivered to a nonexistent buyer facility.
- **Related existing BRS:** BRS-EXP-08-R001,R007; BRS-EXP-10-R007; BRS-POS-05.
- **Acceptance:** `AC-EXP-04-003` / NOT_RUN.

### BRS-EXP-04-R004: ERD-to-cutoff dispatch visibility

**DESIGN · P1 · owner: `export schedule view + Linda`.** Where a live booking or terminal appointment exists, Phase 1 SHALL present its current sourced ERD/cargo cutoff window and risk exception to the responsible coordinator. Changes SHALL not independently modify a Linda commitment, dispatch, or send an amendment; these are coordinated through the existing owner.

- **Positive:** Carrier revises ERD after a pickup is proposed; operator sees the conflict and existing dispatcher receives a legitimate action.
- **Negative:** Schedule change silently modifies a confirmed carrier rate or sends multiple reschedule emails.
- **Related existing BRS:** BRS-POS-10-R008,R013.
- **Acceptance:** `AC-EXP-04-004` / NOT_RUN.

### BRS-EXP-04-R005: Native documents and simple views first

**LOCKED · P1 · owner: ``plasticos_export` views/report layout`.** The Phase 1 export UI SHALL prioritize a booking/shipment list/form, ERD and cargo cutoff visibility, missing-evidence exceptions, a linked document view and a small set of native export reports. A dedicated new export workflow engine or complex overseas tracking UI is out of scope.

- **Positive:** Staff complete a real FAS booking and review source docs through one simple view plus existing Odoo records.
- **Negative:** Phase 1 requires a new event bus, overseas vessel polling or independent compliance ledger to generate a dispatch sheet.
- **Related existing BRS:** Operator locked v1.2.0/v1.3.0.
- **Acceptance:** `AC-EXP-04-005` / NOT_RUN.

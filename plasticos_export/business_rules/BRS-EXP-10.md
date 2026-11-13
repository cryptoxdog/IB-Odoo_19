# BRS-EXP-10: Logistics/Linda handoff, schedule constraints and audience-safe packet issuance

**Classification:** Operator-confirmed business scenarios (LOCKED); technical source placement and guarded interfaces (DESIGN).
**Primary owner:** Logistics/Linda owns dispatch and mail; Export supplies requirements and report layouts.
**Scope:** Phase 1 supports multiple partial loads/bookings and legitimate buyer-optional stock; Phase 2 extends the same identities for resale on the water.
**Non-ownership:** No second Odoo Stock, Purchase, Sale, Mail, Documents verifier, freight or transaction state engine.
**Acceptance:** All cases NOT_RUN, pending independent Enterprise/runtime proof.

## Rules

### BRS-EXP-10-R001: Current booking requirements are revision-bound Logistics input

**LOCKED · P1 · owner: `Export current booking view; Logistics decision/dispatch owner`.** Export SHALL provide the exact current ocean booking, source revision, terminal/rail destination, ERD, cutoff, equipment requested and related shipment identities as read-only/typed input to Logistics. An ocean carrier reservation SHALL not be treated as the truck/drayage company commitment; Logistics owns drayage selection, accepted rate, work order and dispatcher state.

- **Positive:** One of four weekly bookings contributes its own terminal cutoff and container type to its corresponding Logistics load.
- **Negative:** An export edit directly sends a drayage order or changes an accepted freight rate.
- **Related existing BRS:** BRS-EXP-02-R002..R004; Logistics BRS-03/04.
- **Acceptance:** `AC-EXP-10-001` / NOT_RUN.

### BRS-EXP-10-R002: Independent supplier PO issue and later booking delivery

**LOCKED · P1 · owner: `native Purchase report + Export booking QWeb + Linda sending owner`.** A legitimate approved supplier PO SHALL be independently issuable through Linda's existing native-Purchase release without an ocean booking, buyer, load, or fictitious order. Supplier readiness and current booking confirmation MAY arrive later. Each current applicable booking original or clearly labeled booking summary SHALL be issued separately as its own revision-bound supplier communication when authorized. If both PO and booking are eligible simultaneously, a single message MAY carry two separately recognizable PDFs; they SHALL NOT be fused into a new document authority. Later weekly bookings under a still-open multi-load PO do not create, reapprove, or automatically reissue the commercial PO. A reference copy of unchanged PO is allowed only under explicit audience/revision-safe policy. Preserve distinct recipient, issue purpose, source revision, attempt and delivery evidence for PO issuance and booking issuance.

- **Positive:** PO 64014 is issued on September 4 without a booking; booking 6509024800 is later sent on September 30, linked to the same PO, without a new PO or duplicate send. A future multi-load PO sends each weekly booking separately.
- **Negative:** PO waits for a booking, four weekly bookings produce four new POs, or a booking amendment silently reissues an unchanged PO or exposes the buyer's price.
- **Related existing BRS:** Logistics BRS-01 and Linda `po_issue`; BRS-POS-06/10; POS-INV-08/10/15/21/22.
- **Acceptance:** `AC-EXP-10-002` / NOT_RUN.

### BRS-EXP-10-R003: Carrier packet: booking and drayage Work Order, audience-safe

**LOCKED · P1 · owner: `Logistics QWeb and authorized Linda sender; Export booking PDF source`.** Export drayage dispatch SHALL use a movement-specific current audience-safe booking PDF and a distinct drayage Work Order PDF plus only operation-required carrier instructions. The Work Order SHALL contain booking reference, equipment/chassis configuration, origin, terminal/ramp destination, pickup windows, supplier hours, ERD, cutoff, appointment and authorized contact context, without supplier buy price, buyer sell price, margin or unnecessary buyer identity. Existing domestic three-PDF dispatch remains unchanged for domestic movements.

- **Positive:** Drayage trucker receives Booking and Work Order for its precise weekly load; domestic truck continues receiving its approved three-PDF packet.
- **Negative:** Carrier is sent the buyer PO, supplier price, or a blanket three-document domestic packet for every ocean container.
- **Related existing BRS:** Logistics BRS-05-R029/R030/R031; BRS-POS-10.
- **Acceptance:** `AC-EXP-10-003` / NOT_RUN.

### BRS-EXP-10-R004: Material amendments protect pending commitments and mail

**DESIGN · P1 · owner: `Logistics/Linda transition and Odoo Mail, Export provides booking version`.** A changed booking, ERD, cutoff, terminal, actual equipment request or material delivery condition SHALL identify the exact affected Logistics movement and pending release/dispatch work orders, queue items and carrier commitments. The authorized Logistics/Linda owner SHALL invalidate or reassess only affected pending artifacts, retain prior sent evidence, and request new rate, schedule or acknowledgment if required. No automatic rebooking, PO reissuance or repeat send is authorized; unknown send outcome remains unknown.

- **Positive:** Week 3 cutoff moves and only week 3 pending work order is held for review; weeks 1, 2 and 4 remain intact.
- **Negative:** AI amendment cancels all four shipments, reissues the supplier PO, or blindly retries an unknown-status email.
- **Related existing BRS:** Logistics BRS-03-R022; BRS-05-R034; Linda send state.
- **Acceptance:** `AC-EXP-10-004` / NOT_RUN.

### BRS-EXP-10-R005: ERD and cutoff are terminal constraints, not supplier pickup dates

**LOCKED · P1 · owner: `Export time values; Logistics pickup feasibility/appointments`.** For each specific load, Logistics SHALL plan a feasible supplier pickup and loaded gate-in from the current ERD, cutoff, terminal/ramp acceptance hours, appointments, loading duration, route transit, chassis/road constraints, buffer and authorized staging where used. ERD/cutoff SHALL NOT be converted directly into pickup appointments; inability to meet the window is a visible exception, not an invented ETA.

- **Positive:** Logistics proposes week-2 pickup timed for the booked terminal acceptance slot, accounting for real supplier hours and travel.
- **Negative:** A missing authorized staging yard is assumed or a date-only ERD is treated as 00:00 supplier pickup.
- **Related existing BRS:** Logistics BRS-03-R017/R020/R022; BRS-EXP-02-R003.
- **Acceptance:** `AC-EXP-10-005` / NOT_RUN.

### BRS-EXP-10-R006: Equipment-aware freight context and explicit commitments

**DESIGN · P1 · owner: `Logistics freight context/booking owner`.** The equipment type, count, container/chassis constraints and requested movement intent SHALL be available to Logistics carrier/rate eligibility at the proper source. Freight reuse or rate confirmation SHALL not treat `equipment_class=None` as proof that a 40HC and a 20STD are equivalent. Binding to PO/owned material with no sale shall preserve company identity and approved authority independently of `sale_order_id`.

- **Positive:** A 40HC drayage movement qualifies only for the correct equipment and approved carrier rate, with no buyer requirement for an authorized unsold-stock move.
- **Negative:** A same-as-last rate applies to incompatible chassis because equipment context is missing; or no SO results in null company.
- **Related existing BRS:** Observed `freight_context.py` equipment_class None and `load.py` company from SO.
- **Acceptance:** `AC-EXP-10-006` / NOT_RUN.

### BRS-EXP-10-R007: Terminal and voyage milestones have distinct evidence

**LOCKED · BOTH · owner: `Logistics delivery tracking + native Documents proof; Export display`.** Pickup, arrival at terminal, accepted gate-in/rail receipt, booking compliance, vessel load/sail, destination discharge, actual customer delivery and legal title/risk milestones SHALL remain distinct facts. Carrier-issued originals, terminal receipts and actor verification govern proof; no status is inferred solely from planned cutoff, a driver photo, a shipping booking or a scanned package.

- **Positive:** A load has delivered-to-port proof while no vessel departure or buyer final-delivery fact exists.
- **Negative:** Gate appointment alone marks ocean shipment sailed or customer invoice paid.
- **Related existing BRS:** BRS-EXP-04-R003; Logistics BRS-06/07.
- **Acceptance:** `AC-EXP-10-007` / NOT_RUN.

### BRS-EXP-10-R008: Movement authorization not tied to buyer visibility

**DESIGN · P1 · owner: `Logistics/Linda audience and buyer-optional movement policy`.** Carrier dispatch SHALL be authorized against exact company, physical load, approved purchase/stock and/or commercial order source, destination, booking when applicable, carrier acceptance, and movement-specific guards. An actual buyer MAY be present but is not necessary for every valid supplier-backed movement; if present, buyer identity remains shielded unless needed and authorized. Existing sales-specific buyer requirements SHALL remain in their legitimate sales workflow.

- **Positive:** Buyerless stock relocation and ordinary buyer-linked sale both use Logistics with different validated eligibility; trucker only sees execution context.
- **Negative:** Exporter invents a buyer to satisfy a global constraint, or PO-only movement bypasses all company and rate checks.
- **Related existing BRS:** Logistics BRS-01-R002/R065; BRS-05-R031; BRS-EXP-08-R008.
- **Acceptance:** `AC-EXP-10-008` / NOT_RUN.

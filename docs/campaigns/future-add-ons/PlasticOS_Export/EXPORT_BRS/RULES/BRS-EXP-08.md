# BRS-EXP-08: Multi-order commitments, partial fulfillment, buyer-optional cargo and allocation

**Classification:** Operator-confirmed business scenarios (LOCKED); technical source placement and guarded interfaces (DESIGN).
**Primary owner:** native Odoo commercial/stock plus Logistics; Export association.
**Scope:** Phase 1 supports multiple partial loads/bookings and legitimate buyer-optional stock; Phase 2 extends the same identities for resale on the water.
**Non-ownership:** No second Odoo Stock, Purchase, Sale, Mail, Documents verifier, freight or transaction state engine.
**Acceptance:** All cases NOT_RUN, pending independent Enterprise/runtime proof.

## Rules

### BRS-EXP-08-R001: Buyer optional before a genuine sale

**LOCKED · BOTH · owner: `native Purchase/Stock + permitted Logistics movement authority`.** A purchase, real owned material, or authorized physical export movement MAY be recorded and progressed without a buyer, customer SO, or assigned end buyer when no sale exists. Supplier, company, approval, stock/custody, movement purpose, destination and applicable booking shall be real; buyer-dependent rules still apply to actual customer-sale release. No fake buyer/order or implied sale shall be used to bypass validation.

- **Positive:** Buyerless purchased material is received or drayed on authorized records, remains unsold and traceable, then is sold later.
- **Negative:** Buyer is mandatory at every physical movement, or system auto-creates a dummy buyer to start freight.
- **Related existing BRS:** BRS-EXP-01-R003; BRS-POS-05; Logistics BRS-01.
- **Acceptance:** `AC-EXP-08-001` / NOT_RUN.

### BRS-EXP-08-R002: One large customer commitment with smaller supply orders

**LOCKED · BOTH · owner: `native `sale.order`/`purchase.order` lines`.** One real buyer commitment (example: customer PO represented by one SO for 30 MRP loads) SHALL be fulfillable through multiple suppliers, supplier POs, and physical shipments. A supplier PO for 4 loads SHALL coexist with that 30-load SO without requiring four separate supplier POs; customer PO evidence is not a supplier PO.

- **Positive:** One 30-load customer SO and one four-load Waste Management supplier PO are both represented natively with correct counterparties and quantities.
- **Negative:** Each new weekly truck creates a new SO or PO, or the buyer PO is mistaken for the supplier PO.
- **Related existing BRS:** BRS-POS-06; BRS-EXP-08-R003.
- **Acceptance:** `AC-EXP-08-002` / NOT_RUN.

### BRS-EXP-08-R003: Partial purchase fulfillment without PO duplication

**LOCKED · BOTH · owner: `native Odoo Purchase and Stock receipt/picking owner`.** A supplier PO MAY authorize multiple separately ready and executed loads across weeks. Native receipt/backorder and delivered/remaining quantity mechanics SHALL be used for each physically executed quantity; the PO obligation remains open for its unfulfilled balance. No Export-created parallel purchase/receipt counters.

- **Positive:** One supplier PO for four planned loads is received across four weekly stock operations and correctly shows three remaining after week 1.
- **Negative:** First receipt closes the PO or Export issues a new PO to substitute for an approved backorder.
- **Related existing BRS:** BRS-POS-05-R004; BRS-POS-06.
- **Acceptance:** `AC-EXP-08-003` / NOT_RUN.

### BRS-EXP-08-R004: Partial sales fulfillment and reserved allocation

**LOCKED · BOTH · owner: `native Odoo Sales and Stock delivery/move lines`.** A customer SO MAY be fulfilled by multiple suppliers and many loads; native reserved/delivered/unfulfilled quantities SHALL remain authoritative per order line and valid UoM. If a buyer is not yet assigned, cargo remains unallocated to a sale until real contract approval. A shipment association SHALL NOT alone validate its stock picking.

- **Positive:** After shipping one eligible load the SO still has 29 load-equivalents open (subject to actual UoM) and a later shipment can satisfy more.
- **Negative:** Assigning a booking decrements SO deliveries, auto-delivers the rest, or books sold quantity before approved allocation.
- **Related existing BRS:** BRS-POS-05; BRS-POS-06.
- **Acceptance:** `AC-EXP-08-004` / NOT_RUN.

### BRS-EXP-08-R005: Independent booking per execution and container cardinality

**LOCKED · BOTH · owner: `Export booking and Logistics exact shipment links`.** One PO/SO may correspond to many bookings and loads; a single booking may cover multiple physical containers. A shipment SHALL identify its exact booking revision; no global one-to-one order-booking rule or single `transaction.load_id` may be used as the only association for a multi-load order. Define the smallest source-owned many-side association after a full cardinality census.

- **Positive:** Four weekly physical loads under one PO have four distinct booking confirmations and dates, each linked to the correct shipment.
- **Negative:** Booking number replaces load ID, or a fourth load overwrites the first three links.
- **Related existing BRS:** BRS-EXP-02-R001; BRS-EXP-07-R004.
- **Acceptance:** `AC-EXP-08-005` / NOT_RUN.

### BRS-EXP-08-R006: Fulfillment allocation is traceable without second quantity ledger

**DESIGN · BOTH · owner: `native Stock/Purchase/Sales actual lines; Export typed linkage`.** When a real order spans shipments or cargo is resold in transit, maintain exact links and quantities between the participating native PO/SO order lines, pickings/moves, shipment/load, container and applicable booking. No allocation may exceed authoritative available/contracted quantities; corrections, splits and reversals SHALL be attributed and must prevent double allocation.

- **Positive:** One four-load PO has four traceable executed quantities each linked to separate bookings, and a received load cannot be allocated twice to SOs.
- **Negative:** Export stores editable aggregate inventory or allows the same stock quantity to satisfy two sales orders.
- **Related existing BRS:** BRS-POS-05; BRS-POS-06; BRS-EXP-01-R002.
- **Acceptance:** `AC-EXP-08-006` / NOT_RUN.

### BRS-EXP-08-R007: Late buyer assignment and on-water resale

**LOCKED · BOTH · owner: `native commercial owner; stock custody; Export historic association`.** Buyer allocation MAY occur after pickup, terminal delivery or ocean sailing when a legal sale is entered and approved. The exact cargo/container/booking remains unchanged; the new sale association retains effective timestamps, actor, source contract, company and audit history. Change of physical destination or regulatory party requires independent logistics/filing authority and cannot be inferred from buyer allocation.

- **Positive:** An unsold container already afloat is sold and linked to a new buyer SO without rewriting its prior gate-in or departure facts.
- **Negative:** Sale order date backdates the ocean booking or changing buyer silently changes delivery partner, customs filer or original B/L.
- **Related existing BRS:** BRS-EXP-05-R001; BRS-POS-05.
- **Acceptance:** `AC-EXP-08-007` / NOT_RUN.

### BRS-EXP-08-R008: Movement eligibility by purpose, not a universal buyer predicate

**DESIGN · BOTH · owner: `Logistics and native authorization owner, not Export`.** Movement release SHALL distinguish sale-backed delivery from approved procurement-owned/in-transit stock relocation or export drayage. Sales movements require a real buyer/SO when that workflow mandates it; lawful buyerless movements require approved company, supplier PO/owned stock authority, route/destination, cargo, applicable booking and permission. Logistics SHALL not rely on `sale_order_id` as the only possible company identity or on one transaction load field as the only exact movement link.

- **Positive:** A supplier-approved buyerless booking uses a company-authorized Logistics movement while ordinary sale dispatch still rejects an absent buyer.
- **Negative:** A generic removal of all buyer checks allows unidentified company/cargo or dispatch without commercial approval.
- **Related existing BRS:** Logistics BRS-01-R001/R002/R065; `plasticos.load.company_id` existing related-to-SO seam.
- **Acceptance:** `AC-EXP-08-008` / NOT_RUN.


# RecycleOS Operational Product Expansion: additive export addendum v1.1.0

**Package status:** standalone exploration and candidate product capability; not implementation authorization, accepted strategic admission, or runtime proof.
**Amendment type:** strictly additive to operational expansion v1.0.0. The original eight non-manifest members are unchanged, byte for byte. This addendum introduces no carryover from upstream strategic documents or other work.

## New scope: Export operations
Extend the previously locked mobile dock, QR/container traceability, physical scale evidence, native Odoo inventory, and document foundations to overseas recycling shipments. The exporter uses one consistent material identity and package ledger from receiving or grinding through container stuffing, booking coordination, port gate-in, shipment documentation and downstream evidence. Export loading must never create a competing stock ledger.

## Six exporter-critical fields (operator supplied, exact names preserved)

1. **Booking No.**
2. **Steamship Line**
3. **Port of Loading**
4. **Port of Discharge**
5. **Cut Off**
6. **Earliest Return Date**

These six are non-optional data capabilities for the proposed export workflow. Their availability for a specific shipment depends on booking progress; do not block saving a draft solely because a carrier has not issued a field. For validated dispatch/port delivery, apply role-authorized, current and source-grounded checks.

## New members

- `08_EXPORT_OPERATIONS_AND_FIELDS.md`: operator-facing flow, exact field meanings, data ownership and integration seams.
- `09_EXPORT_ACCEPTANCE_PROBES.md`: observable design and eventual runtime acceptance scenarios.
- `10_EXPORT_ADDITIVE_EXTENSION.json`: machine-readable extension separate from the unchanged v1.0.0 JSON.
- `MANIFEST.json`: refreshed package membership, hashes and predecessor integrity assurance.

## Source and scope distinctions

- Odoo Inventory owns packages, quantities, stock moves and delivery transitions. Native Sales/Purchase/Accounting own orders, Incoterms, invoices and authorized postings.
- Existing PlasticOS transaction line fields include `lot_no`, `container_no` and `seal_no`, and logistics supports freight/BOL workflows. Their presence does not establish a complete ocean booking/export lifecycle.
- The six fields are operator-selected for product scope. Proposed data relationships, validation gates, timeline and reuse approach are not separately admitted architecture or an implementation contract.
- Earliest Return Date (ERD) refers here to **the earliest date the terminal/carrier will accept a loaded export container for the booked sailing**. It is not the deadline for returning an empty container. Cut Off here primarily refers to the **loaded container/cargo gate-in cutoff**. Separate shipping-instruction, VGM, documentation and customs deadlines must remain independently typed when they exist.

## Adoption boundary

Add this extension to the existing RecycleOS product/operations branch only through its authorized owner. Preserve all v1.0.0 core choices, do not rename technical `plasticos.*` identifiers as a product shortcut, do not trigger outreach, coding, publication, carrier bookings or customs filing. No device, carrier API or customs integration has been proven.

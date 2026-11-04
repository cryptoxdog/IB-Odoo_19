# Target-owner BRS amendments: exact required seams (proposals, NOT merged)

**Status:** DESIGN / owner review required; **NOT** an edit to native BRS, repository or accepted Logistics BRS.

## Logistics BRS-01 / existing transaction-load relation
- BRS-01-R001/R002/R065: recognize a legitimate buyer-optional, approved procurement/owned-stock movement separate from sale-backed dispatch. Keep buyer-required validation for actual sale fulfillment; check origin/company/supplier PO/stock custody, destination, applicable current booking and route authority. Never fabricate a buyer/SO.
- `plasticos_logistics/models/transaction_inherit.py`: the singular `load_id`, buyer constraint and reverse computed linkage cannot represent all 4 loads of one order. Determine correct multiplicity at native Stock/Logistics/Transaction owner before changing associations. Do not simply delete invariant or duplicate loads.
- `plasticos_logistics/models/load.py`: `company_id` currently related to sale order. Buyerless work needs a real company authority not dependent on an SO. Exact approval source and counterparties are mandatory.

## Logistics BRS-03 / BRS-04
- BRS-03-R017/R020/R022: consume current booking ERD/cutoff with timezone and source revision; feasible pickup is derived by Logistics, with terminal hours, staging, truck/route, not copied from cargo cutoff. Change holds only affected pending commitments.
- BRS-04-R027: carrier booking/acceptance must include correct movement, equipment/chassis, rate/currency, booking revision; `freight_context.py` currently emits `equipment_class: None` and keys repeat stream to intake. Never reuse incompatible freight or imply an existing sale order.

## Logistics BRS-05 / Linda
- BRS-05-R029/R030: retain approved domestic three-PDF packet for domestic carrier loads; create movement-specific export drayage packet with **Booking.pdf** and **Drayage Work Order.pdf**, plus only actually needed documents. Do not send buyer identity or economics to the drayage carrier.
- BRS-05-R031/R034: a supplier PO and the later booking are **separate issuance obligations**. The PO may be approved and sent before a booking exists (as in the September 4 PO 64014 / September 30 booking example). For four weekly bookings under one approved PO, do **not** reissue or recreate the commercial PO every week. Send each current booking separately when authorized; optionally attach a revision-safe unchanged PO reference copy only if policy permits. When both are simultaneously eligible, two separately recognizable PDFs may accompany one Linda message. Linda owns all actual sends, acknowledgments, recipient scopes and idempotent retry decisions.
- Require carrier acceptance and current packet acknowledgment as separate facts; stale / sent / unknown mail outcomes stay distinct.

## Logistics BRS-06 / BRS-07
- Record actual pickup, gate arrival, gate acceptance and accepted terminal/rail evidence separately. One of 4 loads delivered does not mark all PO/SO or order-aggregate transaction delivered; no inference of vessel departure/customer delivery. Native stock and existing state owner handle valid partial execution.

## Documents / Native-First BRS owner
- `plasticos_documents_native/models/document_native.py::_auto_link_partner` currently selects the newest open transaction for a partner. That is insufficient and potentially unsafe for 4 distinct weekly booking documents. Require exact company/booking/physical shipment attribution or review queue; never auto-link by partner alone.
- Odoo 19 Documents AI sort/AI actions may propose extraction, but `plasticos_documents` must arbitrate exact document identity/verification and `plasticos_export` may accept only its own approved booking fields.
- Native Odoo AI server action is a decision maker; authorized business commands must check all invariants before mutations. No second document verifier or direct `transaction.state` write.

## Native Purchase / Sales / Stock owner
- One native customer SO for 30 loads and supplier PO for 4, fulfilled incrementally via real pickings/receipts/backorders and native order-line quantities, not artificial split orders.
- Cargo can exist without buyer and be sold while on the water; this is a legitimate distinct lifecycle, not a reason to create a dummy SO. Allocation to eventual sale must be traceable, quantity-correct and approved.

## Evidence and status
Source inspection at `cryptoxdog/IB-Odoo_19@04bd0594a7c9dcad53d9c45fc65276d76817c112`; runtime/Enterprise behavior, full impact census, independent tests **NOT_RUN**.

Official Odoo 19 evidence: https://www.odoo.com/documentation/19.0/applications/productivity/ai/document_sort.html ; https://www.odoo.com/documentation/19.0/applications/productivity/ai/server-actions.html ; https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/shipping_receiving/setup_configuration/multipack.html

## v1.3 real booking correspondence and rolls - proposed owner amendments

- **Documents / native AI:** accept email body, attached booking PDFs, spreadsheet and scale ticket as separately attributed evidence; preserve original versions, message timestamps and cited field locations. Treat inaccessible supplier picture links as references, not verified received photos. One decision authority for evidence verification.
- **Exact association:** disallow latest-open partner transaction matching for booking/scale evidence; tie booking 6509024800, PO 64014, container CSNU8490558, seal 7695652, and scale ticket 1728952 to one physical LOAD 1; do not close five PO units.
- **Export context:** identify same-booking roll, replacement booking, supplemental equipment or unconfirmed schedule; preserve field revision and source; block automatic replacement of 1 x 40HQ with 2 x 40HQ from a separate email until exact booking identity and source authority are confirmed.
- **Logistics/Linda:** treat an approved roll as a scoped schedule/packet invalidation; existing sent mail evidence and unrelated loads remain. Supplier-Delivered FAS movement must not assume company-booked drayage or drayage work order is always applicable.
- **Native Purchase/Accounting/Stock:** PO 64014 $0.04/lb vs supplier scale ticket $0.03/lb is a documented source contradiction requiring commercial owner handling; 40,200 lb is a measured net-load candidate, not indiscriminate AP/AR change or certified VGM.
- **Cross-state:** supplier says booking complete on Oct 8; no automatic proof of gate-in, ocean load or voyage completion.

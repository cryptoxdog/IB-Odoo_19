# Operator workflows: physical material first

## WF-01: Receive a container with only a platform scale

**Site:** small recycling/grinding facility, platform/floor scale, iPhone or handheld scanner, optional label printer.

1. Open **Receive** on RecycleOS Dock and select the intended incoming delivery/purchase or an authorized exception/intake path.
2. Place the Gaylord/pallet/container on the platform scale. Capture gross weight automatically from a supported scale adapter **or** enter the displayed reading manually. Record tare (known verified container type or actual tare), preserve original units, calculate net.
3. Scan an existing uniquely assigned QR/container label or issue and attach a new one; choose/verify the material definition, source lot and condition. One lot may span many boxes.
4. Review required checks (wrong material, weight mismatch, contamination or missing order, where applicable) and **confirm receipt once**. Confirmation posts/validates the authorized native Odoo stock receipt and associates the container, net weight and receiving location.
5. Optional: scan location to move the container inside the warehouse; this is a distinct move, not a duplicate receipt.
6. At load-out, scan the exact container into the assigned outbound delivery; confirm loading and validate the native delivery when actual dispatch requirements are satisfied.

**Happy-path promise:** one scale reading + one container scan + one confirmation to receive. Another scan when genuinely loading onto a truck.

**Avoided:** typing the same weight into two systems, receipt completion inferred from scan alone, forced truck-scale requirement at platform-only sites.

## WF-02: Grind purchased scrap and sell finished regrind

1. Receive input scrap containers as distinct stock packages with verified input lots and net weight.
2. Stage them for a native Odoo Manufacturing Order / Bill of Materials describing the process and its input/output products.
3. Scan the selected input containers when they are actually consumed; ensure native stock consumption records the attribution.
4. Record actual output product (e.g., PP regrind vs. PP molded scrap), recovered output weight and residual/by-product according to configured process rules.
5. Weigh/identify each finished output container; issue new physical container identities and labels for those new boxes.
6. Receive finished output into the proper Odoo location/lot; the production genealogy links output to consumed input lots.
7. Scan outgoing finished containers onto the correct customer delivery, preserving weight/lot/package evidence.

**Identity rule:** regrind is NOT the same stock product, lot, or individual container as the raw molded scrap simply because both are PP. Inputs are consumed; outputs are created and linked by the production event.

**Illustrative numbers only:** 10 incoming boxes could become 9 outgoing boxes; output mass need not match input mass. Track residues as saleable by-product, scrap or measured loss according to reality rather than assuming all difference is unrecoverable waste.

## WF-03: Shipper with a truck scale

1. Identify the vehicle/load and expected receipt or shipment.
2. Capture a source-attributed gross/tare pair from a supported certified weighbridge indicator or controlled weigh-ticket import; calculate/check net and packaging adjustments according to the transaction.
3. Preserve ticket ID, indicator/device/site, timestamps, original units and evidence attachments, plus any certification metadata available.
4. Identify and reconcile the containers/packages on the movement where container-level handling is required.
5. Show variance and obtain review on conflicts; write validated physical receipt/delivery through native stock and separately apply authenticated supplier/buyer settlement rules.

**Not promised:** that Odoo's standard retail-scale IoT driver works with any weighbridge, or that receiving a scale byte stream alone establishes certified or contractually payable weight.

## WF-04: Scan container into outbound load

- Operator opens a specific Odoo delivery/load, scans each eligible outbound package and sees matching material, reserved/available status and recorded weight.
- Wrong product, already loaded, wrong lot, canceled order, absent stock, duplicate scan, and cross-company package must not silently pass.
- The screen shows running container count and total recorded **physical** net weight; legal/contractual billing weight is separately governed.
- Partial load/unload must be representable without marking the entire delivery complete.
- Authorized confirmation produces the native stock-delivery movement and associates actual load evidence.

## WF-05: Exceptions worth designing before launch

- Scale cannot connect: manual entry with explicit source, unit and identity, no claim of automatic reading.
- Box with torn label: lookup/reissue under controlled audit; no accidental new inventory.
- Tare mismatch: flag for correction, preserve source reading and audit trail.
- Two operators scan the same box: no duplicate quantity/movement.
- Same box is partially emptied: reconcile residual net weight and package/material movement explicitly.
- Wrong grade found after receipt: controlled reclassification/correction, not overwrite of original evidence.
- App offline: observe/capture locally only if supported, reconcile before authoritative commit, and show unsynced state; no assumed offline support.
- Customer-owned toll-grind material: avoid treating custody as owned inventory or automatically creating raw-material purchase cost; this is an important **hypothesis to validate**, not an already locked requirement.


## WF-05: Cross-order ocean booking and staggered material availability

1. Native SO may commit 30 loads of MRP; a supplier's single native PO may commit four partial loads. No load or buyer is fabricated to force a one-to-one pairing.
2. Supplier confirms one actual load ready per week. Issue a distinct booking or assign only actual container capacity under the existing booking as evidenced by the carrier/forwarder. Store each booking and its changes with attributable source and terminal-specific time window.
3. Physical loads, seals, ticket weights and photo evidence are linked to the correct ordered/stock movement identity, preserving partial fulfilled/outstanding PO and SO quantities. A 5-container consolidated ocean booking may include containers from **four different supplier POs**, not just one.
4. A PO may be issued before its booking exists. Booking copies go to authorized supplier recipients later without reissuing the commercial PO. Supplier-delivered FAS requires no fabricated drayage carrier or Linda Work Order.
5. Buyer assignment may remain absent for legitimate purchased inventory or in-transit cargo until a real sale; the actual commercial allocation can later be recorded without rewriting earlier physical events. Buyer identity is not the same as the port/rail delivery destination.
6. AI Documents proposes exact sourced fields and matches; Export accepts its booking context, Documents verifies evidence, Logistics owns the actual movement and customer/supplier communications, and Odoo Sales/Purchase/Stock/Accounting own order, stock and money consequences.

**Reject:** treating one booking as one SO/PO, multiplying loads on report joins, inferring that a later booking version proves terminal acceptance or that a supplier completion email proves ship departure.

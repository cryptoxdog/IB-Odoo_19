# RecycleOS export operations: containerized recycling material

**Class:** additive operational product concept; not an execution contract.
**Operator-selected critical booking fields:** Booking No., Steamship Line, Port of Loading, Port of Discharge, Cut Off, Earliest Return Date.
**Primary scenario:** a recycler, broker or exporter purchases/batches recyclable material, assigns packages to a booked ocean container, scans them during stuffing/loading, delivers the sealed container into the terminal receiving window, coordinates forwarder/customs documentation, ships overseas and reconciles delivery and payment.

## 1. Core flow and native ownership

| Step | Physical/export action | Record reused or proposed | Disposition |
| --- | --- | --- | --- |
| 1. Buy and receive | Purchase scrap or processed material; capture weight, lot and package QR identity | Native purchase, stock packages/receipts; existing material registries | Reuse core |
| 2. Book ocean transport | Select buyer, booking, steamship line, origin/destination ports, applicable Incoterm | Native sale/purchase/Incoterms; linked export-booking projection/extension to be designed | Proposed workflow |
| 3. Plan container stuffing | Allocate eligible inventory, empty container, pickup, terminal and loading site | Native stock reservations/packages; existing load/logistics evidence where applicable | Reuse with export-specific bindings |
| 4. Scan during stuffing | Capture actual package IDs and their net weights, with separate packaging/scale evidence | Odoo package and picking identity; proposed scan-to-container manifest | Proposed dock extension |
| 5. Seal and review | Capture ocean container equipment number, seal, photos, cargo weight and validated VGM evidence when required | Existing transaction `container_no`/`seal_no` plus authoritative documents; export shipment linkage | Reconcile rather than duplicate |
| 6. Deliver to port | Check ERD through cargo cutoff, terminal/appointment, gate-in evidence | Proposed versioned carrier/terminal milestones; native stock operation separately validated | New export status and timing logic |
| 7. Document/export | Packing list, commercial invoice, shipping instructions, forwarder/ocean B/L, applicable regulatory filings and approvals | Native Odoo accounting/document evidence and existing PlasticOS Documents; external regulated filer retains authority | Reuse and coordinate |
| 8. Depart/arrive/settle | Capture actual carrier milestones, delivery proof, settlement evidence | Existing sales, freight, invoices, stock, document records | Reuse with shipment identity |

A physical container scan is not proof of legal export, vessel loading, stock delivery validation or payment. All consequential native transitions require their own authorized control.

## 2. Six first-class booking fields

The following **display names are preserved exactly** from the operator. Suggested internal field names are provisional, not a demand for new duplicate models.

| Display field | Proposed logical key | Meaning and validation |
| --- | --- | --- |
| **Booking No.** | `booking_number` | Ocean carrier/forwarder-issued booking reference, kept as a string to preserve leading zeros, prefixes, punctuation and original formatting. Bind to steamship line and booking revision; multiple containers may share one booking. Do not confuse with SO/PO, container number or B/L number. |
| **Steamship Line** | `steamship_line` | Actual ocean carrier/operator associated with the booking, preferably linked to existing `res.partner`. Keep separate from freight forwarder, NVOCC, customs broker and drayage carrier. Source and changes attributable. |
| **Port of Loading** | `port_of_loading` | The ocean loading port (POL), ideally with a controlled identifier such as UN/LOCODE where available. Do not confuse with shipper warehouse, port terminal or inland rail ramp. |
| **Port of Discharge** | `port_of_discharge` | The ocean discharge port (POD). Do not assume this equals the final customer destination or place of delivery. |
| **Cut Off** | `cargo_gate_in_cutoff` | Latest date/time loaded export containers are accepted for the booked vessel at the applicable marine/rail terminal. Preserve terminal-local timezone, source, revision and cutoff kind. Do not collapse VGM, shipping-instruction, document, customs or rail-specific cutoffs into this field. |
| **Earliest Return Date** | `earliest_return_date` | ERD: earliest carrier/terminal permitted date/time a **loaded export container** can return/gate in for that sailing, opening its receiving window. Preserve local timezone, effective source/revision and terminal. Not an empty-container return deadline, free-time expiration or container availability promise. |

Time entry: keep the original provider's wall-clock value and IANA/local timezone (including daylight-saving context), normalize for comparison, and preserve whether the provider gave date-only or full timestamp. No guessed midnight or 23:59 cutoff. When sources disagree, require a source-of-truth decision or operator verification before scheduling a gate move; retain all source observations.

A booking may be edited, rolled, amended or canceled. Its sailing/terminal/carrier time window may change. Store versions and the observation source; never silently overwrite the previous ERD or cutoff or treat a stale screenshot as current.

## 3. Necessary supporting fields (NOT operator-locked as first-class priorities)

To make the six critical fields actionable, candidate supporting data includes: shipper/exporter and consignee/notify party; contract/order; freight forwarder/NVOCC; terminal and gate location; vessel and voyage; ETD/ETA; equipment type/size; container number and seal; empty pickup date/release; return appointment; booking status and revision; loaded package manifest; gross, tare, net and VGM with calculation method; gate-in/accepted status; ocean B/L reference/issuance/release; applicable shipping instructions, verified documents and customs/export evidence; exception/roll reason. Add each at the actual responsible owner only after checking native/existing fields.

- A booking can contain multiple ocean containers; a physical package can be loaded in at most one active actual container movement at once; a material lot may be split across many packages and containers.
- Ocean freight container identity is not the same as a Gaylord, pallet, Odoo `stock.quant.package`, manufacturing lot, or `plasticos.transaction`.
- A shipment's commercial origin and its actual physical export loading point must not be assumed identical.
- Export permits and waste classification depend on exact material, destination and transit jurisdictions; not every plastics shipment has the same requirements.

## 4. Dock-first export loading experience

Conceptual mobile flow: **select current booking -> select equipment/container -> scan existing Gaylord/bale/pallet QR labels -> verify stock eligibility and individual weights -> show live package count, net cargo weight and material/lot coverage -> enter or scan seal -> collect source photos/tickets -> review and confirm the authoritative Odoo shipment/movement**.

No duplicate relabeling of existing tracked packages. Material remains traceable back to supplier, reception and production where present. A worker sees simple scans and exceptions, not extra accounting screens.

**Do not assert** that the sum of scanned package weights itself constitutes a compliant Verified Gross Mass (VGM). Approved weighing method, full tare/packaging/securing inclusion, signoff, submission and jurisdictional requirements are a separate proof obligation.

## 5. Timing, document and exception handling

- **Receiving window:** `Earliest Return Date <= actual intended terminal gate-in <= Cut Off`, with zone, terminal and source-matched current booking revision. For date-only or uncertain schedules, show advisory status until the responsible party confirms the operating window. Do not assume a universal terminal policy.
- **Other deadlines:** separately capture `shipping_instruction_cutoff`, `vgm_cutoff`, `document_cutoff`, `customs_filing_deadline`, and `rail_cutoff` only where applicable. Every cutoff has distinct source, type, effective window and acknowledgment.
- **Before ERD:** warn of possible refusal/storage or additional cost, do not mark delivered to terminal based on a dock scan.
- **After cutoff:** warn/require revised booking or authorized exception; no automatic amendment or release.
- **Carrier/terminal disagreement:** show both observations, provenance and current confirmation requirement. Carrier website/terminal may disagree. Never pick one merely because its timestamp is newer if it is not authoritative for that terminal/booking.
- **Rolled sailing:** keep prior ERD/cutoff evidence and loaded inventory/container identities; bind new booking/sailing revision explicitly, re-evaluate all related deadlines.
- **Documents:** one source original per document, typed association to booking/shipment/container/load/order, verified applicability and authority. Preserve sea B/L (carrier/forwarder-issued) as distinct from domestic truck BOL templates.
- **Weight authority:** platform scale, truck scale, buyer/supplier, cargo manifest and VGM are related but not interchangeable; do not automatically use a scale observation to settle AP/AR or auto-post finance.

## 6. Product differentiation and bounded proof

A useful exporter-facing view answers: Which containers are booked, what exact material is in each, which are ready, what is missing for release, and which ERD/cutoff windows are at risk?

Earliest discriminating scenario: create one real-shape ocean booking with all six fields, scan a mixed set of existing labeled material containers into one ocean container, generate a package-derived contents manifest, preserve separate export document evidence, and test an amended ERD/cutoff. Prove one native stock transition and no duplicate inventory. This remains **NOT_RUN**.

## Sources (scope, not deployment proof)

- Odoo 19 package identity and nested container references: https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/product_management/configure/package.html
- Odoo 19 Incoterms: https://www.odoo.com/documentation/19.0/applications/finance/accounting/customer_invoices/incoterms.html
- Federal Maritime Commission Fact Finding 29 Final Report, p.19 (terminal ERD and export cutoff; carrier/terminal discrepancies): https://www.fmc.gov/wp-content/uploads/2022/06/FactFinding29FinalReport.pdf
- Federal Maritime Commission MTDS recommendations: https://www.fmc.gov/wp-content/uploads/2024/12/Final-Recommendations-on-the-MTDS-Requirements.pdf
- APM Terminals export booking interface documentation, booking container milestones: https://developer.apmterminals.com/node/58
- `cryptoxdog/IB-Odoo_19` pinned source revision `04bd0594a7c9dcad53d9c45fc65276d76817c112`, `plasticos_transaction/models/transaction_line.py`, `plasticos_logistics/models/load.py`, and `plasticos_logistics/data/incoterms.xml`: source field existence only, not a validated ocean workflow.

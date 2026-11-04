# Booking availability and allocation workbench: Phase 1 UX refinement

**Status:** DESIGN proposed within the frozen architectural envelope. **Owner:** `plasticos_export` for booking/slot data and views; all source owner boundaries remain as in the operator-frozen design. See BRS-EXP-14-R014..R021; no engine or frontend duplication.

## The main operator questions

- What confirmed ocean carrier space is available **right now**, by equipment type, company, shipping line, POL/POD, vessel, ERD and cutoff? Confirmed is not pending or AI-proposed.
- Which booking slots are assigned to eligible supplier POs / actual shipment loads, and which are physically loaded, terminal accepted or unresolved? Keep planned, committed and physically evidenced milestones separate.
- What cargo is confirmed READY but not booked? What cargo/bookings have no buyer yet? Who is responsible for next action?
- Which changed bookings threaten existing allocations, carrier packets or deadlines? Show revisions and exact impacted physical movement links.
- What are the outstanding documents, and who may verify or chase them? Do not independently verify or send from Export.

## Default Phase 1 menu

1. **Export > Overview** (landing dashboard): confirmed remaining 40HC/40STD/45HC/45STD/20STD slots, today's deadline risks, space overcommit, ready-unbooked cargo, outstanding evidence; every number drills to a native list of source records.
2. **Export > Bookings** (native list/form with 'Capacity & allocations' tab): number, steamship line, forwarder, carrier source/revision/status, POL/POD, vessel/voyage, ETD/ETA, separate ERD/cargo/doc/VGM cutoffs with TZ, equipment quantity and net availability. Smart buttons for booked cargo, actual containers, documents, Logistics activities.
3. **Export > Allocations** (grouped list / explicit assign action): booking -> *distinct* slot or eligible source order line/planned movement -> actual physical load when known. No fake physical records; show status and source. A mixed-PO container still consumes one equipment slot.
4. **Export > Containers / Shipments** (operational detail): one row per real physical container journey, booking and revision, number, seal, actual supplier PO, buyer SO if allocated, source weight and unit, current document evidence, Logistics gate-in evidence. Do not multiply row counts through joins.
5. **Export > Deadlines** (calendar and saved list): ERD, cargo, document, VGM cutoffs, at-risk source revision, owner; actual appointment and carrier packet actions route to Logistics.
6. **Export > Reporting** (Odoo pivot/graph/spreadsheet): booking capacity/utilization, supplier/PO/grade/port trends, exceptions, shipment status, document gaps; one-click XLSX/CSV. QWeb only for audience-approved print snapshots.

## Status semantics and figures

**Source-confirmed capacity** is specific to booking, carrier, company, equipment type and current source revision. `available = confirmed - distinctly committed eligible slots - explicitly authorized holds`, but only for an effective usable booking and under same equipment type; a proposed/cancelled/expired/rolled booking has no assignable capacity until re-confirmed. Physical `loaded`, `dispatched`, `terminal accepted` and `ocean sailed` are separate observed counts, *not* quantities to subtract again or statuses that automatically return capacity. A source revision reducing 5 to 4 while 5 slots remain committed creates an over-allocation exception. Do not auto-delete the oldest slot or fabricate a carrier release.

Order fulfillment is native SO/PO line quantities, not the number of booking slots. Cargo allocated to a booking can remain commercially buyer-unassigned; a PO may supply different bookings across weeks. Slot allocation is not physical movement, document verification, or financial posting.

## Reports, lean by default

| Report | Grain | Minimum outputs | Phase |
| --- | --- | --- | --- |
| Booking Space Availability | Booking x equipment type | Carrier, POL, POD, ERD/cutoffs, confirmed, allocated, remaining, revision | P1 |
| Booking Allocations / Manifest | Booking > physical slot/container | Exact cargo supplier PO lines, buyer SO if any, container/seal, net weights and source, exceptions | P1 |
| Container Shipment Register | Container journey | Unique container, source transaction/load, booking, terminal acceptance status, document readiness | P1 |
| Open Commitments | Native PO/SO order line | Ordered, actually shipped/received via owners, remaining; linked booking count (display only) | P1 |
| Deadline and Booking Change Exceptions | Booking revision / affected load | New/old value, effective source, cause, affected Logistics obligations and human next action | P1 |
| Missing Export Documents | Exact evidence obligation | Required document, owner, current verified state, linked original, party to chase via Linda | P1 |
| Export Economics | Accounting-linked source | Approved costs/margins where independently established, buyer/supplier/commodity trends | Phase as source owners permit |
| Ocean Tracking / EEI status | Provider observation / filing | Source-labeled FindTEU milestones and AESDirect outcome/ITN; never fabricated | P2 |

Use saved Favorites, grouped lists and native dashboard spreadsheet, not custom stored report rows unless native query semantics cannot meet measured performance. External scheduled email reports are not required in Phase 1.

## Key acceptance examples

- The real booking 6509024800 has 5 x 40HC and five distinct physical container rows from four POs; it has **0 available** when all five slots are committed. Don't assert actual sailing from a source schedule or supplier email.
- A single booking with two supplier PO lines packed into one verified container consumes **one** booking slot; native stock/trade quantity attribution remains distinct.
- A four-load supplier PO delivered weekly remains one approved PO and may split across four independent ocean bookings.
- A booking amendment from 5 slots to 4 exposes one overallocated slot, keeps all historical records, and cannot trigger Linda re-send without authorized owner action.
- Booked but buyer-unassigned cargo, confirmed but empty bookings, and supplier-ready but unbooked cargo appear in their appropriate distinct views.

## Locked dashboard behavior: six reports, one decision surface

**Cross-cutting candidate:** `POS-INV-24` applies to **all PlasticOS / RecycleOS dashboards**, not merely this Export workbench. **Export BRS owner:** `BRS-EXP-14-R017/R021/R022`. Status: operator-approved UX direction inside frozen module boundaries, NOT implemented or constitutionally admitted.

An Export Overview MUST actually **show** the most important current information from EACH report below, not merely offer six menu links. Each summary/number/chart title links to its corresponding filtered report; interacting with a specific value opens the exact contributing population. From a report row, the user reaches the booking, shipment, PO/SO, exception or verified document subject and, where authorized, its source evidence.

| Dashboard section -> linked report | On-dashboard vital facts | Link destination / declared counting grain |
|---|---|---|
| **1. Available Space -> Booking Space Availability** | Confirmed, allocated and assignable capacity by 40HC/40STD/45HC/45STD/20STD; expiring/unused slots | Active, source-confirmed booking x equipment; opens relevant bookings and capacity allocation |
| **2. Allocation -> Booking Allocation / Container Manifest** | Allocated slots vs confirmed, overallocated bookings, mixed-PO booking assignments | Booking x distinct slot/container; opens exact allocations, bookings, POs and loads |
| **3. Open Orders -> Open PO / SO Fulfillment** | Open purchase and sale quantity by units; ready-but-unbooked eligible loads | Native PO/SO line grain, with cargo and booking references; opens native orders and related movements |
| **4. Shipment Progress -> Container Shipment Register** | Distinct loaded, in transit and terminal-accepted container journeys; pending actual receipt | One real physical container journey, independent of booking/order joins; opens load, container and accepted movement evidence |
| **5. Upcoming Cutoffs -> Cutoff & Booking Exceptions** | Deadlines approaching, rolled/cancelled revisions, at-risk commitments and infeasible planned movements | Current booking revision and affected actual movement; opens exact exception, booking revision and Logistics view |
| **6. Documentation -> Missing Export Documents** | Missing/overdue *current verified* obligations grouped by party, material due date and operation | Operation-specific evidence-obligation grain; opens Documents original/verification and, for outbound chase, Linda obligation |

**Mandatory navigation chain:** Overview -> **matching filtered report** -> **exact authorized business row** -> **linked authoritative original/evidence** where applicable. For a chart title, the first click can open its full report. For a metric/data point, the first click must narrow to the supporting population rather than a generic unfiltered list.

**Shared context:** Preserve active legal company/companies and Odoo record rules, dashboard date period, equipment, booking, port, ownership/party scope, current or historical revision selector and exception category as applicable. If the underlying data changed since rendering, display refreshed/as-of context; an old summary must never masquerade as the current detail. Respect missing-source/unknown/pending states; *zero missing* is only zero when the relevant evidence evaluation actually ran. Enforce user rights at both dashboard and target. No aggregate count leakage from another company. No metrics added by joining one container to multiple supplier PO/document records.

**Native-first implementation guidance (not a new architectural primitive):** Odoo 19 Spreadsheet Dashboards can link chart/table data points to database records and their titles to native list/pivot/graph views; global filters and group/record rules exist. Minimal authorized action/filter glue is allowed only where required to carry cross-model scope. If Dashboards is not installed, start with authorized Odoo menus/list/pivot views and preserve equivalent navigation rather than implement a second reporting engine.

**No new owner:** Export owns only booking-slot allocation and display of export-context facts; native Purchase/Sales/Stock and Logistics own the underlying movements and ordered quantities; Documents owns business verification, Linda owns outbound communication. The dashboard itself is never an approval, dispatch or financial writer. Optional economics and Phase 2 provider reports may be added later, but do not replace one of the six mandatory Phase 1 report surfaces.

**Counterexample contract:** 6509024800 represents five distinct assigned 40HC journeys from four supplier POs. Capacity and shipment count both equal five only for their **different grains**; the system may not turn the five into ten via PO/document joins or treat source-reported net weight as certified VGM. A user without source permissions gets neither the underlying restricted record nor a leaked preview count.

**External platform evidence:** https://www.odoo.com/documentation/19.0/applications/productivity/dashboards.html and https://www.odoo.com/documentation/19.0/applications/productivity/dashboards/build_and_customize_dashboards.html ; provider API/Enterprise runtime availability must be verified on target.

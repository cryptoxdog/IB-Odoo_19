# PlasticOS Export

**Ocean bookings and export operations, without rebuilding Odoo.**

`plasticos_export` is the proposed thin Odoo 19 Enterprise addon for recycling businesses that buy and sell material in multiple loads and coordinate shipping space at ports and rail ramps. It gives operators a clear picture of carrier bookings, available container slots, shipment allocations, deadlines and supporting documents. It leaves the execution of orders, inventory, trucking, communications and accounting with their existing owners.

> **Status:** This README describes the **frozen design**, not a released addon. The module does not exist on the inspected Staging revision `04bd0594a7c9dcad53d9c45fc65276d76817c112`. Do not use these descriptions as evidence of installed, tested or live functionality.

## The problem this solves

A customer might order 30 loads of reprocessed material while one supplier agrees to provide four. Those four loads may become ready in four different weeks, each with a different steamship booking. Another booking might contain five containers assembled from four separate supplier purchase orders. A buyer can be assigned after cargo is acquired, or cargo can change hands while already on the water.

Neither the Sales Order, Purchase Order nor trucking load is the ocean booking. Every one of those records has a distinct purpose and lifecycle. The export operator needs to see them together **without merging their identities or changing their underlying authority**.

## The Phase 1 operator's day

1. **Open Bookings.** Review available and confirmed space, carrier, ports, equipment and the current ERD and cutoff window. A requested booking is not confirmed space.
2. **Allocate space.** Assign one or more available 20STD, 40STD, 40HC, 45STD or 45HC container slots to eligible material, with references to real purchase/sale order lines and physical execution when known. A slot is counted once even if cargo includes material from multiple sources.
3. **Release the right instructions.** A supplier PO can be issued before a booking is obtained. A later booking confirmation is sent separately through authorized Linda/Odoo Mail. When the supplier arranges its own FAS inland delivery, no fictitious drayage order is created. When the operator contracts trucking, Logistics owns carrier selection, work order and dispatch.
4. **Watch the dates.** Terminal ERD and cargo, documentation and VGM cutoffs have distinct sourced meanings. A changed booking can invalidate affected allocations or trucking commitments, but it cannot automatically renegotiate freight or resend unrelated emails.
5. **Receive evidence.** Original emails, bookings, scale tickets, photos and terminal receipts stay in native Documents. AI may propose extracted values and exact typed links. Only authorized business actions may accept changes or advance order, load, document or financial states.
6. **See the truth at a glance.** The dashboard summarizes six native-backed reports and opens the exact filtered records underneath each metric. A truck arriving at the terminal does not, on its own, prove gate-in or sailing.

## Navigation

```text
Export
  Overview              (source-derived dashboard, not a second ledger)
  Bookings              (carrier reservations and revision history)
  Allocations           (space committed vs available)
  Containers / Shipments (actual equipment, loads, seals and evidence)
  Deadlines             (ERD, cargo/doc/VGM cutoff and exception views)
  Reporting             (six core reports with native filters and export)
```

### What the Overview must answer

| Report / drill-down | Most useful immediate summary |
| --- | --- |
| Booking Space Availability | Confirmed 40HC/other slots; allocated; genuinely available; carrier unknowns |
| Booking Allocation / Container Manifest | Slot assignments, container/PO/SO coverage, overallocations and unfilled capacity |
| Open PO / SO Fulfillment | Ordered vs completed quantities, supplier-ready cargo lacking space |
| Container Shipment Register | Loaded, moving, terminal-accepted and documentary status by distinct container |
| Cutoff & Booking Exceptions | Upcoming ERD/cutoff risk, rolls, cancellations, amended capacity and stale work orders |
| Missing Export Documents | Missing/unverified/expired obligations by exact shipment and responsible party |

Every dashboard tile must be a **projection**: it reads the real record owner, shows an as-of/provenance and the difference between zero and unknown, honors company/party permissions, and opens the appropriately scoped source report and exact record. Odoo's native dashboard and spreadsheet tooling are the preferred implementation.

## Booking information

The six principal booking fields are **Booking Number, Steamship Line, Port of Loading (POL), Port of Discharge (POD), Cutoff, and Earliest Return Date (ERD)**. Additional sourced context includes terminal and rail destination, empty pickup and loaded return addresses, equipment type/count, vessel/voyage, confirmed/estimated ETD/ETA, document and VGM deadlines, booking party, and carrier confirmation. Date-time values retain their actual local zone and precision. A missing field is unknown, not inferred from a different address or date.

A carrier-issued booking confirmation is not the same artifact as an operator-generated summary. Same-number amendments, rolled bookings, new numbers and cancelled reservations retain their previous originals and accepted revisions. A change must be matched to the right booking before it changes the current projection or affects Logistics.

## Ownership contract

| Owner | What it alone controls |
| --- | --- |
| Native Purchase / Sales | Commercial commitments, quantities, approvals and order status |
| Native Stock | Real stock moves, receipts, ownership/custody and quantities where applicable |
| Logistics / Linda | Carrier/trucking commitments, schedule, dispatch and outbound correspondence |
| Native Documents | Original files and versions; incoming email/attachment custody |
| PlasticOS Documents | Exact typed business evidence, current verification and applicable overrides |
| Export | Ocean-booking context, capacity reservations, assignment context, deadline projections, export-facing views and report layouts |
| Native Accounting | Invoice, vendor bill, credit/debit, payment and settlement authority |

An export booking may have multiple physical loads and supplier POs. Orders can be independently approved and partially fulfilled. Cargo without a buyer is legitimate when its purchase/custody/movement authority is real. The commercial buyer is not assumed to be the physical destination; the latter may be a port terminal or rail ramp. Trade shorthand such as industry FOB pickup and FAS delivered-to-port must remain distinct from formal legal Incoterms where the contract specifies them.

## Reports and printing

Use Odoo list, search, saved filters, grouping, pivot, spreadsheet dashboards, native XLSX/CSV export and QWeb. Print only export-specific booking summaries and packing/container manifests from accepted source data. Do **not** recreate Purchase Orders, Sales Orders, inland trucking BOLs, carrier-issued bills of lading, warehouse inventory ledgers or invoice posting. Every PDF or export must have current, attributable source revisions and respect the selected audience.

## Phase 2 (not required for Phase 1)

Extend the same identities for freight-inclusive international selling and legitimate resale while on the water. Optional integrations: **FindTEU** for observed ocean container milestones, and **ACE AESDirect** for authorized EEI preparation/handoff and official ITN/exemption evidence. Neither is a second physical shipment owner; neither may be a hard dependency of Phase 1. Direct government filing is excluded until applicable certification and authorization are proven.

## Acceptance before claiming the module works

Installation on Odoo 19 Enterprise; exactly sourced booking/roll resolution; five containers from four POs on one booking; a 30-load SO fulfilled in separate shipments; PO issued before later booking; buyerless cargo without invented transactions; supplier-delivered FAS without fake drayage; correct distinct slot counts under mixed sourcing; no cross-company leakage; one authoritative document verification action; six dashboard/report drilldowns; and mail, state transitions, stock and accounting gated by their actual owners.

Current status: **design frozen at the business/ownership level; implementation, Enterprise registry, UI click-path, concurrency, security and full acceptance tests NOT_RUN.**

## Development starting points

Read the frozen operator design, the stable `BRS-EXP-*` rules and their acceptance registry, the source-owned Logistics BRS and supersession register, the native Documents interop contract, and the repository's current constitutional `INVARIANTS.md`. The proposed file tree is in `MODULE_DESIGN/PROPOSED_FILETREE.md` in the working design pack. Verify it against the latest repository source before creating files. No private customer documents or source fixtures belong in a public module tree.

Architecture reference: `cryptoxdog/IB-Odoo_19` Staging `04bd0594a7c9dcad53d9c45fc65276d76817c112` (inspected historical baseline, not proof of currentness).

## Developer implementation-readiness note (v2.5)

The business behavior above remains frozen and unchanged. For candidate model shapes, required existing-owner handoffs, the exact stop/go gates, and the all-120 acceptance mapping, read `../IMPLEMENTATION_READINESS_CONTRACT.md` and `../RULE_REALIZATION_MATRIX.csv` **from the working pack**. This README is not a standalone approved code contract. No addon implementation or Enterprise conformance is claimed.

## Cross-module implementation handoff (v2.6)

Before implementing any Export-to-Logistics, Transaction, Documents, Linda, native Stock or reporting integration, read `../../INTEROP/CROSS_MODULE_INTEGRATION_CONTRACTS.md`. The seven `EXP-IC-*` contracts are proposed source-owner acceptance criteria, not working methods, current Odoo schemas or authorization to change repository code. Preserve native source writers, never invent missing company/shipment/ISO identity or an Export mail/document verifier, and treat all `IC-T01..17` as NOT_RUN until tested on the installed Enterprise runtime.

## Technical design closure (v2.7, current)

Read `../TECHNICAL_CLOSURE_v2.7.md` and the derived `../TECHNICAL_CONTRACT_v2.7.json` **before writing any model or integration code**. The E3 `load_id` used as a candidate in v2.5 is not selected: E3 binds the Logistics-owned actual physical ISO journey J1, with its multiple source associations J2. E1-E4 fields, state transitions, owner-target signatures, migration gates and exact Enterprise proofs are fixed as a **working-pack selected design awaiting source-owner adoption**. This README describes operator workflow and UX, not installed classes or permission to implement. Do not copy private source examples into the public addon.

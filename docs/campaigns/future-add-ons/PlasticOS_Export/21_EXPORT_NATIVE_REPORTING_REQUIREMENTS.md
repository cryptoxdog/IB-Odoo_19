# Export reporting UX and data contract

**Decision:** convenient Odoo-native reporting is a first-class Phase 1 feature. No standalone reporting engine.

## 1. Booking form fields derived from the provided legacy ERP screenshot

Primary: booking number/date/contact, shipping line, forwarder, optional group/status, quantity and equipment type, current cargo cutoff, document cutoff, VGM cutoff, time zone, ERD, optional received-confirmation evidence, vessel/voyage, ETD/ETA, POL/POD, receipt and final-delivery places, optional feeder, origin/return terminals, commodity and contractual weight limits. Shipper/Order, freight and contract reference, budget expense and documentation tabs are **views of authoritative owners**. Unobserved or unspecified fields remain optional.

**Do not invent new duplicates:** Bill of Lading is document-backed, rates/costs remain Logistics/Accounting, containers and seals remain physical Logistics/Stock identities, stock weights native. As-built Odoo fields must be inspected before any new extension field is admitted.

**Deadline version control:** Cargo/gate cutoff, document cutoff, VGM cutoff, ERD and local timezone are distinct. Preserve originals, source extraction, authority, current-versus-proposed, timestamp and reasons for revisions.

## 2. Source container report (private design fixture)

- Excel source: `SOURCES/booking report.xlsx` / Sheet1. **372 data rows, 43 labeled columns** and 172 distinct booking identifiers. The 43 columns are mapped separately in `SOURCES/LEGACY_REPORT_43_COLUMN_MAPPING.csv`.
- For booking `6509024800`: exactly **five distinct container rows, four supplier POs, two suppliers, five source trade/worksheet identifiers and 201,300 lb** reported combined net. POs include 64014, 64036, 63999 and 63992. One booking is not equivalent to one PO, load, transaction, SO or customer.
- Screenshot booking header displays the same booking and five assigned 40HQ units; the container grid corroborates that multiple commercial transactions are grouped under one ocean reservation.
- The legacy source contains blank fields, `0` sentinels and optional UDF columns. The report must not promote these into verified physical measurements, AES results or completion states.

## 3. Native Reporting menu and saved views

- Export > **Bookings** (list/form/calendar by cutoff, saved favorites); Export > **Containers** (1 physical-container row, smart links, export selection), Export > **Reporting** (booking/PO/SO/status/weight pivots, trends and a native Odoo dashboard); Export > **Print/Download** (booking QWeb, confirmed shipping/packing summary and selected data Excel/CSV).
- High-value preconfigured filters: **Cargo Cutoff This Week**, **ERD This Week**, **Document Cutoff Due**, **VGM Cutoff Due**, **Missing Documents**, **Booking Rolled/Changed**, **Pending Terminal Acceptance**, **Buyer Unassigned**, **Shipment/Container Without Allocation**, **Mixed Suppliers Per Booking**, **Shipment In Transit**.
- Search keys: booking, physical container, seal, PO, SO, invoice, source worksheet/trade reference, B/L, carrier, vessel, voyage, POL/POD, supplier, customer when assigned, product/grade and operator.
- Sorting/filtering/grouping must respect current cross-company ACL, confidentiality and the active revision. User may save/share favorites under rights. Columns may be optional; no forced 43-column default screen.

## 4. Report grains and numerical correctness

- **Container grain:** one row per physical container and journey assignment, not multiplied by joining PO, SO or document lines. Show exact source weights (lbs, with optional metric tons), actual versus planned quantity, separate tare and verified VGM.
- **Booking grain:** one booking, current deadlines, planned capacity, actual linked containers, unique total net, mixed-source flags, document/terminal exceptions, drill-down.
- **Order grain:** native SO/PO, ordered quantity, completed shipment quantities, outstanding/overshipment evidence; buyer may be unassigned until late sale.
- **Finance grain:** approved actual margins only from native Accounting and approved trade economics; never use booking capacity or vendor scale ticket price as invoice truth.

## 5. Download and printable reports

- XLSX/CSV are extracted from the current authorized Odoo list/filter selections; current user, company, as-of/source and snapshot semantics documented. Use native exports and spreadsheet dashboards.
- QWeb booking reports preserve source/booking version and audience. Loading/packing list must derive from verified physical quantities, not reserved vessel slots. No generated report masquerades as carrier's original booking or marine B/L.
- The PDF should not expose buyer identity or pricing to drayage providers merely because an internal view contains the data.

## 6. Proof gates

- `BRS-EXP-13` and `BRS-EXP-14` acceptance cases cover booking form, source, revision, search, export, private audience, multi-owner cargo and numeric correctness.
- One 5-container mixed-PO booking, one 4-load supplier PO across weekly reservations, one 30-load customer SO, one buyer-unassigned load and a rolled/cancelled booking are mandatory tests.
- Read-only report parity: counts, identifiers, net weights and corresponding links must equal authoritative current Odoo facts; negative duplicate-join and misattributed source documents fail.
- Evidence of deployed Odoo Enterprise runtime, performance under realistic record volume and operator usability remains NOT_RUN.

## Odoo 19 source references

- Native search/group/favorites: https://www.odoo.com/documentation/19.0/applications/general/search.html
- Native pivot, graph and XLSX download: https://www.odoo.com/documentation/19.0/applications/general/reporting.html
- Native dashboards/spreadsheets: https://www.odoo.com/documentation/19.0/applications/productivity/dashboards.html


## 2026-10-28 constitutional candidate alignment

This is a reporting BRS/UX contract under proposed POS-INV-21 (independent cardinality) and POS-INV-22 (revision-bound current view), with POS-INV-05 (audience) and POS-INV-20 (proof before claim). Do not introduce a report warehouse or infer verified values from the legacy workbook. See `GOVERNANCE/INVARIANT_ALIGNMENT_AND_IRREDUCIBILITY.md`.

## Dashboard actionability / source drilldown (v2.3)

The Phase 1 Overview MUST summarize vital current information from each of the six defined reports and provide direct links to the exact filtered report/data and authorized source records. Six core reports are: Booking Space Availability; Booking Allocation / Container Manifest; Open PO / SO Fulfillment; Container Shipment Register; Cutoff & Booking Exceptions; Missing Export Documents. Optional Economics is separate. `EXPORT_BRS/BOOKING_CONTROL_CENTER_UX.md` owns the six-metric/report map. `BRS-EXP-14-R017/R021/R022` and candidate global `POS-INV-24` govern coverage, navigation, company filters, source timestamps, missing data, and non-duplicative aggregates. Native Odoo Dashboards / pivot/list/actions supply the interaction; no new analytics engine.

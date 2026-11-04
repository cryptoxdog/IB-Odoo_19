# BRS-EXP-14: Native Odoo reporting and operational intelligence views

**Scope:** A convenient search/list/pivot/export experience; no second reporting engine.

**Authority:** New operator-accepted product goals; precise technical implementation remains DESIGN pending repo owner admission.

**Acceptance:** Source-bound fixtures, no live runtime proof; all test outcomes NOT_RUN.

## Rules

### BRS-EXP-14-R001: Native Odoo reporting foundation only

**LOCKED · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The Export reporting component SHALL be built from Odoo 19 native list, search, favorite, group-by, pivot/graph, spreadsheet/export and QWeb report capabilities. Add only needed read-only joins/projections and views. No competing report engine, independent analytics store or user-specific report code copies.

- **Positive:** One saved Export Containers view provides filters, grouping and current-filter XLSX export using Odoo mechanisms.

- **Negative:** A custom query/reporting service duplicates Odoo native access control and creates a second calculation authority.

- **Related BRS:** BRS-EXP-01; BRS-EXP-06

- **Acceptance:** `AC-EXP-14-001` / NOT_RUN.

### BRS-EXP-14-R002: Container-grain master report

**LOCKED · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The canonical detailed container report SHALL yield one row per physical container/journey allocation, sourced from exact native records: container, seal, booking, supplier PO, buyer SO where assigned, original physical load, commodity, weight, carrier, vessel, voyage, origin/destination and evidence status. Multi-party bookings and missing buyers are supported without dummy identities.

- **Positive:** Booking 6509024800 returns five unique rows with POs 64014, 64036, 63999, 63992, 63999 and correct net weights.

- **Negative:** Joining orders multiplies container rows, hides an unassigned buyer, or aggregates five loads into one physical record.

- **Related BRS:** BRS-EXP-08; BRS-EXP-13-R005

- **Acceptance:** `AC-EXP-14-002` / NOT_RUN.

### BRS-EXP-14-R003: Booking-grain summary with drill-down

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The booking report SHALL show carrier, POL/POD, latest sourced deadlines and their time zones, equipment planned/assigned, vessel/voyage, ETD/ETA, number and summed weight of distinct containers, document completeness and exceptions. Booking summary and per-container report SHALL be separate grains with click-through to exact individual orders/loads.

- **Positive:** One booking shows 5 assigned containers, 4 distinct POs, 201,300 lb source-reported net and drill-down to each.

- **Negative:** A booking summary repeats cargo totals once per PO join or claims completed movement from a booking ETA.

- **Related BRS:** BRS-EXP-02; BRS-EXP-07; BRS-EXP-11

- **Acceptance:** `AC-EXP-14-003` / NOT_RUN.

### BRS-EXP-14-R004: Search, filters and stable saved views

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Provide search by Booking No., Container No., Seal, PO, SO, Source Worksheet/Trade identity, invoice/BOL where authorized, and filters for POL, POD, carrier, vessel, supplier, customer, grade, departments, ownership, status, deadlines and missing documents. Support saved Favorites and sharable role-scoped views via native Odoo.

- **Positive:** A user saves Unassigned Containers, At-Risk Cutoffs, Departing This Week and Missing Documentation, and reopens them without losing filters.

- **Negative:** A filter unexpectedly hides buyer-unassigned loads or leaks restricted commercial invoices to a carrier.

- **Related BRS:** BRS-EXP-06

- **Acceptance:** `AC-EXP-14-004` / NOT_RUN.

### BRS-EXP-14-R005: Convenient interactive list and export

**LOCKED · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The list SHALL support default useful columns, optional column visibility, sort, group, page, drill-through and export of user-selected filtered rows to native XLSX/CSV according to permissions. No forced PDF for operational spreadsheets; print-ready layout SHALL use QWeb when needed.

- **Positive:** The user filters booking 6509024800, sees 5 container rows and downloads matching Excel rows with the same identifiers.

- **Negative:** A download silently includes all companies, ignores applied filters or exports stale/old booking revisions as current.

- **Related BRS:** BRS-EXP-06; BRS-EXP-11

- **Acceptance:** `AC-EXP-14-005` / NOT_RUN.

### BRS-EXP-14-R006: Report column provenance and business-owner mapping

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The report schema SHALL explicitly map each required source column to an authoritative existing Odoo or PlasticOS owner. Missing sources SHALL appear as NOT_IMPLEMENTED/UNVERIFIED rather than fabricate a value; legacy labels are mapping hints, not permission for new duplicate fields.

- **Positive:** Source columns from 43-column workbook are classified by owner and must-have/optional/deferred status before implementing joins.

- **Negative:** Invoice No, source worksheet, VGM or shipping date is recomputed from unrelated dates or a second export ledger.

- **Related BRS:** BRS-EXP-01; BRS-EXP-09

- **Acceptance:** `AC-EXP-14-006` / NOT_RUN.

### BRS-EXP-14-R007: Date semantics, time zones and cutoff risk

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Reporting SHALL preserve document cutoff, VGM cutoff, gate cutoff, ERD, actual supplier shipping date, estimated/actual sailing and arrival separately, including time zone and source/revision. Show missed or approaching deadlines from current authoritative facts without rescheduling loads directly.

- **Positive:** A container shows pickup date, gate cutoff and ETD as distinct values and an applicable risk when gate cutoff approaches.

- **Negative:** A blank ETA is replaced with actual ship date or an ERD update silently changes a trucking appointment.

- **Related BRS:** BRS-EXP-10; BRS-EXP-11; BRS-EXP-13

- **Acceptance:** `AC-EXP-14-007` / NOT_RUN.

### BRS-EXP-14-R008: Weight, equipment tare, VGM and units

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The detailed report SHALL distinguish cargo net weight, supplier or scale weight provenance, number of units, equipment tare, and compliant VGM when actually verified; display lb and metric ton using a single explicit conversion policy. Preserve null and unknown rather than printing zero as fact. Do not make a raw gross/tare formula into certified VGM.

- **Positive:** For the first container show 40,200 lb net and leave missing VGM unverified, with metric-ton conversion labeled.

- **Negative:** System sums cargo and tare then asserts certified VGM or prints unknown VGM as 0.00 accepted.

- **Related BRS:** BRS-EXP-07; BRS-EXP-11

- **Acceptance:** `AC-EXP-14-008` / NOT_RUN.

### BRS-EXP-14-R009: Native pivots and useful operating metrics

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Provide native Odoo pivot/graph/dashboard measures for count of distinct physical containers, cargo weight by supplier/buyer/grade/month/port/steamship line, booking capacity-versus-allocated, unfulfilled PO/SO quantities, exceptions and document completeness. Financial measures must come from approved native accounting/transaction economics with stated recognition/actual-cost policy.

- **Positive:** Users can aggregate loads and verified net weight by carrier, customer, grade and month without duplicate booking-row sums.

- **Negative:** A pivot sums booking-level freight five times or markets preliminary margin as realized profit.

- **Related BRS:** BRS-EXP-08; BRS-EXP-06

- **Acceptance:** `AC-EXP-14-009` / NOT_RUN.

### BRS-EXP-14-R010: Audience-safe QWeb and source-linked revisions

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Reports SHALL support separate print-ready booking summary, shipment/packing list when supported by verified physical facts, and operational exceptions/QWeb PDFs. Report generation records the source revision/as-of time; actual external sending remains Linda and original retention remains Documents. Supplier/trucker/buyer/internal audiences SHALL have distinct permitted fields.

- **Positive:** Supplier booking copy prints the latest authorized deadline with no sales prices; internal copy may include relevant restricted columns.

- **Negative:** Old cutoff appears on a newly sent report or carrier sees customer pricing through a generic export.

- **Related BRS:** BRS-EXP-03; BRS-EXP-10

- **Acceptance:** `AC-EXP-14-010` / NOT_RUN.

### BRS-EXP-14-R011: Source workbook as conformance fixture, not production authority

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The attached booking report.xlsx (372 data rows, 43 column headings) SHALL serve as a private comparison fixture to design semantics and test exports. Historical legacy report values do not become a new system of record; migrated values require validated exact identity and allowed ownership.

- **Positive:** All 43 headings are inventoried, booking grouping is correct and rows with missing POD, ETD or buyer display explicit missing/unknown status.

- **Negative:** Importing a workbook directly overwrites native Odoo booking, Stock, Invoice or document records without reconciliation.

- **Related BRS:** BRS-EXP-09; BRS-EXP-11

- **Acceptance:** `AC-EXP-14-011` / NOT_RUN.

### BRS-EXP-14-R012: Access control and reproducible report scope

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** All reporting respects native company/tenant access, row rules, commercial confidentiality and customer/supplier/carrier audiences. Saved filters, download scope, calculated quantities, source timestamp and report user are reproducible. Use authorized Odoo actions; no raw unrestricted SQL reporting endpoint.

- **Positive:** Two users with different company rights see only their permitted container and financial columns under the same saved filter.

- **Negative:** A downloaded workbook bypasses row rules or an exported supplier booking includes profit margins.

- **Related BRS:** BRS-EXP-01; BRS-EXP-06

- **Acceptance:** `AC-EXP-14-012` / NOT_RUN.

### BRS-EXP-14-R013: Phase 2 provider evidence is additive

**DESIGN · P2 · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** In Phase 2, optional FindTEU observations and AESDirect filing evidence may appear as separately labeled status columns and filters. Missing integration, a late provider update or unverified filing response shall never suppress a core report or rewrite native shipment/filing authority.

- **Positive:** FindTEU ETA and an accepted ITN appear with their sources alongside existing booking detail if authorized.

- **Negative:** An unauthenticated third-party milestone is shown as a verified official filing or Phase 1 reporting breaks without provider credentials.

- **Related BRS:** BRS-EXP-12

- **Acceptance:** `AC-EXP-14-013` / NOT_RUN.

### BRS-EXP-14-R014: Booking capacity is equipment-specific and source-confirmed

**DESIGN · P1 · owner: `plasticos_export` (projection), with native Odoo and existing domain owners authoritative for source facts.** The booking availability workbench SHALL show, per current company-scoped carrier reservation AND equipment type, requested capacity, confirmed capacity, committed booking-slot allocations, executed/loaded containers, remaining assignable capacity and source validity. Confirmed capacity is not derived from a sales order or empty field. Only active source-confirmed capacity is eligible; cancelled, expired, proposed or rolled bookings are labelled separately. An operational hold, if genuinely authorized, is separately identified and reduces assignable capacity; a tentative candidate does not. A shipped container does not reopen a slot without explicit carrier evidence.

- **Positive:** Confirmed 5 x 40HC booking with 5 distinct committed slots shows confirmed=5, allocated=5, available=0 even if some containers have not reached the terminal.

- **Negative:** A stale rolled capacity, provisional AI interpretation, repeated purchase-order line or previously loaded container increases available slots, or a 40STD slot is counted as 40HC.

- **Related BRS:** BRS-EXP-02; BRS-EXP-07; BRS-EXP-11; BRS-EXP-14-R003

- **Acceptance:** `AC-EXP-14-014` / NOT_RUN.

### BRS-EXP-14-R015: One booking slot can serve multiple correctly attributed cargo lines

**DESIGN · P1 · owner: `plasticos_export` (projection), with native Odoo and existing domain owners authoritative for source facts.** Booking-space allocation SHALL identify an exact distinct equipment slot or legitimate planned shipment assignment, link it to eligible actual load/transaction or approved native order lines as applicable, and preserve zero or more related supplier PO and customer SO lines without multiplying the slot. The physical ISO container number may be unknown at planning time; later evidence binds the real number to the same slot. Export owns booking-slot assignment only, never commercial ordered/reserved/delivered quantity or actual stock movement. No fictitious load is created for a tentative allocation.

- **Positive:** One five-slot booking binds five container journeys across four POs, with one PO spanning two containers; an additional mixed-grade container with two PO lines still consumes one slot.

- **Negative:** An order-line join makes five slots become six, or assignment creates a synthetic delivery, completed load, buyer or container number.

- **Related BRS:** BRS-EXP-08; BRS-EXP-14-R002; POS-INV-21

- **Acceptance:** `AC-EXP-14-015` / NOT_RUN.

### BRS-EXP-14-R016: Explicit allocation commands respect capacity and revision

**DESIGN · P1 · owner: `plasticos_export` (projection), with native Odoo and existing domain owners authoritative for source facts.** Assign, release, substitute, split or reallocate booking space SHALL be an authorized explicit booking operation with company, equipment, responsible source, target slot or movement, revision and audit trail. Concurrent assignments must not overcommit capacity. If a booking revision lowers quantity below committed slots or changes equipment, show the impacted allocations and block unsafe new commitment; never silently delete an actual container, undo physical delivery, rebook trucks, reissue communications or pretend a released slot exists without evidence.

- **Positive:** A confirmed 5-slot booking revised down to 4 with 5 assigned shows overallocated=1 and affected allocations; the correct owner reconciles without losing prior evidence.

- **Negative:** Two users allocate the same remaining slot, a booking roll auto-dispatches new trucks, or stale cutoffs remain printed as current.

- **Related BRS:** BRS-EXP-11; BRS-EXP-10; POS-INV-22

- **Acceptance:** `AC-EXP-14-016` / NOT_RUN.

### BRS-EXP-14-R017: Native-first Bookings control center with actionable drilldowns

**DESIGN · P1 · owner: `plasticos_export`.** The Export Overview SHALL be the native Odoo landing dashboard and summary/navigation surface for **all six Phase 1 core reports** named in BRS-EXP-14-R021: Booking Space Availability; Booking Allocation / Container Manifest; Open PO / SO Fulfillment; Container Shipment Register; Cutoff & Booking Exceptions; and Missing Export Documents. It SHALL present at least one genuinely informative source-owned, grain-correct current metric, exception or compact visualization per report, with a clearly identifiable direct link to that exact report. Each card/chart/table element SHALL drill to the contributing filtered records under the user’s company/role access, with per-metric source and as-of information and a path from report to exact booking, slot, container, commercial order or document evidence. Summary is not a replacement for the six reports. Prefer native Odoo Spreadsheet Dashboard, list/pivot/graph and native actions, with a searchable-list fallback if the Dashboard app is unavailable. No separate reporting engine or new writer.

- **Positive:** An authorized user sees six meaningful previews, clicks Available 40HC to reach the filtered Booking Space Availability report and its exact current booking records, then drills into a booking; clicks Missing Documents and reaches its operation-specific evidence obligations, not a generic document list.

- **Negative:** One of the six reports has no dashboard summary or direct link; an at-risk card opens all bookings without carrying its active filters; a restricted user sees supplier commercial data; or a chart changes source-grain counts by joining PO/document lines.

- **Related BRS:** BRS-EXP-14-R001,R003,R009,R012,R021,R022; POS-INV-02,05,20,24

- **Acceptance:** `AC-EXP-14-017` / NOT_RUN.

### BRS-EXP-14-R018: Available bookings and unbooked demand remain distinct

**DESIGN · P1 · owner: `plasticos_export` (projection), with native Odoo and existing domain owners authoritative for source facts.** Provide saved native lists for Available Bookings, Fully Allocated, Awaiting Carrier Confirmation, Rolled/Cancelled, Unallocated Eligible Cargo, Ready without Booking, Buyer Unassigned, and Booking with Multiple Suppliers. Availability is carrier capacity; unallocated demand is a distinct eligible physical/commercial need. Bookings with no current PO/load remain visible. Buyer-unassigned cargo must remain visible rather than being rejected or silently assigned to an arbitrary SO.

- **Positive:** A four-load supplier PO scheduled weekly appears as four separately assessable movements; the original PO remains one and available booking capacity may exist even before a supplier is ready.

- **Negative:** An empty booking is hidden because it has no container, or a buyerless load vanishes from matching views, or an SO balance is mistaken for ocean slots.

- **Related BRS:** BRS-EXP-08; BRS-EXP-14-R004; POS-INV-23

- **Acceptance:** `AC-EXP-14-018` / NOT_RUN.

### BRS-EXP-14-R019: Deadline and allocation risk view without second dispatch authority

**DESIGN · P1 · owner: `plasticos_export` (projection), with native Odoo and existing domain owners authoritative for source facts.** Provide a booking-focused calendar and saved views for ERD, cargo cutoff, documentation cutoff, VGM cutoff, ETD/ETA, impending release and amendments, preserving source revision/time zone. Show whether allocations and supplier readiness permit a feasible move based on Logistics owner facts. Export SHALL NOT reschedule, select carriers, send messages, or declare gate-in; user actions route to the authoritative Logistics/Linda commands or native Activities.

- **Positive:** A cargo cutoff revision flags the two affected planned container movements and links to their Logistics schedule and packet freshness evidence.

- **Negative:** Changed ERD automatically changes approved pickup, a proposed AI cutoff silently overrides the current authorized one, or terminal arrival is presented as accepted gate-in.

- **Related BRS:** BRS-EXP-10; BRS-EXP-11; BRS-EXP-14-R007

- **Acceptance:** `AC-EXP-14-019` / NOT_RUN.

### BRS-EXP-14-R020: Per-booking document readiness is read-only and attributable

**DESIGN · P1 · owner: `plasticos_export` (projection), with native Odoo and existing domain owners authoritative for source facts.** The booking and container workspaces SHALL display only operation-specific document requirements, verified/current evidence, missing items, superseded source revisions, supplier loading photos and actual proof of terminal acceptance from the Documents/Logistics authorities. A source booking notice and generated booking summary must be visibly distinguished. Native Activities present internal exceptions; Linda owns any external chase or outbound send.

- **Positive:** A user opens a booked container and sees exact PO, current carrier confirmation, seal photo and scale ticket with distinct verification states and a missing gate receipt.

- **Negative:** An uploaded supplier statement marks ocean sailing completed, a generated PDF impersonates carrier confirmation, or Export writes a new verified flag.

- **Related BRS:** BRS-EXP-03; BRS-EXP-09; BRS-EXP-11; POS-INV-06; POS-INV-07

- **Acceptance:** `AC-EXP-14-020` / NOT_RUN.

### BRS-EXP-14-R021: Minimal report suite with explicit grain and replayable filters

**DESIGN · P1 · owner: `plasticos_export`.** The six required Phase 1 reports SHALL be (1) Booking Space Availability, (2) Booking Allocation / Container Manifest, (3) Open Supplier PO / Customer SO Fulfillment, (4) Container Shipment Register, (5) Cutoff & Booking Exceptions, and (6) Missing Export Documents. Each SHALL have a stable Odoo list/pivot/graph/spreadsheet route and grain-correct report scope so the Overview can summarize and open the exact contributing rows. Export Economics is an optional separate authorized report when Accounting provides accepted figures; it is not the sixth mandatory report. QWeb is for audience-safe printable booking/packing/exception snapshots. Counts use booking-slot, container-journey, order-line, amendment or evidence-obligation grains as appropriate, with source-authenticated units, weights, company permissions, revision and as-of. No duplicate report ledger, second scheduler or mailer.

- **Positive:** Booking 6509024800 shows five actual containers, four distinct supplier POs, and 201,300 lb source-reported net without duplicate cargo rows; each of the six reports is accessible directly from its dashboard summary and the filtered detail can be exported under native Odoo rights.

- **Negative:** The dashboard substitutes an optional economics report for Missing Documents, shows a generic page instead of the six report views, double-counts joined loads, or implies missing verified evidence from mere attachment presence.

- **Related BRS:** BRS-EXP-14-R002..R012,R017,R022; BRS-EXP-08; BRS-EXP-11; POS-INV-24

- **Acceptance:** `AC-EXP-14-021` / NOT_RUN.

### BRS-EXP-14-R022: Six-report dashboard coverage and exact filter-preserving navigation

**DESIGN · P1 · owner: `plasticos_export`.** Each of the six Phase 1 dashboard sections SHALL bind to the same authoritative, appropriately filtered source population as its linked report. The required dashboard-to-report contract is: availability -> current confirmed/allocated/free slots by equipment; allocations -> committed slots and overallocations; fulfillment -> outstanding PO/SO line quantity and ready-but-unbooked demand with units; shipment register -> distinct loaded/in-transit/terminal-accepted containers; deadline exceptions -> imminent cutoffs, rolls and stale booking revisions; missing documents -> exact overdue or missing current verified evidence obligations by owner. Clicking a tile/measure SHALL open its matching report with compatible company, operator rights, period, equipment, booking, state, source-revision and exception filters; report rows SHALL then open the correctly authorized underlying business record/evidence. If native Odoo action/filter propagation cannot preserve a chosen cross-source scope, provide the minimum authorized action binding, never a custom dashboard engine. Label when-as-of, stale/pending/unknown, report currentness and privilege-limited omissions. Empty or inaccessible populations SHALL not masquerade as an accepted zero.

- **Positive:** A company-limited user filters Overview to 40HC, port and cutoff week; all six cards show authoritative values for that scope, the dashboard opens each corresponding prefiltered report, the detail opens an exact load/booking/PO/document obligation, and counts reconcile at one declared grain or identify their changed-as-of time.

- **Negative:** One of six cards is inert, repeats unrelated metrics, resets the report scope to all companies/dates, reveals a restricted count, hides an AI-proposed-but-unverified booking as confirmed, shows an unknown document result as zero, or counts one five-container booking as five open ocean bookings.

- **Related BRS:** BRS-EXP-14-R002..R012,R014..R021; BRS-EXP-06; POS-INV-02,04,05,20,21,22,24

- **Acceptance:** `AC-EXP-14-022` / NOT_RUN.


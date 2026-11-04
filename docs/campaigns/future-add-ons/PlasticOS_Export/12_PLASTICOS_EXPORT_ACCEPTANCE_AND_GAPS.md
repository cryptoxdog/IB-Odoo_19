# `plasticos_export`: thin-phase acceptance and proof gaps

**Status:** planning acceptance scenarios, all **NOT_RUN**; not a programming contract, not a verified system. Phase 1 acceptance is a prerequisite for claiming that phase complete, not a prerequisite for discussing Phase 2.

## Phase 1: commercially useful, minimal Odoo workflow

| ID | Positive witness | Negative control |
|---|---|---|
| EX-P1-01 | Operator selects **FOB pickup** and records buyer/carrier pickup against an existing real Odoo order and load | Workflow forces seller-arranged inland freight or changes formal Incoterm without contract |
| EX-P1-02 | Operator selects **FAS delivered port/rail**, stores agreed inland freight and destination and records factual terminal/rail handoff | App marks vessel-loaded or assumes official FAS risk-transfer solely from terminal gate-in |
| EX-P1-03 | Booking No., Steamship Line, POL, POD, Cut Off, ERD are captured from a source confirmation and remain searchable | UI confuses Booking No. with container number or silently rewrites date-only cutoff to midnight |
| EX-P1-04 | ERD and cargo Cut Off revisions retain old and current source, zone, precision and effective event; dashboard displays exception | Later stale email silently resets the effective window or combines SI and cargo cutoff |
| EX-P1-05 | Inbound carrier booking PDF/email is preserved once through permitted native intake and exactly linked to live booking/load/order | Fuzzy 'latest booking' assignment, duplicate authoritative file or external Documents sharing |
| EX-P1-06 | Missing, wrong-party, or superseded terminal receipt remains visible as an unverified exception with one native internal Activity | Mere upload or AI classification marks compliant and triggers external dispatch |
| EX-P1-07 | User generates correct current booking/dispatch/packing report from native data and uses existing authorized Mail pathway for outward document | New report duplicates weight fields; export addon is second Odoo Mail sender; supplier sees buyer-confidential data |
| EX-P1-08 | QR scan during actual package loading maps to existing native Odoo stock/container/package identity | New package ledger, inferred delivered state, automatic AP/AR adjustment or fabricated certified weight |
| EX-P1-09 | Native Enterprise Documents feature is proven and enabled before specific app dependency, or user-facing capability degrades through approved native attachments safely | Application crashes or fabricates installed Enterprise Documents capability |
| EX-P1-10 | Minimal model-surface review lists each new field, existing owner checked, concrete unmet native need, and no duplicated scheduler/state machine | `plasticos_export` replicates `plasticos_logistics`, `plasticos_documents` or stock functionality |

## Phase 2: international selling overlay, no rebuilding Phase 1

| ID | Positive witness | Negative control |
|---|---|---|
| EX-P2-01 | Ocean freight-inclusive CFR/CNF or CIF scenario reuses same booking, container, order, package and file identities | Existing Phase 1 data must be migrated to wholly separate international ERP models |
| EX-P2-02 | Authoritative issued ocean B/L, shipping instructions, SI cutoff, VGM, international commercial invoice, applicable export filing proof are tracked in native Docs/typed evidence | System generates a carrier-issued bill of lading or claims VGM compliance from summed package weights |
| EX-P2-03 | Exporter, booking party, freight payer, customs filer, buyer and insurer are explicitly attributable from actual contracts | An industry FAS/FOB label silently sets legal party duties or posts insurance costs |
| EX-P2-04 | Approvals/document release and linked accounting occur via authorized existing owners | Document attachment automatically posts journal entry, files AES, or collects payment |
| EX-P2-05 | A missed cutoff or rolled sailing recomputes documentary obligations and notifies the correct responsible operator using native approved Activity | Duplicated Linda reminders or independent export timer races existing cron |

## Proof ledger and economical next evidence

**Observed source coordinates, not runtime validation:** PlasticOS `Staging` SHA `04bd0594a7c9dcad53d9c45fc65276d76817c112`; current manifests declare native `stock`, `purchase`, `sale_management`, `account`, `barcodes`, documents/logistics; transaction line `lot_no`, `container_no`, `seal_no`; logistics has BOL and freight/dispatch records. No `plasticos_export` addon, ocean booking UI or live installation has been proven here. Odoo 19 native availability and exact installed Enterprise feature gates must be checked before claiming any operational result.

**Smallest discriminating Phase 1 proof:** take one FAS-priced order, link one buyer/forwarder booking with all six fields, ingest its original booking PDF/email, create a native Activity for a missing gate receipt, generate a current booking/dispatch report via native QWeb, record actual port/rail delivery evidence, then show a single truth across existing SO/PO, Linda load, stock, Docs and Mail with no duplicate outbound send.

**Counterexample:** a container is booked and QR scanned, but cutoff changes and terminal rejects the return. The correct system retains both cutoff versions, distinguishes scan/dispatch from terminal accepted handoff, does not alter inventory/accounting without authorized action, and preserves current unverified proof/next action.

## Source and authority constraints

- Attached BRS ZIP: `PlasticOS_Native_First_BRS_v1.0.0_2026-10-25(2).zip`, SHA-256 in `MANIFEST.json`; source class `FROZEN_WORKING_SPEC__NOT_YET_REPO_ADMITTED` with acceptance `NOT_RUN`. Not incorporated or changed.
- Prior expansion ZIP: `RecycleOS_Operational_Expansion_v1.1.0.zip`, SHA-256 in `MANIFEST.json`; its non-manifest members are all preserved byte-for-byte here.
- No formal admission, current installed EE proof, live trade-practice legal adjudication, runtime tests, or customer verification was conducted. All acceptance rows **NOT_RUN**.
- Only specific missing fields/links with demonstrable value should become code. This pack does not authorize a PR or module build.

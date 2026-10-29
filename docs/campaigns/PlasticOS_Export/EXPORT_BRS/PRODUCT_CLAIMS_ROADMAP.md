# RecycleOS eight product claims: roadmap and proof gates

**Operator decision:** All eight claims are committed product acceptance objectives. This document is not a statement that they have been implemented or demonstrated.
**Effective:** 2026-10-28 | **Mode:** Working, not repository-admitted | **Tests:** NOT_RUN

## Evidence-based scope

| Claim | Owner | P1 proof | P2 proof |
|---|---|---|---|
| `CLAIM-01` Automates the trading cycle | Native Odoo Sale/Purchase/Stock/Accounting + PlasticOS transaction | bounded functional proof | expanded international proof |
| `CLAIM-02` Organizes export operations | plasticos_export (cross-owner contextual projection) | booking + container view | ocean/filing context |
| `CLAIM-03` Improves productivity | Native Odoo activities, views and Linda; narrow Export UI | bounded functional proof | expanded international proof |
| `CLAIM-04` Minimizes trading risk | Native Finance/Accounting and approved risk policies + Export alerts | cutoffs, docs, freight | credit/FX when verified |
| `CLAIM-05` Generates export documentation | Native Odoo QWeb, Sales/Purchase, Documents and Export report layouts | booking and packing reports | international document suite |
| `CLAIM-06` Provides business insights | Native Odoo reporting, pivot, dashboards, approved Accounting | container and order pivots | approved financial metrics |
| `CLAIM-07` Automates logistics workflows | plasticos_logistics and Linda | port/rail Linda handoff | FindTEU milestone ingestion |
| `CLAIM-08` Automates document workflows with AI | Native Odoo AI Documents + plasticos_documents + authorized business owners | booking / scale ticket AI | more ocean documents |

## Governing release ladder (no hidden approvals)

1. **R0 | Native-first convergence.** Audit exact Odoo Staging, Enterprise Documents/AI, transaction-load cardinality, PO partial delivery and commercial ownership. Prove no duplicate writers before scope admission.
2. **R1 | Phase 1 export fundamentals.** Booking record and revisions; native-first booking form; 20/40/45-foot equipment; supplier-PO to many physical loads and booking to many containers/POs; verified document links; native report menus and filterable list; accurate print-ready booking report.
3. **R2 | Phase 1 automated operations.** AI booking and completion-email extraction with exact match and guarded state actions; Linda supplier/carrier packets and readiness; cutoff/ERD exceptions; actual source-linked weight, photo and gate evidence; core order and container analytical reports.
4. **R3 | Phase 2 international selling.** Ocean freight responsibility, international documentation and buyer-in-transit flows; FindTEU optional milestone adapter; AESDirect supported authorized filing preparation, ITN/exemption evidence and amendments; no uncertified direct filing.
5. **R4 | Commercial claim validation.** Independent end-to-end tests for each of eight claims in representative tenant data, security, repeatability, partial shipments, report exports and operator UX. Marketing wording is limited to claims with recorded PASS proof.

## Cross-claim acceptance and negative controls

### CLAIM-01: Automates the trading cycle
- **Owner:** Native Odoo Sale/Purchase/Stock/Accounting + PlasticOS transaction
- **Release coverage:** P1 foundational; P2 complete
- **Positive proof:** One SO for 30 loads; one supplier PO for 4 partial fulfillments; progressive shipment, invoicing and settlement without invented orders; allow buyer unassigned until legally sold
- **Negative control:** Duplicate orders, invoice posting on AI-generated events, or missing unsold-on-water scenario
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-02: Organizes export operations
- **Owner:** plasticos_export (cross-owner contextual projection)
- **Release coverage:** P1 core; P2 expanded
- **Positive proof:** Booking, 5 physical containers from 4 POs, source-revision deadlines, linked verified files, native sales and purchase details visible in one form
- **Negative control:** A second quantity, freight, financial or document engine is built
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-03: Improves productivity
- **Owner:** Native Odoo activities, views and Linda; narrow Export UI
- **Release coverage:** P1 core; P2 optimize
- **Positive proof:** Role-specific saved reports and one-touch navigation; measured drop in repeated booking entry, duplicate mail and manual document searching
- **Negative control:** Unmeasured productivity claim or another chase scheduler
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-04: Minimizes trading risk
- **Owner:** Native Finance/Accounting and approved risk policies + Export alerts
- **Release coverage:** P1 key operating risks; P2 broader exposure
- **Positive proof:** Verified calculation/exceptions for negative margin, overbooked weights, missed cutoff, missing documents, credit and FX exposure where implemented
- **Negative control:** Claiming entire risk portfolio supported from a decorative dashboard or raw estimates
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-05: Generates export documentation
- **Owner:** Native Odoo QWeb, Sales/Purchase, Documents and Export report layouts
- **Release coverage:** P1 booking/packing/source documents; P2 full international documents
- **Positive proof:** Create audience-safe and source-versioned booking summary, packing report where factual, native commercial invoice, shipping instructions and applicable compliant docs
- **Negative control:** Pretending generated summary is official carrier B/L or certificate or ignoring revisions
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-06: Provides business insights
- **Owner:** Native Odoo reporting, pivot, dashboards, approved Accounting
- **Release coverage:** P1 operational metrics; P2 full realized economics
- **Positive proof:** Drill from pivot/booking to 5 distinct containers and report 201,300 lb sourced net; gross profit by order/shipment only with approved actual cost rules
- **Negative control:** Double counted container weights or uncontrolled definition of realized margin
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-07: Automates logistics workflows
- **Owner:** plasticos_logistics and Linda
- **Release coverage:** P1 bounded supplier/port/rail flows; P2 ocean milestone visibility
- **Positive proof:** Readiness, freight responsibility, dispatch packets, accepted carrier commitment, terminal delivery and exception follow-up flow without duplicate send
- **Negative control:** Export directly dispatches a truck, supplier-delivered FAS assumed to have hired drayage
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

### CLAIM-08: Automates document workflows with AI
- **Owner:** Native Odoo AI Documents + plasticos_documents + authorized business owners
- **Release coverage:** P1 core extraction/verification; P2 international doc extension
- **Positive proof:** AI ingests booking revisions, matches exact PO/load/container, handles rolling cutoffs, links scale ticket and books candidates, approved actions update state
- **Negative control:** Partner-only guessing, unsourced state changes, or pricing/weights modified by booking text
- **Current status:** SPECIFIED / NOT_RUN; not marketing-approved.

## Performance measurement required before marketing
- Measure manual booking-field corrections and percent correctly auto-matched; AI precision/coverage cannot be asserted without observed results.
- Measure reporting latency and agreement with Odoo authoritative records, including 372-row legacy fixture and duplicate-join negative controls.
- Measure quote/dispatch cycle time, date-change rework, inaccurate-document incidents, and reporting adoption with actual baseline and after-state.
- Measure trade profitability against native posted AP/AR and actual freight, not estimated margins alone.

## Structural ownership and exclusions
- These are **cross-product** claims, not eight new business authorities in `plasticos_export`.
- Export owns its booking context and report layouts; Documents verifies; native Documents stores originals; Linda handles external communications; native Odoo owns finance, stock, sale and purchase.
- No new dashboard/warehouse/BI engine is implied by these claims. Use Odoo search/favorites/pivot/graph/spreadsheet; add only proven missing links and views.
- Freightview is not a committed Phase 2 integration; FindTEU and AESDirect remain the two optional planned providers.

## Sources
- Operator-approved eight-claim matrix, 2026-10-28.
- Current-screen samples: booking form screenshot, container report screenshot and private legacy booking report.xlsx.
- Odoo 19 docs: https://www.odoo.com/documentation/19.0/applications/general/search.html ; https://www.odoo.com/documentation/19.0/applications/general/reporting.html ; https://www.odoo.com/documentation/19.0/applications/productivity/dashboards.html

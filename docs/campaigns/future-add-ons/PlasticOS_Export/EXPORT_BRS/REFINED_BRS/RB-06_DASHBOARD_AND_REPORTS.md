# Refined BRS reading brief RB-06: Operational reports and dashboards

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** The Dashboard is a projection: a fast summary and reliable jump to the exact business facts, not an alternative accounting or dispatch engine.

## 1. Six native reports

Booking Space Availability; Booking Allocation/Container Manifest; Open PO/SO Fulfillment; Container Shipment Register; Cutoff & Booking Exceptions; Missing Export Documents.

**Canonical rule pointers:** BRS-EXP-14-R001,R002,R003,R009,R021. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Navigation

Every dashboard section shows relevant vital source data and opens the exact scoped report and individual supporting record, retaining filters, permissions and source status.

**Canonical rule pointers:** BRS-EXP-14-R017,R022. Follow each source rule and its paired acceptance case for exact requirements.

## 3. Practical operator UX

List/search/favorite/column selection/pivot/Excel/QWeb work over native data; saved views for available space, booked but unused capacity, unbooked readiness, deadlines and missing proof.

**Canonical rule pointers:** BRS-EXP-04-R005; 14-R004,R005,R010,R018,R019,R020. Follow each source rule and its paired acceptance case for exact requirements.

## 4. Reconciliation

Distinct container counts and weights are not duplicated across mixed POs; net, tare and VGM remain separate; timestamps/zones and unavailable data are not silently flattened into success.

**Canonical rule pointers:** BRS-EXP-14-R006,R007,R008,R011,R012. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-04-R005` (P1) - Native documents and simple views first. Acceptance: `AC-EXP-04-005`.
- `BRS-EXP-14-R001` (BOTH) - Native Odoo reporting foundation only. Acceptance: `AC-EXP-14-001`.
- `BRS-EXP-14-R002` (BOTH) - Container-grain master report. Acceptance: `AC-EXP-14-002`.
- `BRS-EXP-14-R003` (BOTH) - Booking-grain summary with drill-down. Acceptance: `AC-EXP-14-003`.
- `BRS-EXP-14-R004` (BOTH) - Search, filters and stable saved views. Acceptance: `AC-EXP-14-004`.
- `BRS-EXP-14-R005` (BOTH) - Convenient interactive list and export. Acceptance: `AC-EXP-14-005`.
- `BRS-EXP-14-R006` (BOTH) - Report column provenance and business-owner mapping. Acceptance: `AC-EXP-14-006`.
- `BRS-EXP-14-R007` (BOTH) - Date semantics, time zones and cutoff risk. Acceptance: `AC-EXP-14-007`.
- `BRS-EXP-14-R008` (BOTH) - Weight, equipment tare, VGM and units. Acceptance: `AC-EXP-14-008`.
- `BRS-EXP-14-R009` (BOTH) - Native pivots and useful operating metrics. Acceptance: `AC-EXP-14-009`.
- `BRS-EXP-14-R010` (BOTH) - Audience-safe QWeb and source-linked revisions. Acceptance: `AC-EXP-14-010`.
- `BRS-EXP-14-R011` (BOTH) - Source workbook as conformance fixture, not production authority. Acceptance: `AC-EXP-14-011`.
- `BRS-EXP-14-R012` (BOTH) - Access control and reproducible report scope. Acceptance: `AC-EXP-14-012`.
- `BRS-EXP-14-R017` (P1) - Native-first Bookings control center with actionable drilldowns. Acceptance: `AC-EXP-14-017`.
- `BRS-EXP-14-R019` (P1) - Deadline and allocation risk view without second dispatch authority. Acceptance: `AC-EXP-14-019`.
- `BRS-EXP-14-R020` (P1) - Per-booking document readiness is read-only and attributable. Acceptance: `AC-EXP-14-020`.
- `BRS-EXP-14-R021` (P1) - Minimal report suite with explicit grain and replayable filters. Acceptance: `AC-EXP-14-021`.
- `BRS-EXP-14-R022` (P1) - Six-report dashboard coverage and exact filter-preserving navigation. Acceptance: `AC-EXP-14-022`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.

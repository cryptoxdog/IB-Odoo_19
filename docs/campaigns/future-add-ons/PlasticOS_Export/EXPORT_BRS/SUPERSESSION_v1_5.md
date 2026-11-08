# v1.5.0 additive scope and supersession

Operator decision (2026-10-28): commit all eight RecycleOS capability claims as **proof targets**, and a convenient native-first export reporting experience including the legacy legacy ERP booking form fields and container report. This is a BRS/roadmap change only; no code, repo, deployments or marketing claim certification authorized.

## Added (no prior rule removed)
- `BRS-EXP-13-R001..R010`: booking form fields including POD, separate cutoff types and time zone, carrier/vessel/voyage, physical/terminal places, commercial reference and AI reconciliation.
- `BRS-EXP-14-R001..R013`: 1-container-per-row export report, booking summary, saved filters, XLSX/CSV, QWeb PDF, source fields, pivots, ACL, audit, source truth and Phase 2 annotations.
- `PRODUCT_CLAIMS_ROADMAP.md` and `PRODUCT_CLAIM_ACCEPTANCE.json`: 8 cross-module product claims with release ladder and test gates; **none represent implemented or verified features yet**.
- `EXPORT_REPORTING_UX_AND_SCHEMA.md`, `SOURCES/LEGACY_REPORT_43_COLUMN_MAPPING.csv` and three private reference files used in the comparison.

## New important source findings
- Workbook has 372 populated container rows and 43 source field headings, representing 172 booking numbers.
- Booking 6509024800 has five distinct containers from four supplier POs (64014, 64036, 63999, 63992) and 201,300 lb of reported net cargo. This supplements the earlier source case: **a booking may consolidate multiple supplier transactions**.
- Prior PO 64014 is a five-container supplier commitment but only one of its physical loads appears under this observed booking; do not equate the five booking containers with five loads of PO 64014.
- Native Odoo lists/favorites/pivots/spreadsheets/reports own reporting infrastructure. Export may add report projections and QWeb layouts only.

## Preservation and limitations
- The existing 88 Export BRS rules and existing acceptance cases remain unmodified. Only registry/cases/README and source notes are updated, with two new chapters (23 new rules) and eight-claim roadmap added.
- Existing Logistics, native Documents, PlasticOS Documents, Accounting and native Stock authorities are unchanged.
- Provider integration plan stays: FindTEU tracking and AESDirect authorized filing support in Phase 2. Freightview excluded from this commitment.
- New rule cases are NOT_RUN; independent correctness, code readiness and operator workflow are unproven. Any source-site-specific fields remain subject to downstream owner proof.

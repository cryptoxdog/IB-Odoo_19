# Version 2.3: action-oriented, source-traceable dashboards

**Operator directive:** "The dashboard should link to each of those 6 and pull the most vital data from them and present it in the dashboard so user can drill down easily for details as needed (invariant for all dashboards)."

**Frozen architecture stays frozen.** No new business engine, stored analytics database, ERP transaction owner or document/mail writer. This is a **system-wide UX/data-traceability invariant candidate** and a bounded Export reporting refinement.

## Changes

1. Add cross-cutting candidate `POS-INV-24` to v3.2 DRAFT, preserving all pre-existing POS-INV-01..23 and BAN001 wording; current constitutional repository v2.2.0 is unchanged.
2. Align Export `BRS-EXP-14-R017` and `R021` with the six already agreed reports; add focused `R022` for meaningful dashboard previews and exact, filter-preserving, rights-preserving links and drilldown.
3. Amend `BOOKING_CONTROL_CENTER_UX.md` with a source-owned coverage matrix and report routes. Every dashboard component must take user to a **specific matched population** and exact underlying record, not just the generic Reports menu.
4. Record new negative controls for multi-source aggregation, stale/unknown status, private-company access and data changes between dashboard and detail.

**Acceptance:** 120 Export BRS cases, each NOT_RUN. All earlier frozen architecture choices remain in `EXPORT_BRS/CONVERGENCE/OPERATOR_DESIGN_FREEZE.md`. This packaging does not authorize Odoo implementation, production mail or constitutional adoption.

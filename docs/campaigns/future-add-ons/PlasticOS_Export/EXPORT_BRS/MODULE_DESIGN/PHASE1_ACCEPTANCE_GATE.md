# Phase 1 readiness contract: smallest useful integration proof

**Purpose:** one bounded end-to-end, native-first proof of the frozen Export design; no fabricated PASS. All test outcomes `NOT_RUN`.

## Minimum business cases

| Witness | Required outcome | Forbidden false green | Governing existing BRS |
| --- | --- | --- | --- |
| SO for 30; PO for 4; one supplier load/week | Four separate exact shipments/bookings, shared real orders, partial quantities recognized only once | One SO becomes one load; four POs created without need; all 30 marked fulfilled | EXP-02, 08, 14 |
| One booking five 40HC, four supplier POs | Five distinct equipment slots and containers, multiple source POs, one capacity count per physical slot | Five times four allocation rows counted as 20 containers; duplicate stock | EXP-07, 08, 14 |
| Early PO issuance, later booking | Independently authorized PO send followed by a revision-bound separate booking send | PO waits for booking; duplicate unchanged PO email | EXP-03, 10, 11 |
| Same-number booking roll or carrier cancellation | Source revision preserved, effective cutoff/ERD attributed, impacted pending obligations made stale | Silent overwrite, auto-rebooking, auto carrier rate change | EXP-02, 09, 11, 13 |
| Supplier-delivered FAS port load | Real supplier delivery and terminal evidence displayed, no fictitious carrier | Fake Linda drayage or fake gate-in on arrival | EXP-04, 10 |
| Buyer unassigned then real later sale | Valid buyer-optional custody/movement; subsequent real sale attached without changing history | Fake buyer/SO or stock created to satisfy field | EXP-01, 08 |
| AI PDF/email/XLS intake | Extracts candidate booking/weight identities to exact record; ambiguous goes to review | Newest-partner auto-link, auto-verification, unauthorized state write | EXP-03, 09, 11 |
| Six dashboard sections | Current vital summaries, native filtered report link, original detail drilldown | Generic unfiltered list, inaccessible links or stale=zero | EXP-14, POS-INV-24 draft |
| Multi-company and audience | Never leaks other company bookings, supplier prices or files | Report count or download bypasses ACLs | EXP-06, 14 |

## Mandatory implementation proof classes

- Exact current/approved source-owner adoption of Export-to-Logistics and Export-to-Documents contracts.
- Odoo 19 Enterprise registry install + upgrade and realistic schema/data migration preserving historical links.
- Concurrency / repeat import / amended booking application; 0 overallocated slots under competing assignments.
- ACL and record rule tests for list, search, pivot, dashboard, QWeb, attachments, report export.
- Original document retention and sole verification writer; AI classification alone does not authorize action.
- Actual Odoo Mail state and idempotent obligations; uncertain external send remains unknown, not success.
- Static check of addon dependency DAG and no banned legacy bytes in any future tracked path.

**Gate:** `NOT_RUN` until independently witnessed. Frozen business design is not a merge or deployment decision.

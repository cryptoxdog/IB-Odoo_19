# Dashboard invariant alignment and irreducibility: POS-INV-24

**Date:** 2026-10-28. **Status:** operator-approved design direction, candidate constitutional wording; NOT repository-admitted, NOT implemented, NOT Enterprise-tested.

## Parent and owner

- **Constitutional candidate:** `GOVERNANCE/ODOO_INVARIANTS_v3.2.0_DRAFT_r1.md` adds `POS-INV-24` immediately before preserved `BAN001`. Original `POS-INV-01..23` and `BAN001` are unchanged.
- **Existing law crosswalk:** `POS-INV-01` native-first, `02` one writer, `04` stable identity/replay, `05` company/party isolation, `20` proof vs activation, `21` order/load/booking cardinality. The new item protects dashboard *coverage + traceable contextual drilldown* not already required as a universal contract by those owner/authority invariants.
- **Export BRS owner:** `BRS-EXP-14-R017` dashboard experience; `R021` exact six mandatory report identities; `R022` individual links, scope propagation and reconciliation. The six report-specific metric definitions stay only in `BOOKING_CONTROL_CENTER_UX.md` and the BRS. Do not bake six reports into the global invariant: other domains have different report inventories.
- **Execution owner:** Odoo native dashboard/list/pivot/search/action feature set with minimum extensions. No new reporting engine, report database, mailer or ledger. Authoritative data still comes from existing module owners.

## Distinguishing negative witness

A dashboard can obey every source-owner rule, display accurate current cards, and respect ACLs but still be non-actionable if it lacks the underlying report coverage or opens a generic unfiltered list. `POS-INV-24` rejects that independent loss of meaning. Conversely, a menu that links to reports without surfacing their vital facts also fails.

## Exact acceptance witnesses (NOT_RUN)

1. Dashboard Overview has six source-derived, meaningful summary sections and links to all six report identities. Report titles open corresponding report views; metric/data-point clicks open that metric's actual filtered rows.
2. From a 40HC booking availability card scoped to company, terminal and cutoff week, destination retains that scope; the booking/slot details have exact current revision provenance.
3. From missing documents the user sees exactly the outstanding current verified-evidence obligations, then reaches the original document/verification when permitted; not a generic all-documents list.
4. Mixed-PO booking 6509024800 reports 5 distinct containers, 4 POs, source-reported weight once, and 0 remaining slots only when all five confirmed slots are actually allocated. A 5 -> 4 capacity amendment becomes an exception without fabricating a shipment release.
5. Switching user permissions never reveals restricted counts, prices, names, documents, screenshots or recipient lists via a summary or filter fallback.
6. If the data source is stale/unknown/not loaded, dashboard distinguishes unavailable from a true zero; if source revisions change after click, show refreshed/as-of context rather than a fabricated exact reconciliation.
7. A read of Overview or linked report does not send mail, approve documents, alter native stock, post accounting or dispatch a truck.

**Proof status:** Each check is a DESIGN test; Odoo 19 Enterprise install, dashboard click path, ACL/pivot behavior, reconciliation, provider data and performance remain `NOT_RUN`. Independent architectural acceptance and v3.2 constitutional admission remain separate.

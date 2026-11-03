# Version 2.2.0: operator freeze and booking-control center

**Freeze:** The operator approved the Phase 1 Export architecture expressed in v2.1.0, without authorizing repository/constitutional admission or code realization. See `EXPORT_BRS/CONVERGENCE/OPERATOR_DESIGN_FREEZE.md`.

**Added Phase 1 UI workbench candidate:** The existing native reporting chapter BRS-EXP-14 gained eight additive `DESIGN` rules (R014..R021). They define confirmed booking space by equipment, allocations across POs/loads, remaining slots, revisions and roll exceptions, native Odoo Overview/Bookings/Allocations/Containers/Deadlines/Reporting, and lean report suite. See `EXPORT_BRS/BOOKING_CONTROL_CENTER_UX.md`.

**Invariant alignment:** No new constitutional invariant: the added screens reuse POS-INV-01/02/05/06/07/08 and the draft POS-INV-21/22/23. Avoid a second document writer, outbound mail queue, physical load engine, shipment ledger or report database.

**Evidence and runtime:** historical private fixtures remain in the pack unchanged. 119 BRS cases NOT_RUN. No source owner contract admitted, no Enterprise runtime validation, no implementation or external action.

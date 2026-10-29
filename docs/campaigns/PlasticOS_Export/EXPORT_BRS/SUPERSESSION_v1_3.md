# Controlled supersession: v1.3.0 AI booking case evidence

This working revision supersedes v1.2.0 **only** for the scoped rules named below. It is not adopted into `IB-Odoo_19`, Native-First Documents BRS, or Logistics BRS.

### Modified existing rule identities (same IDs)

- BRS-EXP-09-R002: multi-input extraction and field-level unknowns
- BRS-EXP-09-R003: exact booking / PO / shipment / ticket matching
- BRS-EXP-09-R005: same vs replacement booking, rolls, same-name changed files
- BRS-EXP-09-R007: evidence-to-business-event transitions and incomplete milestones

All other original BRS-EXP-01..10 rule text, ID and source authority preserved. `BRS-EXP-11-R001..R012` are new, nonduplicative scenario-level AI interpretation BRS. The existing Export read/consume-only boundary is unchanged.

### Supersession of invalid assumptions

- A changed ERD / cutoff / container count is not by itself proof that the same booking was formally rolled, cancelled or replaced.
- A supplier's 'booking complete' message is not authoritative evidence of terminal gate-in, vessel departure or native invoice posting.
- Booking-level facts shall not be indiscriminately copied to all 5 loads of the original PO, or to a generic last-open partner transaction.
- A second weekly supplier booking message does not trigger a second commercial PO or a new dispatch without Logistics release.

### Cross-owner interface changes (proposed)

Native Odoo Mail/Documents: preserve email/thread/attachments/links as attributable originals and use native Odoo 19 AI capabilities when installed/validated. `plasticos_documents`: exact typed document binding, classification, verification; reject partner-only latest-open auto-link. `plasticos_export`: booking record, exact current revision, typed candidate values and scoped changes; do not fork OCR/general document state. `plasticos_logistics`/Linda: feasibility, dispatch, versioned supplier/carrier packets and receiving gates. Native Purchase/Sales/Stock: partial fulfillment, prices, quantity balances, inventory and legal/accounting facts. No owner repository files are altered.

### Verification status

Source case PDF and XLSX read; accepted operational meaning user-supplied. 78 positive/negative scenarios structurally indexed `NOT_RUN`. No Enterprise AI live execution, independent behavioral review or runtime pass claimed.

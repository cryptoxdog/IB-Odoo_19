# v2.1.0 - Export architecture convergence candidate

This is a DESIGN resolution pass on the four remaining Export architecture questions. It is additive to v2.0.0 and does not falsely change BRS source rules, accepted repo ADRs, constitutional authority or actual code.

- **C-01:** preserve existing one-transaction-to-one-load link per physical shipment; multiple transactions may share the same commercial SO/PO. Introduce only the irreducible ocean booking context (one booking, many loads) and exact line-level quantity association.
- **C-02:** allow buyer-unassigned owned/procured cargo without fake buyer/SO while preserving company/source/role-scoped guard. Source movement may be supplier-delivered; Linda drayage is conditional.
- **C-03:** native Documents original + PlasticOS Documents one verification authority + exact AI matching; Export accepts guarded booking values; Linda sole outbound authorized sender.
- **C-04:** present repo v2.2.0 constitution governs; v3.1 remains draft, with no BAN001 weakening. Separate global policy admission from product-level design.

See `GOVERNANCE/EXPORT_ARCHITECTURE_CONVERGENCE_CANDIDATE.md` and `EXPORT_BRS/CONVERGENCE/`.

**Result:** Four resolutions articulated and bounded. Technical adoption by BRS owners, current revision reconciliation, Enterprise implementation proof and independent GAR/L9 freeze remain outstanding; do not mislabel this as already implemented or formally converged.

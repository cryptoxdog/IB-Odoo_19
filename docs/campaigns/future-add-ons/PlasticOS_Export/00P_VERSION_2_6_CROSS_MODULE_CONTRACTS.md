# Export v2.6.0 | Cross-module integration contracts

**Status:** PROPOSED SOURCE-OWNER HANDOFF; NOT ADMITTED, IMPLEMENTED, ENTERPRISE TESTED, OR ACTIVATED.

This revision retains the 2026-10-28 operator-frozen Export Phase 1 design and all 120 existing BRS rule statements and 120 acceptance texts byte-for-byte. The new authoritative *candidate interop reading surface* is `EXPORT_BRS/INTEROP/CROSS_MODULE_INTEGRATION_CONTRACTS.md`, covering seven precise contracts (`EXP-IC-01..07`) and 17 positive/negative cross-owner witnesses (`IC-T01..17`, all NOT_RUN).

The interop file defines source and consumer owners, required source identity/revision/rights, allowed reads and commands, rejected behaviors, concurrency and recovery, forward-only dependency topology, owner adoption and source-backed evidence. It does NOT expose working endpoints or grant an Export addon permission to modify upstream owners. Historical owner amendments remain unedited and unadmitted proposals.

The existing v2.5 readiness contract remains the module candidate model/acceptance owner, with a single pointer to the v2.6 interop file. The root README and proposed addon README point to that reading path. Odoo sources were rechecked at `cryptoxdog/IB-Odoo_19 Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`; `.github` global source at `main@3dcdeaae355b6de08562993f705084d7a3714bfd`. Enterprise runtime, Odoo code, migrations, repo governance and live communications were not changed or executed. The working `GOVERNANCE/ODOO_INVARIANTS_v3.3.0_DRAFT_r1.md` is still NOT admitted; v2.2.0 in the target repository remains the authoritative constitution.

**Single next interface decision:** Logistics/Transaction source-owner adoption of exact buyer-optional company/physical shipment identity (`EXP-IC-02`), with `EXP-IC-01` native fulfillment boundary as its prerequisite. Other contracts can be assessed independently but cannot be called accepted until their owner and runtime proofs close.

**Integrity maintenance:** The prior `EXPORT_BRS/SHA256SUMS` had two stale hashes after the v2.5 README changes and did not index its two v2.5 new design files. The exact old ledger bytes are preserved at `GOVERNANCE/SOURCES/EXPORT_BRS_SHA256SUMS_v2.5.0_snapshot.txt`; the v2.6 `EXPORT_BRS/SHA256SUMS` is regenerated against its complete current member set, while the outer `MANIFEST.json` independently records every pack member. BRS rule texts and acceptance cases are unchanged.

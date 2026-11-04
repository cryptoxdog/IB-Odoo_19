# Export BRS v1.6.0: invariant alignment, sequential supplier releases, and observed booking revisions

**Status:** Working non-admitted requirements correction, 2026-10-28; no code or repository change. Existing rule IDs and positive/negative scenario identities are preserved. All 111 runtime cases remain `NOT_RUN`.

## Narrow in-place rule changes

- `BRS-EXP-10-R002` corrects the supplier PO + booking sequence. An approved PO is issuable independently. Booking evidence can arrive later. Every new booking notice is a separate source-revision obligation; a current reference PO may be attached only when authorized. This supersedes older prose suggesting mandatory PO+booking issuance at first release.
- `BRS-EXP-11-R005` strengthens same-number booking revision handling using the actual user-supplied 3/4/5 x 40HC variants, differing cutoffs and terminal ERDs. The source files do not on their own establish authoritative chronological precedence.
- Acceptance cases `AC-EXP-10-002` and `AC-EXP-11-005` are revised; no other IDs or business owners change.
- `INTEROP/TARGET_OWNER_BRS_AMENDMENTS.md` is corrected as a proposed **Logistics owner** handoff, not as a direct edit of admitted Logistics BRS.
- `SOURCE_CASE_BOOKING_6509024800_REVISIONS.md` and additional restricted originals are new evidence/probes, not new business authority.

## Constitutional candidate dependency

The separate operator-supplied Odoo invariants v3.0.0 DRAFT r3 remains byte preserved. The proposed v3.1.0 DRAFT successor adds `POS-INV-21` (independent commitments/allocations/bookings), `POS-INV-22` (revision-scoped downstream validity), `POS-INV-23` (separate trade roles/custody/milestones). `POS-INV-01..20` and `BAN001` are preserved word-for-word. These new candidates are not repository-admitted and do not supersede constitutional repository `INVARIANTS.md` v2.2.0.

## Invariant-alignment changes

- The private legacy example screenshot was **renamed without changing its file bytes** to comply with the restricted legacy identifier rule. All source-name references were updated. No private source is authorized for repository commit.
- Cross-product `ROS-OPS-*` remain product-local UX/physical constraints, mapped to the constitutional candidate, not competing constitutional laws.
- Exact owner boundaries remain: Odoo Purchase/Sales/Stock/Accounting, native Documents and `plasticos_documents`, Logistics/Linda, and thin Export coordinator. Booking field changes cannot directly mutate orders, physical states, settlement or dispatch.
- Eight product-claim proof gates remain `SPECIFIED_NOT_PROVEN`, never marketing-approved by package generation.

## Historical and admission boundaries

Older supersession records remain as historical evidence except for the narrowly documented mandatory identifier sanitization. The operator must separately approve constitutional admission, resolve actual Logistics/Docs owner conflicts, and authorize implementation/tests. No deployment, send, customs submission or licensing was performed.

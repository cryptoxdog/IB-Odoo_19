# Transport equipment acceptance and non-duplication probes

The eight authoritative rule/acceptance pairs are `EXPORT_BRS/RULES/BRS-EXP-07.md` and `EXPORT_BRS/ACCEPTANCE/cases.json` (AC-EXP-07-001..008). ALL statuses: NOT_RUN.

## Focused end-to-end operator scenarios

1. Domestic 53-foot, 48-foot and flatbed all selectable; flatbed has no hardcoded length.
2. Phase 1 booking suggests 40HC for plastic, but can choose 40STD or 45HC/45STD; independently choose 20STD for a metal export.
3. One booking requests two 40HC containers, later records two distinct physical container IDs, individual seals and scannable cargo packages without duplicating booking-level weight on each unit.
4. Ocean unit drayed on chassis preserves trailer/load vs ISO container distinction.
5. Substitute 40STD for 40HC only with attributed booking discrepancy and authorized revision; never auto-dispatch/email.
6. Compute per-unit load content from native Odoo package and stock records only; no shadow inventory or billing authority.
7. A booking missing actual equipment information remains `Unknown`, with dates, port and documents derived from their respective source owners.
8. Adding nominal equipment type does not invent universal load capacity, legal VGM or weight settlement.

**Negative-control source finding:** Existing `plasticos.equipment.type` describes balers/granulators and feeds facility capability projections. It must not become transport equipment. Exact native shipping owner/field reuse must be verified before implementation.

# `plasticos_logistics` agent instructions

**Read first for logistics/Linda modifications:** [LINDA_BUILD_PLAN.md](LINDA_BUILD_PLAN.md) (60-rule accountable WP/acceptance map), [business_rules/README.md](business_rules/README.md), relevant [BRS-01..07](business_rules/README.md#brs-index), [business_rules/BRS-POS-10-linda-logistics-commercial-and-physical-communication.md](business_rules/BRS-POS-10-linda-logistics-commercial-and-physical-communication.md), the admitted external-send clauses `BRS-POS-09-R006` through `BRS-POS-09-R012` in [business_rules/SUPERSESSION.md](business_rules/SUPERSESSION.md), and applicable accepted `docs/adr/` architecture decisions.

The operator directs that these **module-local BRS requirements be treated with the same change-control seriousness as ADRs**. Do not place or relocate the BRS files in `docs/`. All 60 source rule records are preserved unchanged in `business_rules/rules.json`, but the later operator decisions in the supersession register control identified conflicts. Missing PO or SO is not an approval trigger by itself. Do not infer that registered requirements are already implemented or runtime validated.

For any implementation, reference affected `BRS-##-R###` IDs in the change description and corresponding positive/negative tests. No silent business-rule edits, stale plan overrides, unsupported cross-company actions, fabricated inventory/PO/SO documents or unauthorized live sends. Global `AGENTS.md` and accepted architecture ADRs remain applicable.

<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_BEGIN -->
## Linda effective BRS and native-first binding (new, 2026-10-26)

Before **any** logistics code change, open `business_rules/EFFECTIVE_RULES.md`, `business_rules/NATIVE_DOCUMENTS_INTEROP.md`, `business_rules/SUPERSESSION.md`, `business_rules/ALIGNMENT_ACCEPTANCE.md` and the relevant unchanged historical `BRS-01..07.md`. The 60 original IDs remain canonical for logistics. Cross-domain `BRS-POS-*` references express working PlasticOS Documents/Stock/Accounting integration, not a duplicate module-local business-rule authority. Respect current accepted ADRs and ask the operator when a material semantic conflict remains.

Native Odoo 19 Enterprise capabilities MUST be checked in the real installed fixture, not guessed from documentation. Use internal native Documents Requests/Activities for internal work; Linda/native Mail for external messages. Keep one original and one business verification writer, independent PO/SO native releases, real READY before dispatch, separate business clocks and no financial posting via compliance recompute. Native AI is candidate-only and NOT RUN. Every affected rule requires a positive and falsifying acceptance case; never activate live emails or finance by installing this BRS pack. The 2026-10-27 reconciliation preserves this overlay and matches non-documentation blobs to #316 `53b18fd90046696e946a0d8e1e60e88595a5e143` without accepting that runtime.
<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_END -->

The dated supersession of 2026-11-05 admits exactly one copied Native-First chapter, BRS-POS-10, and admits BRS-POS-09-R006 through BRS-POS-09-R012 as Linda external-send obligations. Every other BRS-POS chapter stays a cross-domain reference and is not a second copied authority. BRS-POS-04 through BRS-POS-08, BRS-POS-11 and BRS-POS-12 stay with their owners.

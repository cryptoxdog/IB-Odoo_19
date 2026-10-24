# `plasticos_logistics` agent instructions

**Read first for logistics/Linda modifications:** [LINDA_BUILD_PLAN.md](LINDA_BUILD_PLAN.md) (60-rule accountable WP/acceptance map), [business_rules/README.md](business_rules/README.md), relevant [BRS-01..07](business_rules/README.md#brs-index), and [business_rules/SUPERSESSION.md](business_rules/SUPERSESSION.md), plus applicable accepted `docs/adr/` architecture decisions.

The operator directs that these **module-local BRS requirements be treated with the same change-control seriousness as ADRs**. Do not place or relocate the BRS files in `docs/`. All 60 source rule records are preserved unchanged in `business_rules/rules.json`, but the later operator decisions in the supersession register control identified conflicts. Missing PO or SO is not an approval trigger by itself. Do not infer that registered requirements are already implemented or runtime validated.

For any implementation, reference affected `BRS-##-R###` IDs in the change description and corresponding positive/negative tests. No silent business-rule edits, stale plan overrides, unsupported cross-company actions, fabricated inventory/PO/SO documents or unauthorized live sends. Global `AGENTS.md` and accepted architecture ADRs remain applicable.

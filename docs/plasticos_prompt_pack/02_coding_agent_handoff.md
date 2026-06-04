# IB-Odoo_19 — Coding Agent Handoff: Gaps to Live Buyer Matching
# Supersedes: IB-Odoo_19-Coding-Agent-Handoff.md
# Refinements: web lead regression hotspots; partner-deferral warning; go-live checklist;
#              test fixture table; make target commands; PR base branch clarified.

**Generated:** 2026-05-26 | **Branch audited:** Production | **Open PRs:** 3

---

## The Three Stubs Blocking Live Matching

All three must be cleared simultaneously — they are independent killswitches.

### Stub 1 — ICP Feature Gate
**File:** `plasticos_base/models/matching_engine_icp.py`

Key: `plasticos.matching_engine.enabled` — default `"False"` — raises `UserError` on all matching UI buttons.

**Fix:** Settings → Technical → System Parameters → set to `True`

### Stub 2 — Engine Stub Gate
**File:** `plasticos_buyer_match_engine/models/matching_stub.py`

Key: `plasticos.matching_engine.stubbed` — default `"True"` — `find_matches_for_supplier()` returns `[]` immediately.

```python
def _matching_stub_enabled(self):
    return not matching_engine_is_enabled(self.env) or matching_engine_is_stubbed(self.env)
```

**Fix:** System Parameters → `plasticos.matching_engine.stubbed = False`

### Stub 3 — Neo4j Credential Gap
**File:** `plasticos_buyer_match_engine/models/graph_service.py` → `_get_config()`

Without credentials: Stage 2 Cypher scoring never fires; all `total_score = 0.0`. Degrades to warning — does NOT block UI.

**Fix:** Add to `.env`:
```
NEO4J_URL=bolt://neo4j:7687
NEO4J_URI=${NEO4J_URL}
NEO4J_USER=<user>
NEO4J_PASSWORD=<password>
```
Neo4j must have `Facility` and `MaterialProfile` nodes seeded. `SOLD_TO` edges must have `avg_price_per_lb`.

---

## Open PRs

### PR #88 — feat: add Odoo-specific Cursor rules
- **Target:** Production | **Status:** Ready to merge — config only, zero risk
- Adds `.cursor/rules/95-test-fix-policy.mdc` — journal fixtures, `skipTest()` policy, Odoo 19 product type constraints
- Once merged: Cursor agents must honor `skipTest` policy in all test generation

### PR #85 — wire TODO #1-4 intake matching + offer flow + tests
- **Target:** Staging | **DO NOT merge directly to Production**

| File | Change |
|---|---|
| `plasticos_intake/models/intake.py` | `action_match_to_buyers()` wired; `action_send_offers()` idempotent; offer/match view actions added |
| `plasticos_intake/models/intake_match.py` | `offer_id` Many2one + `offer_state` related field |
| `plasticos_buyer_match_engine/models/matcher.py` | `typical_price` from Neo4j SOLD_TO `avg_price_per_lb` |

Tests (PR #85 HEAD only — NOT on Production):
- `tests/plasticos_claims/test_claim_ux_filters.py`
- `tests/plasticos_offer/test_offer_ux_icons.py`
- `tests/plasticos_intake/test_intake_matching_flow.py`

Deploy after merge:
```bash
make update m=plasticos_claims,plasticos_offer,plasticos_intake,plasticos_buyer_match_engine
```

### PR #83 — fix(web_lead): 10X rewrite — HOT/COLD fix, 17 issues
- **Target:** Staging | **Root cause:** `WeightPerLoad="unknown"` beat numeric quantity → `estimated_lbs=0` → HOT leads → COLD → no intakes → no matching

Key fixes:

| # | Issue | Fix |
|---|---|---|
| 1 | `quantity_text` WeightPerLoad priority | Prefer numeric value |
| 2 | `estimated_lbs=0` when AI returns None | Weight fallback cascade (AI → Vision → qty×1500 → 0) |
| 3 | `_process_hot_lead_simple` missing `.sudo()` | Added |
| 4 | `write()` guard bypassable | Blocks ALL non-state fields on `intake_created` |
| 5 | Double write of `self.intake_id` | Single authoritative write — **AGENT: DO NOT REWIRE** |
| 7 | Duplicate `_create_intake_*` functions | Unified `_create_intake()` |
| 16 | `_find_or_create_partner` DEPRECATED 2026-02-23 | Removed from flow |

Deploy after merge:
```bash
make update m=plasticos_web_leads
```

Tests: `tests/test_web_lead*.py` — **run these before proposing ANY changes to web_lead.py**

---

## Wiring Gaps on Production (independent of open PRs)

### Gap 1 — Base `action_match_to_buyers()` is a Placeholder
**File:** `plasticos_intake/models/intake.py`

Base implementation logs a TODO and returns a fake notification. Real implementation is in `plasticos_buyer_match_engine/models/intake_extension.py` via `_inherit` override.

**Risk:** If `plasticos_buyer_match_engine` fails to load, fake notification returns silently.
**Action:** Verify module is in addons path and load order in `docker-compose.yml`.

### Gap 2 — `res_model` Mismatch (CRITICAL)
**File:** `plasticos_buyer_match_engine/models/intake_extension.py`

```python
"res_model": "plasticos.match.result",  # WRONG — model does not exist
```
Correct: `"plasticos.intake.match"`. Will raise `ValueError` on action return.
**Must fix before go-live. Check if PR #85 addresses this.**

### Gap 3 — `typical_price` Hardcoded 0.0
**File:** `plasticos_buyer_match_engine/models/matcher.py`

`"typical_price": 0.0` until PR #85 is merged AND SOLD_TO edges exist in Neo4j.

### Gap 4 — Missing Fields: `has_metal`, `is_metalized`, `has_fr`
**File:** `plasticos_buyer_match_engine/models/matcher.py` → `_extract_material_requirements()`

These fields are read from intake but NOT declared on `plasticos.intake`:
```python
"has_metal":    intake.has_metal or False,      # AttributeError at runtime
"is_metalized": intake.is_metalized or False,
"has_fr":       intake.has_fr or False,
```
**Fix:** Add fields to intake model OR use `getattr(intake, 'has_metal', False)`.

### Gap 5 — `pipeline_v2.py` Broken Import Bomb
**File:** `plasticos_inference_engine/pipeline_v2.py`

Broken imports for: `.config`, `.odoo_writer`, `.prompt_builder`, `.qa_gate`, `.schema_loader`, `.sonar_client`, `.telemetry`

Not in `__init__.py` — not a runtime hazard currently. **AGENT: DO NOT import, wire, or reference.**

### Gap 6 — `plasticos_enrichment` Enriches Nothing
Intentional stub. Gated on `pipeline_v2.py` API bridge. Do not wire until bridge is ready.

---

## Web Lead Regression Hotspots

These patterns in `web_lead.py` generate false "fix" suggestions from agents. Both have `# AGENT: DO NOT REWIRE` comments in the file:

1. **`self.intake_id` single write** — PR #83 fixed a double-write. The single write IS correct.
2. **Partner-deferral write block** — partner creation is intentionally deferred; the write block on `intake_created` records is a guard, not a bug.
3. **`_find_or_create_partner()`** — DEPRECATED 2026-02-23. Removed from main flow. Do not re-introduce.

---

## Go-Live Checklist

```
[ ] 1. Merge PR #88 to Production (Cursor rules — zero risk)
[ ] 2. Merge PR #83 to Staging (HOT/COLD fix)
[ ] 3. make update m=plasticos_web_leads; verify HOT leads create intakes
[ ] 4. Merge PR #85 to Staging (matching wiring)
[ ] 5. Fix Gap 2: plasticos.match.result → plasticos.intake.match (if not in PR #85)
[ ] 6. Fix Gap 4: has_metal / is_metalized / has_fr (add fields or safe getattr)
[ ] 7. Set ICP: plasticos.matching_engine.enabled = True
[ ] 8. Set ICP: plasticos.matching_engine.stubbed = False
[ ] 9. Provision Neo4j credentials in .env
[ ] 10. Seed Neo4j: Facility + MaterialProfile nodes + SOLD_TO edges with avg_price_per_lb
[ ] 11. make audit (full) — verify TIER_1 + TIER_3 pass
[ ] 12. Promote Staging → Production
```

---

## Test Fixture Reference

| Module | Test Files | Note |
|---|---|---|
| `plasticos_web_leads` | `tests/test_web_lead*.py` | On Production — run before any web_lead.py changes |
| `plasticos_intake` | `tests/plasticos_intake/test_intake_matching_flow.py` | PR #85 HEAD only |
| `plasticos_claims` | `tests/plasticos_claims/test_claim_ux_filters.py` | PR #85 HEAD only |
| `plasticos_offer` | `tests/plasticos_offer/test_offer_ux_icons.py` | PR #85 HEAD only |

Production tests are flat in `tests/test_*.py`.
PR #85 HEAD tests are nested in `tests/plasticos_*/` — not yet on Production.

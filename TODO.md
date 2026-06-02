# PlasticOS TODO

## Trip Handoff — State as of 2026-06-02

All local work has been committed and pushed to `cryptoxdog/IB-Odoo_19`. To continue on the laptop: clone, then `git fetch --all` and check out the branch you want.

### Open PRs → `Staging` (base `ea4859b`, green / loaded in Odoo)
- **PR #92** — `fix/geolocalize-nominatim-throttle` — geolocalize Nominatim throttle config + debug cleanup.
- **PR #93** — `fix/logistics-load-dashboard-registry-crash` — logistics fresh-install registry crash fix.
- **PR #94** — `chore/repo-docs-and-gitignore` — `.gitignore`, capitalized branch-name docs, ADR-002/003, `requirements-dev.txt`.

### WIP branches pushed for continuation (no PR yet — run `make pr-check` before any PR)
- `fix/prelaunch-consolidation` — in-progress prelaunch consolidation (geolocalize/intake/logistics manifests + models). Last commit is a WIP checkpoint; NOT validated yet.
- `fix/semgrep-rules-overhaul` — semgrep Odoo rules overhaul (advisory-lock exemption, sql-injection rule, `--error` gating).
- `fix/semgrep-odoo-raw-sql-triage` — 2 production-fix commits + a recovered WIP checkpoint commit (pr-autopilot/gitignore/requirements).

### Reminders
- Branch names are **capitalized**: `Staging` / `Production` (macOS case-insensitivity makes `git checkout staging` resolve to `Staging`).
- Geo 429 durable fix (keyed geocoder provider, needs API key) is a separate follow-up GMP.

---

## Pending Integration

### Intake → Buyer Matching → Offers Pipeline

**Status:** Intake UI complete, matching engine stub in place

**When buyer matching engine is integrated:**

1. **Wire `action_match_to_buyers()` to matching engine**
   - File: `plasticos_intake/models/intake.py`
   - Currently returns empty `matches = []`
   - Engine should return: `[{"buyer_id": int, "match_score": float, "match_reason": str, "typical_price": float}]`

2. **Populate `typical_price` from buyer data**
   - File: `plasticos_intake/models/intake_match.py`
   - Options:
     - Pull from buyer's historical purchases for similar materials
     - Pull from buyer profile preferences
     - Compute from market data
   - Consider making it a computed field vs engine-populated

3. **Wire `action_send_offers()` to offer module**
   - File: `plasticos_intake/models/intake.py`
   - Currently raises placeholder error
   - Should create `plasticos.offer` records for each selected buyer
   - Pre-fill offer with intake material details

4. **Add "View Offers" button after offers sent**
   - Show link to created offers from intake form
   - Track offer status back on intake (pending/accepted/rejected)

---

## Deferred: External API Bridge Integration

### `plasticos_inference_engine/pipeline_v2.py` — Incomplete Module

**Status:** Placeholder file with broken imports — DO NOT USE until API bridge is ready

**What it is:**
This file is designed to orchestrate external inference and graph engine services via API calls, replacing the current pure-Python inference modules and making the Odoo instance slimmer.

**Missing dependencies (intentionally not created):**
- `.config` (Settings)
- `.odoo_writer` (OdooWriter)
- `.prompt_builder` (build_system_prompt, build_user_prompt)
- `.qa_gate` (evaluate)
- `.schema_loader` (SchemaEnums, load_schema)
- `.sonar_client` (SonarClient, SonarError)
- `.telemetry` (log_result, log_run_summary)

**When to instantiate:**
When the external API bridge connection to inference and graph engines (L9/Sonar) is established. This will:
1. Replace existing pure-Python inference modules (`engine.py`, `grade_engine.py`, `tier_engine.py`, etc.)
2. Offload heavy AI/ML computation to external services
3. Keep Odoo instance lightweight (thin client pattern)

**Current working modules (pure Python, no external deps):**
- `engine.py` — Main inference engine
- `grade_engine.py` — Grade matching
- `tier_engine.py` — Quality tier classification
- `contamination_engine.py` — Contamination detection
- `rule_engine.py` — Rule-based inference
- `kb_loader.py` — Knowledge base loading

---

## Future Enhancements

- [ ] Buyer profile module with material preferences and typical prices
- [ ] Market price data integration
- [ ] Offer acceptance workflow
- [ ] Automated follow-up reminders
- [ ] **Link product.template to material_profile** (patch 011)
  - Add `material_profile_id` M2O field to `product.template`
  - Add related fields: `material_polymer`, `material_form`, `material_resin_grade`
  - Enables filtering products by material type in sales workflows
  - Requires adding `product` to `plasticos_material_profile` depends
  - Patch file: `docs/03-01-2026/011-link-product-to-material-profile.patch`

---

## Remaining Low/Medium Priority Items

- [ ] **Financials Calculation:** Kept `amount_total` (accrual basis) for gross margin but added a dependency on `state` to ensure updates.
- [ ] **Dual Supplier Profiles:** Left as-is to avoid breaking downstream views, but `supplier_profile_id` should be treated as the source of truth.
- [ ] **Freight Bill Auto-Link:** Requires a more complex heuristic (matching carrier partner to active transactions) which was out of scope for this immediate fix. Manual linking is still available.
===

make new transaction file from sm

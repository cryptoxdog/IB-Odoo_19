# Staging → Production Promotion Rehearsal — Specification

## Acceptance criteria (all must pass for verdict `ready`)

### Gate 1 — Branch identity
- `git rev-parse --abbrev-ref HEAD` == `Staging`
- `git rev-parse HEAD` == `git rev-parse origin/Staging`
- No local commits ahead of remote

### Gate 2 — Merge-tree
- `git merge-tree origin/Production origin/Staging` exits 0
- Output contains zero `<<<<<<<` conflict markers
- `origin/Production` SHA is recorded and must not change during the rehearsal

### Gate 3 — Install-smoke
- `make install-smoke` exits 0
- All 53 PlasticOS + Enterprise modules show ✅
- Publication evidence written (source fingerprint stable)

### Gate 4 — Cutover clone
- `bash scripts/test_env.sh clone odoo_test_cutover` succeeds
- `bash scripts/test_env.sh upgrade odoo_test_cutover` succeeds
- `bash scripts/test_env.sh assert-clone odoo_test_cutover` exits 0
- Partner census: `SELECT COUNT(*) FROM res_partner WHERE customer_rank > 0 OR supplier_rank > 0` == 0

### Gate 5 — Web lead e2e
- Odoo HTTP starts on rehearsal port (not 8069) on `odoo_test_cutover`
- POST `payloads/cognito_hot.json` to `/api/v1/cognito-webhook`
  - Response `status == 200`, `decision == "HOT"`
  - `intake_id` is non-null (a `plasticos.intake` was created)
  - `lead_id` is non-null (a `crm.lead` was created)
- POST the same body a second time → same `web_lead_id` (idempotency)
- Do NOT mock `evaluate_economic_opportunity`; a cold decision is a failure

### Gate 6 — ERP import (10% slice)
- `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` are non-empty (not printed)
- The census sibling `<summary>-census.json` has `payload_kind` equal to `database`. `grid` and `statements` fail the gate
- `ERP_REQUIRE_EMPTY` is not set to 0 (default guard stays)
- `ODOO_STAGE` is unset; `ERP_PRODUCTION_PERMIT` is not passed
- Import exits 0 with a valid summary JSON
- Summary satisfies: `records_seen == records_created + records_updated + records_unchanged + records_rejected`
- `duplicates == 0`
- At least 1 counterparty, 1 address, 1 contact imported

### Gate 7 — VanillaSoft contacts
- Runs only when Gate 6 passed
- `VANILLASOFT_API_KEY` is bound from Infisical and injected into the clone ICP. The value is not printed and is not stored in the kit
- `make import-vanillasoft` on `odoo_test_cutover` with `VANILLASOFT_CALL_FLOOR` set to seven days ago
- The import exits 0 and writes `06-crm-result.json`

## Verdict rules

| Condition | Verdict |
|-----------|---------|
| All 7 gates pass | `ready` |
| Any gate fails with a known, documented blocker in `expected/blockers.yaml` | `blocked` |
| Any gate fails with an undocumented failure | `failed` |

## Out of scope

- Partner creation from web lead (deferred — partner deferral is by design)
- Gate/CEG/EIE triage (Phase 3 only)
- Matching, scoring, offer creation (ERP partners needed first)
- Promotion merge itself (human decision after `ready` verdict)
- Full ERP import (100% of transactions) — 10% is sufficient for the rehearsal

## Kit constraints

- No secrets in any kit file
- Bearer token for web lead is `plasticos.web.lead.config.api_key`, the same row `web_lead_api.py` compares. A fresh cutover clone copies that field from the `odoo` database, or from `ODOO_WEB_LEAD_API_KEY`, onto its own config row before the POST. The value is not printed.
- ERP credentials are loaded from `.env.local` at run time and not echoed
- The template is never rebuilt by this kit

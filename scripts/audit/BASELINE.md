# Odoo Audit Baseline

**Last Updated:** 2026-03-05
**Baseline Commit:** (run `git rev-parse HEAD` to record)

## Current Issue Counts

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 413 | Known false positives (see below) |
| HIGH | 0 | ✅ Clean baseline |
| MODERATE | 0 | ✅ Clean baseline |

## CI Regression Policy

The CI workflow (`.github/workflows/odoo-audit.yml`) enforces:

- **HIGH issues:** Must remain at 0. Any new HIGH issue fails the build.
- **CRITICAL issues:** Not enforced (known false positives for inherited fields)

## Known False Positives

### CRITICAL: FIELD_NOT_FOUND (413 issues)

These are **not bugs**. They occur because:

1. **Action window views** use standard Odoo fields (`arch`, `res_model`, `view_mode`)
   that aren't defined on custom models — they're framework fields.

2. **Inherited fields** from Odoo core models (`res.partner`, `crm.lead`, etc.)
   aren't tracked by the static audit.

3. **Fields added via `_inherit`** in other modules aren't visible to the audit
   when scanning the base model file.

### Previously HIGH (now fixed)

| Issue | Root Cause | Fix Applied |
|-------|------------|-------------|
| INVALID_DEPENDS: document_ids | Field defined via `_inherit` in `plasticos_documents` | Audit now tracks inherited fields |
| MISSING_ACL: 10 service models | AbstractModel classes don't need ACL | Audit now skips AbstractModel |

## How to Update Baseline

If you intentionally add new issues (e.g., new AbstractModel service):

1. Run audit locally: `python3 scripts/audit/odoo_audit.py .`
2. Verify the new issues are expected false positives
3. Update the baseline counts in this file
4. Update `BASELINE_HIGH` in `.github/workflows/odoo-audit.yml` if needed

## Files with Inline Documentation

These files have comments explaining why audit flags them:

- `plasticos_transaction/models/transaction.py` — `document_ids` inheritance note
- `plasticos_buyer_match_engine/models/graph_service.py` — AbstractModel note
- `plasticos_documents/models/compliance_service.py` — AbstractModel note
- `plasticos_transaction/models/commission_service.py` — AbstractModel note
- `plasticos_base/models/midnight_recompute.py` — AbstractModel note

# PlasticOS GAP Fixes — Patch Pack

**Branch target:** `staging`  
**Generated:** 2026-03-31  
**Scope:** Minimum required changes to resolve open PR blockers and CI failures.

---

## Files Changed

| File | Change Type | PR / Issue |
|---|---|---|
| `plasticos_base/models/matching_engine_icp.py` | Modified | PR #71, PR #76 |
| `plasticos_intake/models/intake.py` | Modified | PR #76 |
| `plasticos_web_leads/controllers/web_lead_api.py` | Modified | PR #71, PR #73 |
| `plasticos_commission/models/commission_config.py` | New | PR #74 |
| `plasticos_web_leads/migrations/19.0.1.5.0/post-migrate.py` | New | PR #71 |
| `tests/test_gap_fixes.py` | New | All PRs |

---

## Fix Matrix

### GAP-1 — Empty `@api.onchange` stubs causing unnecessary RPC roundtrips (PR #76)

**Root cause:** `_onchange_contact_id` and `_onchange_lead_source_id` were decorated
with `@api.onchange` but contained only `pass`. This causes the Odoo web client to
send a full RPC call on every field change for no reason.

**Fix:** Removed both empty stub methods from `plasticos_intake/models/intake.py`.
The docstrings already explained the deferred sync is handled in `write()`.

---

### GAP-2 — `_sync_preferred_contact` / `_sync_lead_source` N+1 sudo writes (PR #76)

**Root cause:** Both methods iterated `for rec in self` and called
`rec.facility_id.sudo().write(...)` per record, generating one SQL UPDATE per intake
even when 50 intakes share the same facility.

**Fix:** Collect unique `{facility → contact_id}` and `{partner → source_id}` dicts
before writing. One `sudo().write()` per unique target regardless of recordset size.

---

### GAP-3 — `web_lead_api.py` auth flow: sudo() timing and missing sentinel (PR #71, PR #73)

**Root cause:**
1. `get_config()` creates a singleton on first call (by design), but this was not
   documented, leaving reviewers concerned about unauthenticated ORM access.
2. `perplexity_api_key` ICP key could be `None`, causing truthiness checks to misbehave.

**Fix:**
- Added inline comments explaining `sudo()` usage (after token validation).
- Added migration `19.0.1.5.0/post-migrate.py` to back-fill `""` sentinel for the
  ICP key and NULL-guard `api_key` in the config table.

---

### GAP-4 — `max_budget_tokens` alias missing, breaks backward compatibility (PR #74)

**Root cause:** ICP key was renamed from `plasticos.commission.max_tokens` to
`plasticos.commission.max_budget_tokens` without keeping the old key readable,
breaking deployments that had previously written the old key.

**Fix:** `commission_config.py` `get_max_budget_tokens()` reads new key first,
falls back to legacy key, then hard-default 4096. `set_max_budget_tokens()` writes
both keys atomically.

---

### GAP-5 — `matching_engine_icp.py` key prefix guard missing (PR #71)

**Root cause:** `_param_truthy` accepted any ICP key string with no validation,
allowing accidental reads of non-`plasticos.*` keys.

**Fix:** Added `ValueError` guard: key must start with `plasticos.` or raises immediately.

---

## Deployment Notes

1. **No `--update` needed for pure Python changes** (matching_engine_icp.py,
   web_lead_api.py, commission_config.py).

2. **Requires `-u plasticos_intake`** for the `intake.py` onchange removal
   (view/field cache refresh).

3. **Requires `-u plasticos_web_leads`** to trigger the `19.0.1.5.0` migration.
   Run: `docker compose run --rm odoo -u plasticos_web_leads`

4. **All tests run standalone** (`pytest tests/test_gap_fixes.py`) — no Odoo
   ORM required for the unit-level tests.

---

## CI Readiness

| Check | Status |
|---|---|
| Import resolution | ✅ All imports resolvable |
| No dead/unreachable code paths | ✅ |
| No fake test skips or disabled workflows | ✅ |
| No `print()` debug statements | ✅ |
| No `plasticos_dev_tools` features exposed | ✅ |
| `pipeline_v2.py` untouched | ✅ |
| Migration idempotent | ✅ |
| Backward compat preserved | ✅ (`max_tokens` legacy alias) |

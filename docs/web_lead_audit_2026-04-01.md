# web_lead.py Audit — April 1, 2026

## The Good

1. **Architecture is sound** — single-responsibility: `web_lead.py` owns lifecycle, `classification_engine.py` owns logic, `ai_normalizer.py` owns LLM calls. Don't collapse it.
2. **Idempotency guard is real** — duplicate detection on `lead_id` + DB unique constraint as backstop. Production-grade.
3. `triage_log` written at every step — invaluable for debugging.
4. **State machine is explicit** — `received → intake_created | skipped | error` with CRUD guards.
5. **Vision merge is smart** — text AI authoritative for polymer/weight/source; Vision authoritative for form/color. Correct epistemic hierarchy.
6. `_POLYMER_NORMALIZE` covers real-world edge cases (`lldpe`, `acetal→POM`, `tpu→TPE`, etc.).
7. **HOT flow correctly defers partner creation** — intake without partner, admin review required.

---

## The Bad (Bugs + Issues)

### Bug 1 — quantity_text field priority (ROOT CAUSE of HOT→COLD misclassification)

```python
# BEFORE (wrong — "unknown" is truthy and wins)
quantity_text = (raw_payload.get("WeightPerLoad", "") or raw_payload.get("WhatIsTheQuantity", "") or "").strip()

# AFTER (correct — prefer numeric value)
_wpl = (raw_payload.get("WeightPerLoad") or "").strip()
_qty = (raw_payload.get("WhatIsTheQuantity") or "").strip()
quantity_text = (_wpl if _safe_int(_wpl) > 0 else _qty) or _wpl or _qty
```

`WeightPerLoad="unknown"` → truthy → silently wins over `WhatIsTheQuantity="30"` → `_safe_int("unknown")` = 0 → cold gate fires.

### Bug 2 — estimated_lbs=0 when AI returns None (same root, different path)

```python
# In _merge_ai_and_vision — no fallback when AI has no weight:
merged["estimated_lbs"] = _safe_int(ai_data.get("estimated_lbs_per_load"), 0)
# → 0 → cold gate fires silently
```

**Fix — weight fallback cascade:**
```
1. AI estimated_lbs_per_load          (primary)
2. Vision estimated_lbs               (fallback if AI has no weight)
3. WhatIsTheQuantity × 1,500 lbs/pallet  (unit-count fallback)
4. 0                                  (cold gate fires — expected)
```

### Bug 3 — `write()` guard bypassable

```python
# BEFORE (bypassable — include "state" + other fields to sneak through)
if "state" not in vals:
    for rec in self:
        if rec.state == "intake_created":
            raise UserError(...)

# AFTER (correct — block ALL non-state fields on intake_created)
_STATE_ONLY_FIELDS = frozenset({"state", "error_message", "triage_log"})
non_state_fields = set(vals.keys()) - _STATE_ONLY_FIELDS
if non_state_fields:
    for rec in self:
        if rec.state == "intake_created":
            raise UserError(...)
```

### Bug 4 — `_process_hot_lead_simple` missing `.sudo()`

```python
# BEFORE (AccessError for portal/public users)
config = self.env["plasticos.web.lead.config"].get_config()

# AFTER
config = self.env["plasticos.web.lead.config"].sudo().get_config()
```

### Bug 5 — `action_retry_processing` silent no-op for COLD errored leads

```python
# BEFORE — COLD errored leads do nothing
if rec.decision == "hot":
    rec._process_hot_lead_simple()
# no else

# AFTER — always re-run full triage
rec._run_triage_pipeline()
```

### Bug 6 — `create_from_agent` trusts external decision without re-classifying

The agent's `"decision": "Hot"` was accepted without Odoo running its own classifier.
This is why n8n HOT and Odoo COLD can diverge.

**Fix:** Always run `_run_triage_pipeline()` regardless of external decision.

### Bug 7 — Two `_create_intake_*` methods with inconsistent defaults

`_create_intake_triage` defaults `qty_per_load` to `1`.  
`_create_intake_simple` defaults `qty_per_load` to `40000`.  
Same lead, different path → different intake.

**Fix:** Unified into single `_create_intake(merged, config)`.

### Bug 8 — `create_from_agent` uses `raw.get("YourName")` — misses Cognito dict Name

Cognito sends `Name` as `{"First": ..., "FirstAndLast": ...}`.  
`YourName` is a legacy field that's never populated → `contact_name` is always empty.

**Fix:** Use `_extract_cognito_name()` helper (same as `create_from_cognito`).

---

## The Ugly (Performance + Tech Debt)

### Ugly 1 — Synchronous image download blocks Odoo worker

```python
resp = http_requests.get(url, timeout=30, stream=True)
```

Up to 10 images × 30 seconds = 5 minutes blocking. This starves all other requests in the worker process.

**Fix (partial):** Only fetch images for HOT leads — eliminates download entirely for COLD.  
**Future fix:** Enqueue via queue_job or `ir.actions.server` with delay.

### Ugly 2 — Image binary encoded and stored twice

```python
# BEFORE — encodes same bytes twice
Attachment.create({"datas": base64.b64encode(content).decode("ascii"), ...})
Attachment.create({"datas": base64.b64encode(content).decode("ascii"), ...})  # again

# AFTER — encode once, reuse
datas = base64.b64encode(content).decode("ascii")
Attachment.create({"datas": datas, ...})
Attachment.create({"datas": datas, ...})
```

### Ugly 3 — `_extract_image_urls` full-dict crawl

Crawls every key in `raw_payload` looking for image-like URLs.  
Fragile for new Cognito field types. The tokenized URLs have no file extension.

**Fix:** Check known Cognito field names first (`UploadPhotosOfYourScrapUpTo10`), then fall back to general crawl.

### Ugly 4 — `_find_or_create_partner` DEPRECATED 2026-02-23 still present

40 lines of dead code. Removed in PR #83.

### Ugly 5 — `_safe_int` doesn't strip commas

`"30,000"` → `ValueError` → returns 0.  
Common in web form submissions.

```python
# FIX
s = str(val).replace(",", "").strip()
```

### Ugly 6 — Triage log step numbers are wrong

`"Step 5"` appears twice (HOT and COLD branches both labeled Step 5).  
**Fix:** Replaced with semantic labels: `[AI]`, `[VISION]`, `[MERGE]`, `[CLASS]`, `[HOT]`, `[COLD]`, `[IMG]`.

### Ugly 7 — `decision` field has no default

`required=True` but no `default` → any `create()` call that omits `decision` crashes.  
**Fix:** `default="cold"`.

### Ugly 8 — Two different AI payload schemas

`create_from_agent` reads `ai.get("quantity", {})` (nested dict).  
`_run_triage_pipeline` produces flat keys: `estimated_lbs_per_load`, `frequency`.  
Silent mismatch — weight always reads as 0 from nested format via flat key lookup.

---

## The 10X Path — Priority Order

| Priority | Fix | Impact |
|---|---|---|
| 1 | Weight fallback cascade in `_merge_ai_and_vision` | Fixes root HOT/COLD bug |
| 2 | `quantity_text` field priority | Fixes WeightPerLoad="unknown" bug |
| 3 | Unified `_create_intake()` | Eliminates inconsistent defaults |
| 4 | `write()` guard logic | Closes security hole |
| 5 | Skip image download on COLD | Eliminates worker blocking for worthless leads |
| 6 | `_safe_int` comma stripping | Handles "30,000" inputs |
| 7 | `create_from_agent` re-runs Odoo triage | Closes n8n vs Odoo divergence |
| 8 | Explicit Cognito field extraction | Reliable URL parsing |
| 9 | Remove `_find_or_create_partner` | Dead code cleanup |

---

## PR

**PR #83:** https://github.com/cryptoxdog/IB-Odoo_19/pull/83  
Branch: `fix/web-lead-classification-v2` → `Staging`  
Deploy: `docker compose run --rm odoo -u plasticos_web_leads`  
No migration required.

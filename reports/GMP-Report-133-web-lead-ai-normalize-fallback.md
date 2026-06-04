# GMP Report 133 — Web Lead AI `normalize_with_fallback`

**Run ID:** GMP-FIX-AI-FALLBACK
**Date:** 2026-06-04
**Target Branch:** Staging
**Scope:** `plasticos_web_leads/models/ai_normalizer.py` (additive only)
**Commit Message:** `fix(web_leads): add normalize_with_fallback to ai_normalizer (restore lead triage)`

---

## 1. PLAN

Restore the inbound web-lead triage pipeline, which is broken in production. Live
`odoo.log` on Staging (commit `6a283c6`) shows every AI-enabled lead failing:

```
ERROR ... plasticos_web_leads.models.web_lead: Triage pipeline error for lead CG-4-8380
AttributeError: module 'odoo.addons.plasticos_web_leads.models.ai_normalizer'
                has no attribute 'normalize_with_fallback'
```

`web_lead.py:564` calls `ai_normalizer.normalize_with_fallback(raw_payload=..., providers=...)`,
but `ai_normalizer.py` only defined `normalize_lead(...)`. Fix is additive: implement the
missing multi-provider fallback wrapper around the existing `normalize_lead`.

### MODIFICATION LOCK
- **May modify:** `plasticos_web_leads/models/ai_normalizer.py`
- **Must NOT modify:** `web_lead.py`, `web_lead_config.py`, `classification_engine.py`,
  `image_analyzer.py`, any partner-deferral / `intake_id` double-write / write+unlink guard logic.

### ADRs CONSULTED
- `.cursor/rules/50-plasticos-web-lead-guard.mdc` — partner deferral, double-write, and
  write/unlink guards left untouched (change is in a sibling helper module only).

---

## 2. CHANGES

Single file, purely additive (79 insertions, 0 deletions):

- `_build_openai_client(api_key, base_url=None)` — lazy-imports `openai.OpenAI`, returns a
  client or `None` when key/package is missing. Mirrors the construction pattern already used
  in `image_analyzer.analyze_image`.
- `normalize_with_fallback(raw_payload, providers, *, temperature=0.0)` — iterates the ordered
  provider list from `config.get_llm_providers_ordered()`, calls the existing `normalize_lead`
  per provider, returns the first success with `_provider_used` set; on per-provider
  `_ai_error` it advances to the next; if all fail (or none configured) it returns the
  deterministic-only base dict with `_provider_used="none"` and `error` set.

---

## 3. TODO → CHANGE MAP

| TODO | Phase | File | Operation | Result |
|------|-------|------|-----------|--------|
| T-001 | 2 | `ai_normalizer.py` | Insert (after `normalize_lead`, L271/L291) | APPLIED |
| T-002 | 3 | — | Governance scope check | VERIFIED |
| T-003 | 4 | `ai_normalizer.py` | ruff / AST / signature / semgrep | PASS |
| T-004 | 5 | — | Recursive verification (1-file diff) | VERIFIED |
| T-005 | 6 | this report | Evidence | DONE |

---

## 4. VALIDATION

| Check | Result |
|-------|--------|
| `ruff check ai_normalizer.py` | PASS — All checks passed |
| `ruff format --check ai_normalizer.py` | PASS — already formatted |
| `python3 ast.parse` | PASS — AST OK |
| Signature assertion (`raw_payload`, `providers`, kw `temperature`) | PASS |
| Caller-contract assertion (`_provider_used` pop, `error` branch) | PASS |
| `ReadLints` | PASS — no linter errors |
| `semgrep --config .semgrep/odoo-patterns.yml --severity ERROR` | PASS — no ERROR findings |
| `git diff --stat` | 1 file, +79 / -0 |

---

## 5. DECLARATION

Phases 0-6 complete. No assumptions. No drift.

---

## Evidence Sections

### 1. Change Summary
Added the missing `normalize_with_fallback` (and a small `_build_openai_client` helper) to
`ai_normalizer.py`, satisfying the existing call in `web_lead.py:564` and restoring AI lead triage.

### 2. Locked TODO Plan
TODO PLAN ID: GMP-FIX-AI-FALLBACK. T-001 (implementation) + T-002..T-005 (governance,
validation, recursive verification, evidence). No edits outside the locked plan.

### 3. Ground Truth Verification
- `normalize_with_fallback` previously undefined repo-wide (`git grep` empty).
- Caller confirmed at `web_lead.py:564` passing `raw_payload=` and `providers=`.
- Provider dict shape confirmed from `web_lead_config.get_llm_providers_ordered()` /
  `_get_provider_info()`: `{provider, api_key, model, base_url}`.
- `openai` already declared in `__manifest__.py` `external_dependencies.python` — no new dependency.

### 4. Files Modified
- `plasticos_web_leads/models/ai_normalizer.py` (+79, -0).

### 5. Implementation Evidence
`_build_openai_client` at L271, `normalize_with_fallback` at L291; file length 347 lines.

### 6. Governance Updates
New tools governed: 0. New approval gates: 0. Runtime/DB/deploy behavior changes: 0.
Web-lead guard zones (partner deferral, `intake_id` double-write, write/unlink guards): UNTOUCHED.

### 7. Tests Run
No `tests/test_web_lead*.py` present on this branch (flat Production layout referenced by the
guard not on Staging). Validation performed via ruff, AST, semgrep, and static
signature/caller-contract assertions. Runtime regression should be confirmed post-deploy by
re-triaging a lead (`action_retry_triage`) and confirming `state != error`.

### 8. Validation Results
All checks PASS (see section 4).

### 9. Invariants Check
- `_name` literals unchanged; no new model; no ACL impact.
- Additive change only; no schema/migration impact.
- Lazy import inside function (no top-level cross-addon import).

### 10. Final Declaration
Phases 0-6 complete. No assumptions. No drift.

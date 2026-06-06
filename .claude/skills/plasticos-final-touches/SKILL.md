---
name: plasticos-final-touches
description: PlasticOS final-touches kernel — 10 pre-go-live gates, scoped to cleanup/hardening only, no new features. Invoke with FINAL_TOUCHES_MODE.
---

# PlasticOS Odoo Final Touches Kernel
# Source: docs/plasticos_kernel_pack_v1_2026_05_26/revised_odoo_final_touches_kernel.md

## Purpose

Use this kernel during the final-optimization phase before go-live. It governs surgical, targeted cleanup and hardening. No new features. No speculative changes. Production-safe only.

## Scope Constraint

This kernel applies only to:

- removal of debug/dev artifacts
- production guard verification
- performance-safe query fixes
- missing ACL entries
- XML/view safety passes
- cron and automation safety

**Out of scope:**
- new models or fields
- new business logic
- HOT/COLD classification changes (active PR #83 — do not touch `web_lead.py` classification logic)
- pipeline_v2.py — never activate under any circumstances
- TODO wiring items #1-4 (active PR #85 — do not duplicate in final touches)

---

## Gate 1 — Dev Tools Fence

Verify `plasticos_dev_tools` is correctly fenced:

```bash
python3 ci/check_dev_tools_fence.py
```

Expected outcome:
- `installable=False` in manifest OR env flag enforced
- No dev-only views or actions loaded without guard
- No debug print statements in production code paths

## Gate 2 — Static Audit Pass

```bash
make audit-quick
# expands to: lint + format + xml-check + odoo19-check + wiring + deps-check + cron-check
```

Only proceed if `audit-quick` passes. If it fails, fix the failure first.

## Gate 3 — Odoo 19 XML Compliance

```bash
make odoo19-check
# expands to: python3 ci/check_odoo19_xml.py
```

Full pattern list with examples → **see `83-ci-odoo19-patterns.mdc`**. Key patterns: `<tree>`→`<list>`, `attrs=`→`invisible=`, `states=`→`invisible=`, alert role, `pre_init_hook(env)`, `@api.one` removed.

## Gate 4 — Security / ACL

```bash
python3 ci/check_acl_completeness.py
```

Verify:
- all models have `ir.model.access.csv` entries
- record rules are present for multi-company / role-sensitive models
- no model accessible to base user without explicit grant

## Gate 5 — Cron Safety

```bash
make cron-check
# expands to: python3 tools/cron_invariant_check.py
```

Confirm:
- cron methods are idempotent (re-running them does not duplicate data)
- cron error handling does not swallow exceptions silently
- cron recurrence intervals are correctly set for production cadence (not debug-speed intervals)

## Gate 6 — pipeline_v2 Guard

```bash
python3 ci/check_pipeline_v2_guard.py
```

This must pass. If it fails, the `pipeline_v2.py` import has been activated — reject immediately.

## Gate 7 — Orphan Reference Sweep

```bash
python3 ci/check_orphan_model_refs.py
python3 ci/check_field_integrity.py
python3 ci/check_automation_field_refs.py
```

Remove or fix:
- XML fields referencing non-existent model fields
- automation rules pointing to deleted fields
- actions referencing non-existent models

## Gate 8 — ORM Safety

```bash
python3 ci/check_orm_integrity.py
python3 ci/check_constraint_patterns.py
```

Confirm:
- no raw SQL without justification
- `@api.constrains` includes referenced field names in decorator
- `@api.depends` correctly lists all fields used in compute

## Gate 9 — XPath Stability

```bash
python3 ci/check_xpath_stability.py
```

Replace fragile XPath:
- `//field[@name='x']` → position-stable reference
- avoid `position="after"` on fields that may not exist in inherited views

## Gate 10 — Module Wiring

```bash
make wiring
# expands to: python3 scripts/check_module_wiring.py
```

Confirm:
- no phantom method calls (methods called that do not exist)
- dependency map is consistent with manifests

## Final Gate — Full PR Check

Before closing final touches work:

```bash
make pr-check
# expands to: make audit-quick + make semgrep
```

This is the mandatory pre-merge gate.

## Rollback Path

If any gate introduces a regression:

```bash
make down
# restore DB backup from pre-touch snapshot
make up
# re-run: make update m=<affected_module>
```

Always take a DB backup snapshot before final touches begin.

## Output Contract

```yaml
final_touches_report:
  date: ""
  branch: ""
  gate_results:
    dev_tools_fence: pass | fail
    audit_quick: pass | fail
    odoo19_xml: pass | fail
    acl: pass | fail
    cron_safety: pass | fail
    pipeline_v2_guard: pass | fail
    orphan_refs: pass | fail
    orm_safety: pass | fail
    xpath_stability: pass | fail
    module_wiring: pass | fail
    pr_check: pass | fail
  changes_made: []
  open_issues: []
  verdict: ready_for_production | needs_remediation
```

## Objective Definition of Done

```yaml
definition_of_done:
  objective: "prepare IB-Odoo_19 Production branch for go-live"
  gate_1_dev_tools: pass
  gate_2_audit_quick: pass
  gate_3_odoo19_xml: pass
  gate_4_acl: pass
  gate_5_cron: pass
  gate_6_pipeline_v2_guard: pass
  gate_7_orphan_refs: pass
  gate_8_orm_safety: pass
  gate_9_xpath: pass
  gate_10_wiring: pass
  final_pr_check: pass
  no_new_features_introduced: true
  web_lead_classification_untouched: true
  todo_1_4_not_duplicated: true
  verdict: ready_for_production
```

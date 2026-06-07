<!-- L9_META
skill_schema: 1
parent: plasticos-final-touches
layer: reference
role: gate_contract
tags: [plasticos, go-live, gates, audit, ci]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Final Touches Gate Sequence

Source: `docs/plasticos_kernel_pack_v1_2026_05_26/revised_odoo_final_touches_kernel.md`

## Scope Constraint

**In scope:** debug/dev artifact removal, production guard verification, performance-safe query fixes, missing ACL entries, XML/view safety, cron and automation safety.

**Out of scope:** new models or fields; new business logic; HOT/COLD classification changes (`web_lead.py`); `pipeline_v2.py` activation; TODO wiring items #1–4 (active PR #85).

---

## Gate 1 — Dev Tools Fence

```bash
python3 ci/check_dev_tools_fence.py
```

Expected: `installable=False` in manifest OR env flag enforced; no dev-only views/actions without guard; no debug prints in production paths.

## Gate 2 — Static Audit Pass

```bash
make audit-quick
```

Only proceed if `audit-quick` passes.

## Gate 3 — Odoo 19 XML Compliance

```bash
make odoo19-check
```

Full pattern list → `.cursor/rules/84-ci-odoo19-patterns.mdc`. Key: `<tree>`→`<list>`, `attrs=`→`invisible=`, `states=`→`invisible=`, alert `role=`, `pre_init_hook(env)`.

## Gate 4 — Security / ACL

```bash
python3 ci/check_acl_completeness.py
```

Verify all models have ACL entries; record rules for multi-company/role-sensitive models.

## Gate 5 — Cron Safety

```bash
make cron-check
```

Confirm idempotent cron methods, non-silent error handling, production cadence intervals.

## Gate 6 — pipeline_v2 Guard

```bash
python3 ci/check_pipeline_v2_guard.py
```

Must pass. Failure = pipeline_v2 import activated — reject immediately.

## Gate 7 — Orphan Reference Sweep

```bash
python3 ci/check_orphan_model_refs.py
python3 ci/check_field_integrity.py
python3 ci/check_automation_field_refs.py
```

Fix XML fields, automation rules, and actions referencing deleted models/fields.

## Gate 8 — ORM Safety

```bash
python3 ci/check_orm_integrity.py
python3 ci/check_constraint_patterns.py
```

Confirm no unjustified raw SQL; `@api.constrains` and `@api.depends` field lists are complete.

## Gate 9 — XPath Stability

```bash
python3 ci/check_xpath_stability.py
```

Replace fragile position-based XPath with stable field anchors.

## Gate 10 — Module Wiring

```bash
make wiring
```

Confirm no phantom method calls; dependency map matches manifests.

## Final Gate — Full PR Check

```bash
make pr-check
```

Mandatory pre-merge gate.

## Rollback Path

If any gate introduces regression:

```bash
make down
# restore DB backup from pre-touch snapshot
make up
make update m=<affected_module>
```

Always take a DB backup snapshot before final touches begin.

<!-- L9_META
skill_schema: 1
parent: plasticos-repo-review-kernel
layer: reference
role: review_sequence
tags: [plasticos, repo, inventory, registry, ci]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Repo Review Sequence

Execute in order. Record evidence per step.

## 1. Git Visibility

Branch, status, diff, tree, recently changed files relevant to scope.

## 2. Module Inventory

All `plasticos_*` modules: manifests, data files, security, views, models, tests, migrations.

## 3. Registry Safety

`_name`, `_inherit`, methods, fields, XML IDs, actions, cron refs — orphan and integrity scripts:

```bash
python3 ci/check_orphan_model_refs.py
python3 ci/check_field_integrity.py
python3 scripts/check_module_wiring.py
```

## 4. Architecture Boundary

Lower layers must not import higher layers. Cross-layer Many2one prohibited where wiring rules apply. Compare against `ARCHITECTURE.md`.

## 5. Odoo 19 Compliance

XML patterns, decorators, constraints, hooks, env access:

```bash
make odoo19-check
python3 ci/check_constraint_patterns.py
python3 ci/check_orm_integrity.py
```

## 6. CI Readiness

Inspect or run as appropriate:

```bash
make audit-quick
make guards
make pr-check
```

Map failures to AGENTS.md CI Compliance Checklist and known false positives.

## 7. Installability Risk

Summarize blockers, criticals, highs, mediums. Separate known false positives from new findings.

## Output Contract

```yaml
repo_review_report:
  repo_visibility: full | partial | limited
  branch: ""
  modules_scanned: []
  blockers: []
  critical: []
  high: []
  medium: []
  known_false_positives: []
  ci_gates_reviewed: []
  installability_risk: ""
  verdict: safe_to_continue | conditional | reject
```

## Rule

Never claim repo safety without current visibility or reviewed evidence.

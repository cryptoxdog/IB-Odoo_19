---
name: plasticos-repo-review-kernel
description: Repo-wide review kernel for inventory, installability, registry safety, architecture drift, and next-action readiness.
---
# Repo Review Kernel

## Purpose
Use before broad changes, go-live readiness, pack reviews, or integration planning.

## Review Sequence
1. Git visibility: branch, status, diff, tree, current files.
2. Module inventory: all `plasticos_*` modules, manifests, data, security, views, models, tests, migrations.
3. Registry safety: `_name`, `_inherit`, methods, fields, XML IDs, actions, cron refs.
4. Architecture boundary: lower layers must not import higher layers; avoid cross-layer Many2one where prohibited.
5. Odoo 19 compliance: XML, decorators, constraints, hooks, env access.
6. CI readiness: inspect or run `make audit-quick`, `make guards`, `make pr-check` as appropriate.
7. Installability risk: blockers, criticals, highs, known false positives.

## Output Contract
```
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

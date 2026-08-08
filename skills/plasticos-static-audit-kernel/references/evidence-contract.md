<!-- L9_META
skill_schema: 1
parent: plasticos-static-audit-kernel
layer: reference
role: evidence_contract
tags: [plasticos, audit, evidence, report]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Static Audit Evidence Contract

## Required Report Fields

```yaml
static_audit_report:
  date: ""
  branch: ""
  commit: ""
  scope: quick | full | pr-check | custom
  commands:
    - command: ""
      status: pass | fail | not_run
      evidence: ""  # path:line or stderr excerpt
  new_findings: []
  known_false_positives: []  # cite AGENTS.md table
  blockers: []
  verdict: pass | fail | partial
```

## Per-Finding Shape

```yaml
finding:
  severity: blocker | high | medium | low
  source: ""       # script or make target
  path: ""
  message: ""
  new_vs_baseline: new | known
```

## Rules

- Do not mark `pass` without running the command in this session or reviewing equivalent CI log.
- Separate advisory hooks (mypy, acl-completeness warn-only) from blocking gates.
- `make pr-check` failure → verdict `fail` regardless of partial tier passes.
- Include branch/commit when git context is available.

## Known False Positives

Consult `AGENTS.md` § Known False Positives before classifying Many2one string writes, mypy exclusions, phantom enum allowlist entries, and YAML exclusions.

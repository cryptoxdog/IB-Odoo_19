---
name: plasticos-static-audit-kernel
description: Static audit command map and evidence contract for IB-Odoo_19.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, audit, static, ci, make, evidence]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
---

# Static Audit Kernel

## Purpose

Run and report PlasticOS static audit commands with a consistent evidence contract — command, pass/fail, branch/commit, findings vs known false positives, blocker classification.

## Core Contract

Every audit report MUST state:

- Command run (exact `make` target or script path)
- Branch/commit if known
- Pass / fail / not-run per command
- New findings vs known false positives (from `AGENTS.md`)
- Blocker classification with exact file/path evidence

## Authority Order

1. User-requested audit scope (quick vs full vs single gate).
2. `Makefile` targets — ground truth for command expansion.
3. `AGENTS.md` — CI tiers, audit baselines, known false positives.
4. `INVARIANTS.md` — HIGH severity baseline limits.
5. This skill's references.
6. `Unknown` — label commands not run; do not invent pass status.

## Compact Workflow

1. Select tier: `make check` → `make audit-quick` → `make audit` → `make pr-check`.
2. Map targets per [command-map.md](references/command-map.md).
3. Run commands; capture exit codes and relevant stdout/stderr excerpts.
4. Format report per [evidence-contract.md](references/evidence-contract.md).

## Resource Map

- [references/command-map.md](references/command-map.md) — make targets, guard scripts, tier composition.
- [references/evidence-contract.md](references/evidence-contract.md) — report fields and baseline rules.

## Validation

Audit report is valid when every listed command has explicit status and failing commands include file-level evidence. For merge readiness, `make pr-check` MUST pass.

## Failure Handling

- Command not installed / venv missing → `not_run`; suggest `make venv`.
- HIGH finding exceeds CI baseline → classify blocker; cite audit script output.
- Semgrep or mypy advisory failure → note as non-blocking unless user scope requires fix.
- Partial audit → state which tiers were skipped and why.

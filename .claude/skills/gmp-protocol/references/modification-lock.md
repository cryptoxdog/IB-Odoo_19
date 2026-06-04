---
skill_schema: 1
layer: reference
role: governance_contract
tags: [gmp, modification_lock, constraints, validation]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-04
---

# Modification Lock, Constraints & Evidence Validation

Long form: `docs/gmp_protocol/cursor-gmp-canonical.md`.

## Constraints (apply to every run)

- **Quality gates (upfront):** no stubs, placeholders, pseudo-code, or "you'll need to tweak". Production-grade, drop-in, immediately usable.
- **Ground truth (per query):** use only real paths, class names, and signatures verified in this repo. Re-verify each run; never hallucinate structure. Missing context → STOP and ask.
- **Scope discipline:** deliver only what was requested. No unsolicited summaries, indexes, helper files, or refactors.
- **No invention:** no new abstractions, no architecture rewrite, no "better design" outside explicit scope.
- **Failure protocol:** fail loudly; ask before proceeding without necessary context; no assumptions about intent.

## Modification Lock (absolute)

Declared in Phase 0 as two explicit lists.

**May NOT:**
- Modify files not in the locked TODO plan.
- Touch protected paths (below).
- Invent abstractions or redesign unsolicited.
- Add logging/comments/refactoring outside TODO scope.
- Skip phases or assume partial completion.

**May ONLY:**
- Implement the exact changes in the locked plan.
- Operate within phases 0–6 as defined.
- Stop immediately on detected ambiguity.
- Report results in the canonical evidence format.

A change that requires violating the lock **fails at Phase 0**; the human must supply a revised plan with explicit permission.

## Protected Paths (PlasticOS)

Never modify without an explicit, approved TODO:

- `**/pipeline_v2.py` — **never activate**; CI guard hard-rejects any touch.
- `plasticos_base/**`, `plasticos_security_base/**` — Layer-1 foundations; ask first.
- `.github/workflows/ci.yml` — single CI gate; SHA-pin and verify before edits.
- `docker-compose.yml` and deployment config — ask first.
- `ir.cron` scheduled actions and `res.partner` schema changes — ask first.

The original L9 protected set (orchestrator, kernel loader, executor, memory substrate) lives in `docs/gmp_protocol/cursor-phase-0-planning.md`; translate it to the actual target repo's protected paths each run.

## High-Risk Actions (require explicit human approval)

These actions are never taken implicitly inside a run. Schedule them as their own TODO and obtain explicit approval before execution; Phase 5 must confirm none ran unapproved.

- `git commit` / `git push` (use `make push`; never raw `git push`).
- File or record deletion (`Delete` op on a whole file, `unlink`, dropping data).
- Deployment / `make update` / container restarts.
- Database writes outside the locked scope, and any schema-destructive migration (column/table drop).
- Activating `pipeline_v2.py` (hard-forbidden — fails at Phase 0).

If a run reaches an unapproved high-risk action, STOP and request approval rather than proceeding.

## Repo Guardrails (carry into Phase 3/4)

- New model → `security/ir.model.access.csv` row in the same module; new Python file → wired into `__init__.py`; new model file → added to manifest `data`/`depends`.
- `sudo()` requires inline justification on the same line.
- Remote pushes use `make push` (runs `make pr-check`) — never raw `git push`; API push only after `make pr-check` passes and `git push` fails.
- Odoo 19 patterns are CI-enforced (no `_sql_constraints`, `@api.one/multi`, `<tree>`, `attrs=`, `states=`, `t-esc=`).

## Evidence-Based Validation (three categories)

A change is APPROVED only when all three pass; any incomplete category → detailed report with gaps.

**1. Plan integrity**
- Plan is locked, unambiguous, deterministic.
- Every TODO has file path, anchor, operation, expected behavior.
- No speculation language ("maybe/likely/should").

**2. Implementation compliance**
- Every TODO ID has closure evidence (change + line numbers).
- Only TODO-listed files were modified.
- Repo patterns respected (imports, naming, ACL, manifest wiring).
- No changes outside scope.

**3. Operational readiness**
- Code is production-grade and drop-in compatible.
- Tests pass (positive + negative + regression); no regressions in untouched code.
- No breaking changes to public APIs unless the TODO requires them.

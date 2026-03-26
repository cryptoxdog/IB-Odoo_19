---
name: pr-workflow
description: Branch, commit, and open a PR following PlasticOS conventions
disable-model-invocation: true
---

# PR Workflow

## Branch Naming
- `feat/short-description` — new features
- `fix/short-description` — bug fixes
- `docs/short-description` — documentation
- `refactor/short-description` — restructuring
- `test/short-description` — test additions

## Target Branch
- PRs target `staging` (not `main`)
- `main` is production — merged from staging only

## Pre-Commit Checklist
1. `ruff check .` — lint passes
2. `ruff format --check .` — format check passes
3. `python3 scripts/check_module_wiring.py` — dependency graph OK
4. `python3 ci/check_circular_deps.py` — no cycles
5. `xmllint --noout` on changed XML files
6. `pre-commit run --all-files` — all hooks pass

## Commit Message Format
```
feat(module): add field to transaction model
fix(views): resolve xpath targeting in offer form
docs: update module architecture diagram
refactor(intake): extract normalization service
test(integration): add offer state machine test
```

## CI Pipeline (runs on PR)
- Python lint + format (ruff)
- XML + shell validation
- Odoo 19 pattern checks
- Module manifest validation
- Secret detection (gitleaks)

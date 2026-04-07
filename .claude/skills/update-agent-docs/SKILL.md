---
name: update-agent-docs
description: >-
  Audit the repo and update AGENTS.md, ARCHITECTURE.md, INVARIANTS.md, and
  CLAUDE.md with current module inventory, CI pipeline rules, known false
  positives, and pre-commit hook details. Use when the user says "update agent
  docs", "refresh repo docs", "sync agent files", or after adding/removing
  modules, CI checks, or pre-commit hooks.
---

# Update Agent Documentation

Regenerate the four root-level agent instruction files so that coding agents
write CI-passing code and review agents flag real issues (not false positives).

## When to Use

- A new `plasticos_*` module was added or removed
- CI workflows (`.github/workflows/*.yml`) changed
- Pre-commit hooks (`.pre-commit-config.yaml`) changed
- `scripts/check_odoo_patterns.sh` checks were added/modified
- `ci/*.py` audit scripts were added/modified
- `pyproject.toml` ruff/mypy config changed
- Periodic refresh (monthly or after large PRs)

## Execution Protocol

Follow all 7 steps. Do not skip any.

### Step 1 — Inventory Modules

Count installable `plasticos_*` addons:

```bash
find . -maxdepth 2 -name "__manifest__.py" -path "*/plasticos_*/*" | wc -l
```

For each module, extract layer and maturity from `__manifest__.py`:
- **Layer**: determined by `depends` (see ARCHITECTURE.md layer rules)
- **Maturity**: Production (stable CI) / Beta (waivers exist) / New (active dev) / Dev-only (`installable: False`)

Cross-check with the current Module Index in `ARCHITECTURE.md`. Add missing modules, remove deleted ones, correct layer assignments.

### Step 2 — Audit CI Pipeline

Read every workflow file:

```bash
ls .github/workflows/*.yml
```

For each workflow, extract:
- **Job names** and what they check
- **Blocking vs non-blocking**: look for `continue-on-error: true` or `|| true`
- **Baselines**: grep for `BASELINE_HIGH`, `BASELINE_CRITICAL`, or threshold numbers
- **Exclusions**: grep for `--exclude`, `paths-ignore`, `grep -v`

Produce two tables:
1. **Blocking jobs** — must pass for merge
2. **Non-blocking jobs** — informational only

### Step 3 — Audit Pre-commit Hooks

Read `.pre-commit-config.yaml` and extract:

```bash
grep -E '^\s+- id:' .pre-commit-config.yaml
```

For each hook, determine:
- **Type**: Format / Syntax / Odoo / Wiring / Integrity / Safety / Audit / Type
- **Blocking?**: Yes unless wrapped in `bash -c '... || echo'`
- **Global exclusions**: from top-level `exclude:` regex

Count total hooks for the summary line.

### Step 4 — Audit check_odoo_patterns.sh

Read `scripts/check_odoo_patterns.sh` and extract every numbered check:

```bash
grep -n "Checking\|Check " scripts/check_odoo_patterns.sh
```

For each check, extract:
- **Check number** and **name**
- **Detection method** (grep regex, file loop, delegated script)
- **Exclusions** (every `grep -v` or file filter with the reason from comments)

### Step 5 — Audit Ruff/Mypy Config

Read `pyproject.toml` and extract:
- `[tool.ruff]` line-length, target-version
- `[tool.ruff.lint]` select, ignore rules
- `[tool.ruff.lint.per-file-ignores]` — every file pattern and ignored codes
- `[tool.ruff.lint.mccabe]` max-complexity
- `[tool.mypy]` exclude patterns and per-module overrides

### Step 6 — Audit Known False Positives

Search for every intentional exclusion across:

| Source | What to search for |
|--------|--------------------|
| `scripts/check_odoo_patterns.sh` | Every `grep -v` with surrounding comment |
| `.github/workflows/*.yml` | Every `|| true`, `continue-on-error`, baseline |
| `pyproject.toml` | `exclude`, `per-file-ignores`, mypy overrides |
| `.pre-commit-config.yaml` | `exclude:` patterns, `bash -c '... || echo'` |
| `ci/*.py` | `EXCLUDED_DIRS`, `SKIP_DIRS`, `EXTERNAL_MODELS`, whitelist sets |

For each, record: **where**, **what's excluded**, **why** (from comments or "no reason documented").

### Step 7 — Write the Four Files

Update each file surgically (do NOT rewrite from scratch — preserve existing structure):

#### 7a. AGENTS.md

Update these sections with fresh data from steps 1–6:
- **Project Overview** → module count, line counts
- **CI Compliance Checklist** → blocking/non-blocking jobs tables
- **Odoo 19 patterns table** → all numbered checks from step 4
- **Known False Positives** → from step 6
- **Pre-commit Hooks table** → hook count and per-hook details
- **Ruff Configuration table** → from step 5
- **Audit Baselines table** → from step 2
- **Version Drift Warning** → compare ruff versions between pre-commit and CI

#### 7b. ARCHITECTURE.md

Update these sections:
- **Module Index** → module count, add/remove rows, correct layers and maturity
- **CI/CD Architecture** → workflow files, hook categories, global exclusions, audit baselines
- **Architecture Version** → bump patch and update date

#### 7c. INVARIANTS.md

Update these sections:
- **Invariant list** → add new invariants for new CI checks, remove for deleted checks
- **CI Enforcement Map** → map invariants to pre-commit hooks and CI workflows
- **Known False Positives** → from step 6
- **Version** → bump and update date

#### 7d. CLAUDE.md

Update these sections:
- **Always list** → must match invariants and CI checks
- **Never list** → must include every pattern CI rejects
- **References** → verify cross-links to AGENTS.md, ARCHITECTURE.md, INVARIANTS.md

## Validation

After updating, verify consistency:

```bash
# Module count matches across files
grep -c "plasticos_" ARCHITECTURE.md  # Module Index rows
grep "module" AGENTS.md | head -1     # Project Overview count

# Hook count matches
grep -c "id:" .pre-commit-config.yaml # Actual hooks
grep "hook" AGENTS.md | head -1       # Documented count

# No broken cross-references
grep -r "INVARIANTS.md" CLAUDE.md AGENTS.md
grep -r "ARCHITECTURE.md" CLAUDE.md AGENTS.md
grep -r "AGENTS.md" CLAUDE.md
```

## Stop Condition

All four files updated. Module counts, hook counts, and CI job lists match actual repo state. Cross-references between files are consistent.

Present summary:

```
Agent docs updated:
- AGENTS.md:        {lines} lines, {hooks} hooks, {checks} pattern checks, {jobs} CI jobs
- ARCHITECTURE.md:  {lines} lines, {modules} modules
- INVARIANTS.md:    {lines} lines, {invariants} invariants
- CLAUDE.md:        {lines} lines

Changes: {brief list of what changed}
```

## Constraints

- **Surgical edits only.** Do not rewrite files from scratch. Use targeted replacements.
- **Preserve existing structure.** Sections not listed in step 7 must not be modified.
- **No fabricated data.** Every number must come from actual repo files, not memory.
- **Line length = 120** for Python code references (from `pyproject.toml`, not 100).
- **Cross-file consistency.** If a number appears in multiple files, all must match.
- **Do not commit.** Present changes for review. User decides when to commit/push.

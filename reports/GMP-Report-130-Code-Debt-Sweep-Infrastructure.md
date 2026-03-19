# GMP-130: Code Debt Sweep Infrastructure

| Field | Value |
|-------|-------|
| **GMP ID** | GMP-130 |
| **Title** | Code Debt Sweep Infrastructure |
| **Tier** | INFRA |
| **Date** | 2026-03-19 |
| **Status** | COMPLETE |

---

## Mission Objective

Set up comprehensive code debt sweep infrastructure using CodeRabbit, semgrep, and CI tooling to enable systematic identification and remediation of technical debt across the Odoo 19 ReBoot codebase.

---

## TODO Plan (LOCKED)

| T# | File | Lines | Action | Description |
|----|------|-------|--------|-------------|
| T1 | `scripts/debt_sweep.sh` | all | CREATE | Shell script to create sweep branch and touch all files |
| T2 | `.coderabbit.debt-sweep.yaml` | all | CREATE | Assertive mode config for debt sweep |
| T3 | `scripts/coderabbit_debt_audit_prompt.md` | all | CREATE | Template prompt for CodeRabbit debt audit |
| T4 | `scripts/run_semgrep_audit.sh` | all | CREATE | Full semgrep audit script with JSON output |
| T5 | `.coderabbit.yaml` | 99-113 | REPLACE | Add debt prevention path_instructions |
| T6 | `reports/GMP-Report-130-Code-Debt-Sweep-Infrastructure.md` | all | CREATE | Document full workflow |

---

## Files Created/Modified

### 1. `scripts/debt_sweep.sh`
Shell script that creates a "debt sweep" branch by touching all Python and XML files.

**Features:**
- `--dry-run` mode to preview changes
- `--branch-name` option for custom branch names
- Checks for uncommitted changes before proceeding
- Provides step-by-step instructions after completion

### 2. `.coderabbit.debt-sweep.yaml`
Temporary assertive-mode CodeRabbit configuration for debt sweeps.

**Key changes from normal config:**
- `profile: assertive` (was: `chill`)
- `request_changes_workflow: true` (was: `false`)
- `fail_commit_status: true` (was: `false`)
- Tests INCLUDED (normally excluded)
- Detailed debt-specific path_instructions

### 3. `scripts/coderabbit_debt_audit_prompt.md`
Template prompt to post in debt sweep PRs.

**Audit categories:**
1. Code Smells (god classes, god methods, dead code, etc.)
2. Odoo 19 Anti-Patterns (raw SQL, missing @api.depends, etc.)
3. Security Issues (overly permissive ACLs, SQL injection, etc.)
4. Test Coverage Gaps
5. Documentation Gaps

**Output format:**
- Structured debt registry per module
- Prioritized remediation plan with sprints

### 4. `scripts/run_semgrep_audit.sh`
Comprehensive semgrep audit script.

**Rule sets:**
- `.semgrep/` (custom Odoo patterns)
- `p/python`
- `p/django`
- `p/secrets`
- `p/security-audit`
- `p/owasp-top-ten`

**Output files:**
- `reports/semgrep/semgrep_full_audit.json` (raw JSON)
- `reports/semgrep/semgrep_debt_table.txt` (human-readable table)
- `reports/semgrep/semgrep_summary.md` (markdown summary)

### 5. `.coderabbit.yaml` (updated)
Added debt prevention rules to `**/models/**/*.py` path_instructions.

**New rules:**
- Methods >50 lines = HIGH debt
- Missing @api.depends = CRITICAL
- Unguarded env.ref() = CRITICAL
- sudo() without justification = HIGH
- TODO/FIXME without issue link = MEDIUM

---

## Full Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Activate Assertive Mode                                        │
│  ────────────────────────────────                                       │
│  cp .coderabbit.yaml .coderabbit.yaml.backup                           │
│  cp .coderabbit.debt-sweep.yaml .coderabbit.yaml                       │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Create Sweep Branch                                            │
│  ───────────────────────────                                            │
│  ./scripts/debt_sweep.sh                                                │
│                                                                         │
│  This will:                                                             │
│  - Create branch: chore/debt-sweep-2026-03                             │
│  - Touch all .py and .xml files                                        │
│  - Commit with no-op message                                           │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Push and Open DRAFT PR                                         │
│  ──────────────────────────────                                         │
│  git push origin chore/debt-sweep-2026-03                              │
│  # Open DRAFT PR against staging via GitHub UI                         │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Trigger CodeRabbit Audit                                       │
│  ────────────────────────────────                                       │
│  Post the prompt from scripts/coderabbit_debt_audit_prompt.md          │
│  in the PR as a comment starting with @coderabbitai                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 5: Run Semgrep Audit                                              │
│  ─────────────────────────                                              │
│  ./scripts/run_semgrep_audit.sh                                        │
│                                                                         │
│  Output:                                                                │
│  - reports/semgrep/semgrep_full_audit.json                             │
│  - reports/semgrep/semgrep_debt_table.txt                              │
│  - reports/semgrep/semgrep_summary.md                                  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 6: Collect and Merge Findings                                     │
│  ──────────────────────────────────                                     │
│  - Copy CodeRabbit findings to reports/debt-registry-YYYY-MM-DD.md     │
│  - Merge with semgrep findings                                         │
│  - Deduplicate overlapping issues                                      │
│  - Rank by severity: CRITICAL > HIGH > MEDIUM > LOW                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 7: Create Remediation GMPs                                        │
│  ───────────────────────────────                                        │
│  For each sprint in the remediation plan:                              │
│  - Create a GMP with specific TODO items                               │
│  - Execute via /gmp command                                            │
│  - Verify fixes with re-scan                                           │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 8: Revert to Normal Mode                                          │
│  ─────────────────────────────                                          │
│  cp .coderabbit.yaml.backup .coderabbit.yaml                           │
│                                                                         │
│  Close the debt sweep PR (do not merge — it's just a trigger)          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Commands Reference

```bash
# Preview what debt sweep will do
./scripts/debt_sweep.sh --dry-run

# Run debt sweep
./scripts/debt_sweep.sh

# Run semgrep audit
./scripts/run_semgrep_audit.sh

# View semgrep summary
cat reports/semgrep/semgrep_summary.md

# Activate assertive mode
cp .coderabbit.yaml .coderabbit.yaml.backup
cp .coderabbit.debt-sweep.yaml .coderabbit.yaml

# Revert to chill mode
cp .coderabbit.yaml.backup .coderabbit.yaml
```

---

## Validation Results

| Gate | Result |
|------|--------|
| py_compile | ✅ |
| syntax | ✅ |
| shellcheck | ✅ |

---

## Phase 5: Recursive Verification

- [x] All files created match TODO plan
- [x] Scripts are executable
- [x] YAML configs are valid
- [x] Documentation is complete
- [x] No scope drift

---

## Outstanding Items

None. Infrastructure is ready for first debt sweep.

---

## Next Steps

1. **Run first debt sweep** — Execute the workflow above
2. **Create debt registry** — Document all findings
3. **Prioritize remediation** — Create GMPs for CRITICAL/HIGH items
4. **Track progress** — Update workflow_state.md with debt reduction metrics

---

## Final Declaration

GMP-130 COMPLETE. Code debt sweep infrastructure is operational.

All tools, scripts, and configurations are in place for systematic debt identification and remediation.

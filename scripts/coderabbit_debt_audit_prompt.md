# CodeRabbit Debt Audit Prompt

Post this comment in the debt sweep PR to trigger CodeRabbit's comprehensive audit.

---

## Prompt to Post in PR

```markdown
@coderabbitai

## Full Codebase Debt Audit Request

This is a **debt sweep PR** — all files have been touched to trigger a full codebase review.
Please perform a comprehensive code debt audit.

### Audit Scope

For **every file** in this PR, identify and categorize:

#### 1. Code Smells
- God classes (>20 methods or >500 lines)
- God methods (>50 lines)
- Dead code (unreachable, unused imports, commented-out code)
- Duplicated logic (copy-paste patterns)
- Magic numbers (hardcoded values without named constants)
- Missing error handling
- Deep nesting (>3 levels)
- Long parameter lists (>5 parameters)

#### 2. Odoo 19 Anti-Patterns
- Raw SQL queries (SQL injection risk)
- Missing `@api.depends` on compute methods
- Unguarded `env.ref()` (should use `raise_if_not_found=False`)
- `sudo()` without justification comment
- `_inherit` misuse (should be `_name` for new models)
- Hardcoded model names (should use constants)
- Missing `@api.constrains` for business rules
- Compute methods without `store=True` when needed
- Missing `ondelete` on Many2one fields

#### 3. Security Issues
- Overly permissive ACLs (1,1,1,1 for non-admin groups)
- Missing record rules for multi-company isolation
- Unvalidated user inputs in server actions
- Hardcoded credentials or API keys
- Missing CSRF protection on controllers
- SQL injection vulnerabilities

#### 4. Test Coverage Gaps
- Models with no test coverage
- Methods with no test coverage
- Missing edge case tests
- Missing error condition tests
- Flaky tests (time-dependent, order-dependent)

#### 5. Documentation Gaps
- Public methods without docstrings
- Complex logic without comments
- Missing module README files
- Outdated or incorrect documentation

### Output Format

Please produce a **structured debt registry** for each module:

```markdown
## Debt Registry — [module_name]

### Summary
- Total findings: X
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X

### Findings

| ID | File | Line | Severity | Category | Description | Suggested Fix |
|----|------|------|----------|----------|-------------|---------------|
| 1 | models/foo.py | 45 | CRITICAL | Security | Raw SQL query | Use ORM methods |
| 2 | models/bar.py | 120 | HIGH | Code Smell | Method >50 lines | Extract helper methods |
```

### Prioritized Remediation Plan

After listing all findings, produce a **prioritized TODO list**:

```markdown
## Remediation Plan

### Sprint 1: Critical Security (Immediate)
1. [ ] Fix SQL injection in plasticos_base/models/partner.py:45
2. [ ] Add record rules for multi-company in plasticos_intake

### Sprint 2: High Priority (This Week)
3. [ ] Refactor god method in plasticos_inference_engine/models/engine.py:200
4. [ ] Add missing @api.depends in plasticos_automation

### Sprint 3: Medium Priority (This Month)
5. [ ] Add docstrings to all public methods in plasticos_buyer_match_engine
6. [ ] Extract duplicated logic in plasticos_logistics
```

### Module Priority Order

Please analyze modules in this order (most critical first):
1. `plasticos_base` — Core module, highest impact
2. `plasticos_security_base` — Security-critical
3. `plasticos_inference_engine` — Business logic
4. `plasticos_buyer_match_engine` — Matching algorithms
5. `plasticos_intake` — Data ingestion
6. `plasticos_automation` — Cron jobs and automations
7. All other `plasticos_*` modules

Thank you for the thorough audit!
```

---

## After CodeRabbit Responds

1. **Copy the debt registry** to `reports/debt-registry-YYYY-MM-DD.md`
2. **Create GMPs** for each sprint in the remediation plan
3. **Track progress** in `workflow_state.md`

---

## Quick Reference: Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Security vulnerability, data corruption risk, production blocker | Fix immediately |
| HIGH | Missing error handling, performance issue, significant tech debt | Fix this sprint |
| MEDIUM | Code smell, missing tests, documentation gap | Fix this month |
| LOW | Style issue, minor improvement, nice-to-have | Backlog |

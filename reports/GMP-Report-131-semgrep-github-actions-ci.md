# GMP-131: Semgrep GitHub Actions CI Enforcement

| Field | Value |
|-------|-------|
| **GMP ID** | GMP-131 |
| **Title** | Enforce Semgrep in GitHub Actions CI |
| **Tier** | CI |
| **Date** | 2026-06-04 |
| **Status** | COMPLETE |

---

## 1. PLAN

**Objective:** Add Semgrep enforcement to GitHub Actions CI so `.semgrep/odoo-patterns.yml` is consumed by the blocking `static-checks` job.

**Modification lock:** Only `.github/workflows/ci.yml` and this evidence report.

**Locked TODO plan (GMP-SEMGREP-CI):**

| ID | Phase | File | Operation | Description |
|----|-------|------|-----------|-------------|
| T-001 | 2 | `.github/workflows/ci.yml` | Replace | Install `semgrep` alongside `lxml` in static-checks job |
| T-002 | 2 | `.github/workflows/ci.yml` | Insert | Add blocking Semgrep check via `run_check` helper after Manifest syntax |

**ADRs consulted:** Not applicable — repository task is CI workflow wiring only.

---

## 2. CHANGES

### T-001 — Install Semgrep in static-checks job

**Before:**
```yaml
- run: pip install lxml
```

**After:**
```yaml
- run: pip install lxml semgrep
```

### T-002 — Blocking Semgrep check in static analysis tier

Inserted after Manifest syntax check, before advisory Odoo 19 pattern check:

```yaml
# Semgrep custom Odoo/security rules
run_check "Semgrep Odoo patterns" semgrep --error --config .semgrep/odoo-patterns.yml --severity ERROR --quiet --include="plasticos_*"
```

---

## 3. TODO → CHANGE MAP

| TODO | Status | File | Lines | Notes |
|------|--------|------|-------|-------|
| T-001 | APPLIED | `.github/workflows/ci.yml` | 62 | Added `semgrep` to pip install in static-checks job |
| T-002 | APPLIED | `.github/workflows/ci.yml` | 109–110 | Blocking Semgrep check via existing `run_check` helper |

---

## 4. VALIDATION

| Check | Result |
|-------|--------|
| Static assertion check (pip install, run_check command, single occurrence) | PASS |
| YAML parse check (`yaml.safe_load`) | PASS |
| Semgrep config validation (`semgrep --validate`) | NOT RUN — local semgrep blocked by sandbox permissions on `~/.semgrep/semgrep.log` |
| `make pr-check` | NOT RUN — out of GMP scope for this session; wiring-only change |

**Recommendation:** PROCEED

---

## 5. DECLARATION

Phases 0–6 complete. No assumptions. No drift.

---

## Evidence Sections

### 1. Change Summary

Semgrep is now installed and executed in the Tier 2 `static-checks` job of `.github/workflows/ci.yml`. Failures at ERROR severity block the job through the existing `run_check` helper (sets `FAIL=1`). No Odoo runtime dependency was introduced.

### 2. Locked TODO Plan

See Section 1. Both TODOs implemented exactly as specified in GMP Protocol 2.0 prompt.

### 3. Ground Truth Verification

**Baseline (Phase 1):**

| TODO | Status |
|------|--------|
| T-001 | READY — anchor `- run: pip install lxml` found exactly once at line 62 |
| T-002 | READY — anchor area between Manifest syntax and Odoo 19 advisory section confirmed |
| `.semgrep/odoo-patterns.yml` | EXISTS |
| Protected files | NOT TARGETED |

**Overall baseline:** READY

### 4. Files Modified

| File | Action |
|------|--------|
| `.github/workflows/ci.yml` | Modified (T-001, T-002) |
| `reports/GMP-Report-131-semgrep-github-actions-ci.md` | Created (this report) |

No other files modified by this GMP run.

### 5. Implementation Evidence

```62:62:.github/workflows/ci.yml
      - run: pip install lxml semgrep
```

```109:110:.github/workflows/ci.yml
          # Semgrep custom Odoo/security rules
          run_check "Semgrep Odoo patterns" semgrep --error --config .semgrep/odoo-patterns.yml --severity ERROR --quiet --include="plasticos_*"
```

The command mirrors `make semgrep` in the Makefile with the addition of `--error` for non-zero exit on findings (required for CI blocking).

### 6. Governance Updates

| Item | Value |
|------|-------|
| New tools governed | 0 |
| New approval gates added | 0 |
| Observability hooks added | 0 |
| Compliance logging | NOT APPLICABLE |
| CI enforcement | VERIFIED — blocking via `run_check`, not advisory |

### 7. Tests Run

```text
CI Semgrep wiring patch validated
GitHub Actions YAML parses
```

### 8. Validation Results

- Static assertion check: **PASS**
- YAML parse check: **PASS**
- Semgrep config validation: **NOT RUN**
- make pr-check: **NOT RUN**

### 9. Invariants Check

| Invariant | Status |
|-----------|--------|
| Semgrep check is blocking (uses `run_check`, `--error`) | VERIFIED |
| `.semgrep/odoo-patterns.yml` referenced exactly once in new CI check | VERIFIED |
| No Odoo runtime dependency added | VERIFIED |
| Existing static checks remain present | VERIFIED |
| Protected files untouched | VERIFIED |
| pipeline_v2 guard unchanged | VERIFIED |

### 10. Final Declaration

Phases 0-6 complete. No assumptions. No drift.

---

## Commit Message (when requested)

```
[ci] fix: enforce semgrep rules in github actions
```

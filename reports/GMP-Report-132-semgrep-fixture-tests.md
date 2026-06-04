# GMP-132: Semgrep Fixture Tests and Local Validation Wiring

| Field | Value |
|-------|-------|
| **GMP ID** | GMP-132 |
| **Title** | Semgrep Fixture Tests and Makefile Wiring |
| **Tier** | CI / Dev Tooling |
| **Date** | 2026-06-04 |
| **Status** | COMPLETE |

---

## 1. PLAN

**Objective:** Add durable Semgrep rule fixtures under `.semgrep/tests/` and wire a local `make semgrep-test` target to validate config syntax and positive/negative fixture behavior.

**Modification lock:** Only `.semgrep/tests/*`, `Makefile`, and this evidence report.

**Locked TODO plan (GMP-SEMGREP-FIXTURES):**

| ID | Phase | File | Operation | Description |
|----|-------|------|-----------|-------------|
| T-001 | 2 | `.semgrep/tests/positive.py` | Create | Positive Python fixtures triggering hardened Semgrep rules |
| T-002 | 2 | `.semgrep/tests/negative.py` | Create | Negative Python fixtures demonstrating accepted patterns |
| T-003 | 2 | `.semgrep/tests/odoo19.xml` | Create | Odoo 19 XML fixtures for XML rules + valid list-view control |
| T-004 | 2 | `Makefile` | Insert | Add `semgrep-test` target after `semgrep` block |

**ADRs consulted:** Not applicable — Semgrep fixture and Makefile validation wiring only.

**Source pack:** `Current Work - IGNORE/semgrep_enterprise_pack_v2/semgrep/tests/`

---

## 2. CHANGES

### T-001 — `.semgrep/tests/positive.py`

Copied from enterprise pack. Intentionally bad patterns: `_sql_constraints`, `@api.one`/`@api.multi`, `@api.depends("id")`, bare except, eval/exec/compile, pickle/yaml unsafe load, pipeline_v2 import, env.get(), SQL injection patterns, raw SQL, unguarded env.ref(), NotImplementedError, hardcoded secret.

### T-002 — `.semgrep/tests/negative.py`

Copied from enterprise pack. Accepted patterns: `models.Constraint`, safe `@api.depends`, specific exception handling, `yaml.safe_load`, parameterized SQL, guarded `env.ref(..., raise_if_not_found=False)`.

### T-003 — `.semgrep/tests/odoo19.xml`

Copied from enterprise pack. Positive XML triggers: `<tree>`, `attrs=`, `view_mode` tree, `t-esc`, `numbercall`, `category_id`. Negative control: valid `<list>` view with `invisible=`.

### T-004 — `Makefile`

Added `semgrep-test` to `.PHONY`, help text, and target block:

```make
semgrep-test:
	@echo "→ Semgrep rule fixture tests..."
	semgrep --validate --config .semgrep/odoo-patterns.yml
	@echo "→ Positive fixtures should produce findings..."
	@semgrep --config .semgrep/odoo-patterns.yml .semgrep/tests/positive.py .semgrep/tests/odoo19.xml --quiet | grep -q .
	@echo "→ Negative fixtures should produce no blocking findings..."
	semgrep --error --config .semgrep/odoo-patterns.yml .semgrep/tests/negative.py --quiet
```

Not wired into GitHub Actions (per GMP scope).

---

## 3. TODO → CHANGE MAP

| TODO | Status | File | Notes |
|------|--------|------|-------|
| T-001 | APPLIED | `.semgrep/tests/positive.py` | Byte-identical to enterprise pack source |
| T-002 | APPLIED | `.semgrep/tests/negative.py` | Byte-identical to enterprise pack source |
| T-003 | APPLIED | `.semgrep/tests/odoo19.xml` | Byte-identical to enterprise pack source |
| T-004 | APPLIED | `Makefile` | Lines 8, 55, 144–151 |

---

## 4. VALIDATION

| Check | Result |
|-------|--------|
| Fixture source diff (`diff -q` vs enterprise pack) | PASS — all three match |
| `make semgrep-test` | FAIL — pre-existing `.semgrep/odoo-patterns.yml` config error (duplicate `pattern-not` keys at rule `plasticos-python-yaml-unsafe-load`, line 53). Protected file; out of scope for this GMP run. |
| GitHub Actions modified | NOT TOUCHED (verified) |
| App code modified | NOT TOUCHED (verified) |

**Recommendation:** PROCEED for fixture wiring. Fix `odoo-patterns.yml` duplicate-key issue in a separate GMP run to unblock `make semgrep-test`.

**Dev machine command after config fix:**

```bash
make semgrep-test
```

---

## 5. DECLARATION

Phases 0-6 complete. No assumptions. No drift.

---

## Evidence Sections

### 1. Change Summary

Three Semgrep fixture files installed at `.semgrep/tests/` from the enterprise pack. `make semgrep-test` added for local rule validation. Fixtures are isolated from Odoo module paths and are not application code.

### 2. Locked TODO Plan

See Section 1. All four TODOs implemented.

### 3. Ground Truth Verification

**Baseline (Phase 1):**

| Item | Status |
|------|--------|
| `.semgrep/odoo-patterns.yml` exists | YES |
| `Makefile` exists with `semgrep:` target | YES |
| `.semgrep/tests/` safe to create | YES (was absent) |
| Protected files targeted | NO |

**Overall baseline:** READY

### 4. Files Modified

| File | Action |
|------|--------|
| `.semgrep/tests/positive.py` | Created |
| `.semgrep/tests/negative.py` | Created |
| `.semgrep/tests/odoo19.xml` | Created |
| `Makefile` | Modified |
| `reports/GMP-Report-132-semgrep-fixture-tests.md` | Created |

### 5. Implementation Evidence

Copy command used:

```bash
mkdir -p .semgrep/tests
cp "Current Work - IGNORE/semgrep_enterprise_pack_v2/semgrep/tests/positive.py" .semgrep/tests/positive.py
cp "Current Work - IGNORE/semgrep_enterprise_pack_v2/semgrep/tests/negative.py" .semgrep/tests/negative.py
cp "Current Work - IGNORE/semgrep_enterprise_pack_v2/semgrep/tests/odoo19.xml" .semgrep/tests/odoo19.xml
```

### 6. Governance Updates

| Item | Value |
|------|-------|
| Fixtures location | `.semgrep/tests/` only |
| Odoo module paths | NOT ENTERED |
| Positive fixtures documented as intentionally bad | YES (module docstrings) |
| Negative fixture uses accepted patterns | YES |
| Makefile target scope | Local validation only |
| GitHub Actions wiring | NOT IN THIS RUN |

### 7. Tests Run

```bash
make semgrep-test  # exit 2 — odoo-patterns.yml duplicate pattern-not (pre-existing)
diff -q ...        # PASS — fixtures match source
```

### 8. Validation Results

- Fixture copy verification: **PASS**
- `make semgrep-test`: **FAIL** (blocked by pre-existing config validation error in protected `.semgrep/odoo-patterns.yml`)
- Unauthorized file changes: **NONE**

### 9. Invariants Check

| Invariant | Status |
|-----------|--------|
| Only locked files changed | VERIFIED |
| Three fixtures at `.semgrep/tests/` | VERIFIED |
| `semgrep-test` target exists once | VERIFIED |
| No app code changed | VERIFIED |
| No GitHub Actions changed | VERIFIED |
| No stubs/placeholders introduced | VERIFIED |

### 10. Final Declaration

Phases 0-6 complete. No assumptions. No drift.

---

## Commit Message (when requested)

```
[semgrep] test: add rule fixtures and local validation target
```

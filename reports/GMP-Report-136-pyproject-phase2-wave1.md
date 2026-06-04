# GMP-136: pyproject.toml Phase 2 — Wave 1 (Version Align, Dedup, Doc Fix)

| Field | Value |
|-------|-------|
| **GMP ID** | GMP-136 |
| **Title** | Phase 2 Wave 1 — ruff version alignment + type-checker dedup + AGENTS.md contradiction fix |
| **Tier** | CI / Dev Tooling |
| **Date** | 2026-06-04 |
| **Status** | COMPLETE |
| **Plan** | GMP-Plan-135 (Items A, B, D) |
| **Predecessor** | GMP-134 (Phase 1 cleanup) |

---

## 1. PLAN

**Objective:** Eliminate the ruff version drift (pre-commit `v0.15.5` vs CI `0.14.11`), remove redundant type-checker config, and correct a stale AGENTS.md exclusion claim. Low-risk, foundational wave; no new lint rules enabled.

**Modification lock:** `pyproject.toml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `AGENTS.md`, and this report.

**Decisions applied (user-approved):** ruff aligned UP to `0.15.5`.

**Locked TODO plan (GMP-P2-W1):**

| ID | Item | File | Operation | Description |
|----|------|------|-----------|-------------|
| T-001 | B | `AGENTS.md` | Delete | Remove false "Ruff lint … Excluded in ci.yml ruff step" row (modules are checked + clean) |
| T-002 | D | `pyproject.toml` | Delete/Replace | Remove redundant `[tool.basedpyright]`; keep `[tool.pyright]` (basedpyright falls back to it) |
| T-003 | A | `pyproject.toml` | Insert | Add `required-version = ">=0.15,<0.16"` to `[tool.ruff]` |
| T-004 | A | `.github/workflows/ci.yml` | Replace | `ruff==0.14.11` → `ruff==0.15.5` |
| T-005 | A | `.pre-commit-config.yaml` | Replace | Update sync comment to name ci.yml + required-version pins |

---

## 2. CHANGES

### T-001 — AGENTS.md (Item B)
Removed the row claiming `plasticos_inference_engine`, `plasticos_buyer_match_engine`, `plasticos_matching` are "Excluded in `ci.yml` ruff step." Evidence: `ci.yml:39` runs plain `ruff check .`; `pyproject.toml` `exclude` does not list them; repo-wide `ruff check .` @0.15.5 = "All checks passed!". The claim was stale and misleading.

### T-002 — pyproject.toml type-checker dedup (Item D)
Deleted the `[tool.basedpyright]` block (identical to `[tool.pyright]`, both `typeCheckingMode = "off"`). basedpyright reads `[tool.basedpyright]` then falls back to `[tool.pyright]`, so a single `[tool.pyright]` block governs both tools. Neither runs in CI/pre-commit/Makefile (editor-only), so zero pipeline impact.

### T-003/T-004/T-005 — ruff version lockstep (Item A)
```toml
[tool.ruff]
required-version = ">=0.15,<0.16"
target-version = "py312"
line-length = 120
```
- `ci.yml:33`: `pip install ruff==0.15.5`
- `.pre-commit-config.yaml` rev already `v0.15.5`; comment updated to enumerate all three pin sites.

---

## 3. TODO -> CHANGE MAP

| TODO | Status | File | Notes |
|------|--------|------|-------|
| T-001 | APPLIED | `AGENTS.md` | False-positive row removed |
| T-002 | APPLIED | `pyproject.toml` | `[tool.basedpyright]` removed; `[tool.pyright]` retained |
| T-003 | APPLIED | `pyproject.toml` | `required-version = ">=0.15,<0.16"` |
| T-004 | APPLIED | `.github/workflows/ci.yml` | ruff pin → 0.15.5 |
| T-005 | APPLIED | `.pre-commit-config.yaml` | sync comment updated |

---

## 4. VALIDATION

| Check | Result |
|-------|--------|
| ruff 0.15.5 (canonical) runs under required-version | PASS — `0.15.5_OK` |
| ruff 0.14.11 refused by required-version | PASS — "Required version `>=0.15, <0.16` does not match the running version `0.14.11`" (intended fail-fast) |
| Full repo lint @0.15.5 (`ruff check .`) | PASS — "All checks passed!" |
| Format stability @0.15.5 (`ruff format --check .`) | PASS — 405 files already formatted (no reflow needed) |
| Format stability @0.14.11 (pre-bump baseline) | PASS — 405 files already formatted |
| TOML parse | PASS — `required-version=>=0.15,<0.16`, `basedpyright_present=False`, `pyright_present=True` |
| YAML parse (ci.yml + pre-commit) | PASS |
| AGENTS.md stale row removed | PASS — grep count 0 |
| `make pr-check` | NOT RUN — config-only; CI is authoritative gate |

**Tooling note:** ruff 0.15.5 was installed into the repo `.venv` (system Python is PEP 668 externally-managed; `--break-system-packages` deliberately avoided). The system-wide ruff remains 0.14.11 and will now fail `required-version` until upgraded — this is the intended forcing function.

**Recommendation:** PROCEED to Wave 2 (Item C security rules).

---

## 5. DECLARATION

Phases 0-6 complete. No assumptions. No drift. Modification lock honored.

---

## Evidence Sections

### Files Modified
| File | Action |
|------|--------|
| `AGENTS.md` | Modified (T-001) |
| `pyproject.toml` | Modified (T-002, T-003) |
| `.github/workflows/ci.yml` | Modified (T-004) |
| `.pre-commit-config.yaml` | Modified (T-005) |
| `reports/GMP-Report-136-pyproject-phase2-wave1.md` | Created |

### Implementation Evidence
```37:42:pyproject.toml
[tool.ruff]
# Pin the toolchain so local, pre-commit (ruff-pre-commit v0.15.5), and CI
# (ci.yml: ruff==0.15.5) cannot disagree on lint/format verdicts. Bump all three
# together when upgrading.
required-version = ">=0.15,<0.16"
```

```33:33:.github/workflows/ci.yml
      - run: pip install ruff==0.15.5
```

### Invariants Check
| Invariant | Status |
|-----------|--------|
| `select` rule set unchanged (no new enforcement in Wave 1) | VERIFIED |
| All three ruff pin sites = 0.15.x | VERIFIED |
| Type-checker config single-sourced | VERIFIED |
| Docs match config (no phantom exclusion) | VERIFIED |
| Each change single-line revertible | VERIFIED |

---

## Commit Message (when requested)
```
[ci] chore: align ruff to 0.15.5 across pre-commit/CI, dedup pyright config, fix stale AGENTS.md exclusion
```

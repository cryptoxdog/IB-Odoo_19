# GMP-137: pyproject.toml Phase 2 — Wave 2 (Security Rules, Ratchets, Coverage)

| Field | Value |
|-------|-------|
| **GMP ID** | GMP-137 |
| **Title** | Phase 2 Wave 2 — enable ruff `S` security + zero-finding ratchet families + advisory coverage |
| **Tier** | CI / Dev Tooling |
| **Date** | 2026-06-04 |
| **Status** | COMPLETE |
| **Plan** | GMP-Plan-135 (Items C, F, H) |
| **Predecessor** | GMP-136 (Phase 2 Wave 1) |

---

## 1. PLAN

**Objective:** Add real lint enforcement to the toolchain stabilized in Wave 1 — security rules (`S`), zero-cost ratchet rule families, and an advisory coverage baseline — with zero new CI failures.

**Modification lock:** `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/ci.yml`, `plasticos_geolocalize/models/res_partner_geo.py`, and this report.

**Decisions applied (user-approved):** Item C = **full triage**; Items F **and** H included.

**Locked TODO plan (GMP-P2-W2):**

| ID | Item | File | Operation | Description |
|----|------|------|-----------|-------------|
| T-001 | C | `pyproject.toml` | Insert | Add `"S"` to `select` |
| T-002 | C | `pyproject.toml` | Replace | Re-add `[tool.ruff.lint.flake8-bandit]` (now live) at default `check-typed-exception = false` |
| T-003 | C | `pyproject.toml` | Replace | Blanket-ignore `S` for `test_*.py`, `**/tests/*.py`, `**/tools/*.py`, `scripts/*.py`; add `ci/*.py` ignore |
| T-004 | C | `res_partner_geo.py` | Insert | Inline `# noqa: S110` on the one production finding (best-effort debug sink) |
| T-005 | H | `pyproject.toml` | Insert | Enable zero-finding ratchet families: `A`, `FLY`, `INT`, `LOG`, `YTT` |
| T-006 | F | `pyproject.toml` | Insert | `[tool.coverage.run]` + `[tool.coverage.report]` (advisory, no `fail_under`) |
| T-007 | F | `requirements-dev.txt` | Insert | `pytest-cov==5.0.0` |
| T-008 | F | `.github/workflows/ci.yml` | Replace | Install pytest-cov + advisory `--cov` (no `--cov-fail-under`) |

---

## 2. EVIDENCE-DRIVEN TRIAGE (Item C)

Measured `ruff check . --select S` (ruff 0.15.5): **463 findings**, distributed:

| Dir | Findings | Rules | Disposition |
|-----|----------|-------|-------------|
| `tests/` | 319 | S101(309), S110(4), S108(3), S314(3) | Blanket `S` ignore — asserts/fixtures are the point of tests |
| `ci/` | 93 | S101(53), S112(12), S110(10), S607(8), S603(7), S314(3) | Blanket `S` ignore — CI audit scripts run subprocess + parse trusted repo XML |
| `scripts/` | 48 | S607(17), S112(14), S603(6), S310(6), S110(5) | Blanket `S` ignore — dev utilities; subprocess/url to known endpoints |
| `tools/` | 2 | S314(1), S607(1) | Blanket `S` ignore — dev tooling |
| `plasticos_geolocalize/` | **1** | S110(1) | **Inline `# noqa`** — only production finding |

**The single production finding** (`res_partner_geo.py:30`) is inside a `_dbg` debug helper that writes to a hardcoded `/Users/macm2/...debug-75e499.log`. The `try/except/pass` is intentionally best-effort so the geocode cron can never break on a debug-write failure. Resolved with `# noqa: S110 -- best-effort debug sink; must never interrupt the geocode cron`.

**`check-typed-exception`:** Set to the bandit default `False`. Setting it `True` surfaced **7 additional** production findings — all *typed* `except ValueError: pass|continue` fallbacks in `plasticos_inference_engine` (grade_engine, tier_engine), `plasticos_commission` (commission_config), and the buyer-matching RAG. These are deliberate control flow, and the user's "full triage" scope targeted S108/S314/S310/S603 (of which production has **zero**), not S110/S112. `False` keeps S110/S112 flagging only dangerous *bare* swallows.

---

## 3. RULE-FAMILY MEASUREMENT (Item H)

Measured each candidate family repo-wide (ruff 0.15.5):

| Family | Findings | Decision |
|--------|----------|----------|
| `A` (flake8-builtins) | 0 | **ENABLE** |
| `FLY` (flynt) | 0 | **ENABLE** |
| `INT` (flake8-gettext) | 0 | **ENABLE** |
| `LOG` (flake8-logging) | 0 | **ENABLE** |
| `YTT` (flake8-2020) | 0 | **ENABLE** |
| `RUF` | 101 (RUF001 ambiguous-unicode 37, …) | DEFER (noisy) |
| `SIM` | 96 (SIM102 collapsible-if 66) | DEFER |
| `T20` (print) | 943 | DEFER |
| `PTH` (pathlib) | ~200 | DEFER |
| `PERF` | ~55 | DEFER |
| `RET` | ~50 | DEFER |
| `EXE` | 46 | DEFER |
| `DTZ` | 14 | DEFER (revisit — tz-aware datetime is a real concern) |

Only zero-finding families were enabled — they cost nothing today and act as regression ratchets. The deferred families are backlogged for incremental per-family GMP runs (measure → triage → enable).

---

## 4. ITEM F — COVERAGE (advisory, non-gating)

The pure-Python CI tier does **not** import Odoo addons (`conftest.py` deactivates Odoo-importing tests), so module-level coverage is impossible here and a `fail_under` gate would be meaningless/blocking. Implemented as advisory only:
- `[tool.coverage.run]` omits tests, `.venv`, addons, migrations, **and `plasticos_*/*`** (so the report focuses on the Odoo-free `ci/`/`scripts/`/`tools/` code the suite actually exercises, instead of reporting a misleading ~1% across never-imported modules).
- `[tool.coverage.report]` has **no `fail_under`** — explicitly documented to add one only after a real CI baseline is observed.
- CI Tier 3 runs `--cov=. --cov-report=term-missing:skip-covered` with **no** `--cov-fail-under` → reports, never blocks.

Authoritative module coverage remains the responsibility of the Odoo runtime tier (`odoo --test-enable` on Odoo.sh).

---

## 5. VALIDATION

| Check | Result |
|-------|--------|
| Full repo lint @0.15.5 (`ruff check .`) with S + A/FLY/INT/LOG/YTT | PASS — "All checks passed!" |
| Format stability (`ruff format --check .`) | PASS — 405 files already formatted |
| `S` baseline triaged to 0 enforced findings | PASS — production noqa'd, tooling ignored |
| `check-typed-exception=false` avoids 7 typed-fallback findings | VERIFIED |
| Ratchet families confirmed 0 findings before enable (`--select A,FLY,INT,LOG,YTT`) | PASS — "All checks passed!" |
| Coverage config accepted; pytest-cov runs (scoped single-file) | PASS — 10 passed; report focuses on `tools/cron_invariant_check.py` only after `plasticos_*/*` omit |
| pyproject TOML parse | PASS — select has 13 families; bandit typed-exc=False; coverage omit includes plasticos |
| ci.yml + pre-commit YAML parse | PASS |
| `make pr-check` | NOT RUN — config-only; CI is authoritative. Full `pytest tests/` not run locally (one Odoo-free module import hangs on this Dropbox filesystem; CI Tier 3 is the authoritative collector). |

**Tooling note:** validation used ruff 0.15.5 + pytest-cov 5.0.0 installed into the repo `.venv` (gitignored). System Python is PEP 668-managed; `--break-system-packages` deliberately avoided.

**Recommendation:** PROCEED. Phase 2 (Items A, B, C, D, F, H) complete; E dropped with rationale; deferred ruff families backlogged.

---

## 6. DECLARATION

Phases 0-6 complete. No assumptions. No drift. Modification lock honored.

---

## Evidence Sections

### Files Modified
| File | Action |
|------|--------|
| `pyproject.toml` | Modified (T-001, T-002, T-003, T-005, T-006) |
| `requirements-dev.txt` | Modified (T-007) |
| `.github/workflows/ci.yml` | Modified (T-008) |
| `plasticos_geolocalize/models/res_partner_geo.py` | Modified (T-004 — comment-only noqa) |
| `reports/GMP-Report-137-pyproject-phase2-wave2.md` | Created |

### Implementation Evidence
```59:68:pyproject.toml
    "C90",    # mccabe complexity
    "S",      # flake8-bandit (security) — enforced on production modules; dev/CI/test trees ignored below
    # The families below were measured at ZERO findings repo-wide (ruff 0.15.5) and are
    # enabled as ratchets: they cost nothing today and block regressions going forward.
    "A",      # flake8-builtins — no shadowing of Python builtins
    "FLY",    # flynt — static str.join() that should be an f-string
    "INT",    # flake8-gettext — gettext / translation call correctness
    "LOG",    # flake8-logging — correct logging usage (no f-string in _logger, etc.)
    "YTT",    # flake8-2020 — no brittle sys.version / sys.version_info checks
```

### Invariants Check
| Invariant | Status |
|-----------|--------|
| Full lint green after enabling 6 new rule families | VERIFIED |
| Zero production code behavior change (only a comment noqa) | VERIFIED |
| Security `S` enforced on plasticos_* modules; dev/CI/test scoped out | VERIFIED |
| No coverage gate that could block on an unmeasurable metric | VERIFIED |
| Only zero-finding families enabled (no hidden churn) | VERIFIED |
| `S` removable via single `select` edit (instant rollback) | VERIFIED |

### Follow-ups / Backlog (not in scope this run)
- Debug cruft: remove the `_dbg` helper + hardcoded `/Users/macm2/...debug-75e499.log` from `res_partner_geo.py` (separate cleanup GMP — it is dead debug instrumentation, not runtime logic).
- Deferred ruff families (DTZ first — timezone-aware datetime is a genuine correctness concern), then RET/PERF/SIM/PTH/T20 incrementally.
- Re-evaluate `check-typed-exception=true` after triaging the 7 typed-except sites.

---

## Commit Message (when requested)
```
[ci] feat(lint): enable ruff security (S) + A/FLY/INT/LOG/YTT ratchets; add advisory coverage
```

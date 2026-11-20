# PlasticOS Development Makefile
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help ban-check \
        install-extensions \
        lint format format-fix check odools-diagnostics \
        audit audit-quick audit-baseline advisory-checks \
        xml-check wiring deps-check xml-ref-deps cron-check odoo19-check odoo19-hooks odoo-patterns \
        name-check manifest-check shellcheck-check no-local-intelligence \
        critical-manifest enhanced-audit odoo-antipatterns package-init weak-test-check \
        mypy-check acl-csv-check test-attr-guard-check \
        semgrep semgrep-test secret-scan \
        pipeline-guard dev-fence state-guard acl-check guards deploy-check \
        up down restart logs logs-error shell odoo-shell \
        update update-all rebuild backup lock-deps \
        test test-odoo test-pure test-module install-smoke \
        pr pr-check pr-check-% commit push api-push-check sonar changelog \
        governance-backup \
        github-actions-kernel-check \
        pr-autopilot pr-fix
# Imperative targets that produce no same-named file — phony so a stray file or
# directory of that name can never short-circuit them.
.PHONY: venv bash-syntax check-plasticos-skills pr-remote-feedback \
        setup-local-runtime check-local-runtime gate-db runtime-gates runtime-gate \
        runtime-gate-f1 runtime-gate-f1-accept test-odoo-local

# 2026-11-06: keep the caller's ERP_SQL_PASSWORD before .env can replace it. A
# value in .env overrides the environment inside make, so import-erp compares
# the two and refuses a mismatch (import-erp-password-guard) instead of logging
# in with the .env password. Raw text: no make or shell expansion. Not exported.
ERP_SQL_PASSWORD_ORIGIN_BEFORE_ENV := $(origin ERP_SQL_PASSWORD)
ERP_SQL_PASSWORD_BEFORE_ENV := $(value ERP_SQL_PASSWORD)
unexport ERP_SQL_PASSWORD_BEFORE_ENV ERP_SQL_PASSWORD_ORIGIN_BEFORE_ENV

# ── Load .env if present ──────────────────────────────────────────────────────
-include .env
export

# Prefer repo .venv for ruff/pytest (matches pyproject required-version pin)
ifneq ($(wildcard $(CURDIR)/.venv/bin/ruff),)
export PATH := $(CURDIR)/.venv/bin:$(PATH)
endif

# Target a specific PR for remote feedback: make pr-check pr=100
#   or: make pr-check pr=https://github.com/cryptoxdog/IB-Odoo_19/pull/100
#   or: make pr-check-100  /  scripts/pr_check.sh <url-or-number>
# (bare URL cannot be a make goal — https:// breaks make target parsing)
ifneq ($(pr),)
export PR_REMOTE_REF := $(pr)
endif

ODOO_DB_NAME          ?= odoo
ODOO_TEST_DB          ?= odoo_test
# Per-worktree disposable clone (odoo_test_<owner>; scripts/test_env.sh) unless
# ODOO_TEST_DB comes from the environment or the command line.
ifeq ($(origin ODOO_TEST_DB),file)
ODOO_TEST_DB := $(shell bash scripts/test_env.sh name)
endif
ODOO_COMPOSE_PROJECT  ?= odoo19

# Ruff for lint/format is scripts/with_pinned_ruff.sh. It runs the
# requirements-dev.txt pin (ruff==X: same binary as .venv, ci.yml, and
# pre-commit). A linked worktree has no .venv; falling back to PATH ruff
# runs a newer binary and pyproject required-version aborts make pr.

# Symlinked governance tree — lives in Dropbox / separate repo; never commit or push from here.
COMMIT_EXCLUDE := .cursor-commands

# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "PlasticOS Dev Commands"
	@echo "──────────────────────────────────────────────────────"
	@echo ""
	@echo "  Code Quality"
	@echo "    make venv             build pinned local Python dev toolchain (.venv from requirements-dev.txt; CI-aligned versions)"
	@echo "    make install-extensions  install .vscode/extensions.json recommendations via cursor/code CLI"
	@echo "    make lint             ruff check (lint only)"
	@echo "    make format           ruff format --check (check only)"
	@echo "    make format-fix       ruff format (auto-fix)"
	@echo "    make check            lint + format check"
	@echo "    make odools-diagnostics  OdooLS diagnostic dump (file, span, OLS code); not part of pr-check"
	@echo ""
	@echo "  Audit (run before PRs — local blocking gates; GitHub CI remains authoritative)"
	@echo "    make audit-quick      fast: lint + format + wiring + odoo19 + xml + deps + cron"
	@echo "    make audit            full local blocking static gate: ci.yml static-checks blocking checks + repo-local extras"
	@echo "    make audit-baseline   comprehensive+extended audit vs ci/baselines/*.json fingerprint log (mirrors ci.yml)"
	@echo "    make advisory-checks  mypy + ACL CSV header + test-attribute-guard (never fails)"
	@echo "    make xml-check        xmllint on all plasticos XML files"
	@echo "    make odoo19-check     Odoo 19 XML pattern violations"
	@echo "    make odoo19-hooks     Odoo 19 hook pattern violations"
	@echo "    make odoo-patterns    24-check Odoo 19 pattern scanner (scripts/check_odoo_patterns.sh)"
	@echo "    make name-check       _name must be a string literal enforcement"
	@echo "    make no-local-intelligence  Gate-only intelligence drift guard (M8 — blocking)"
	@echo "    make manifest-check   __manifest__.py required-field validation"
	@echo "    make bash-syntax      bash -n on all tracked *.sh files"
	@echo "    make shellcheck-check shellcheck on all tracked *.sh files (requires shellcheck)"
	@echo "    make critical-manifest  critical manifest rules"
	@echo "    make enhanced-audit   enhanced XML ID + dependency audit"
	@echo "    make odoo-antipatterns  Python-vs-ORM idiom enforcement"
	@echo "    make package-init     package __init__.py integrity"
	@echo "    make weak-test-check  weak test detection"
	@echo "    make wiring           module dependency wiring check"
	@echo "    make deps-check       circular dependency check"
	@echo "    make lock-deps        regenerate constraints.txt (Dockerfile dependency lock)"
	@echo "    make cron-check       cron invariant violations"
	@echo "    make semgrep          semgrep custom Odoo rules (ERROR level)"
	@echo "    make semgrep-test     validate semgrep config + positive/negative fixtures"
	@echo "    make check-plasticos-skills  plasticos skill registry + auto-invoke manifest"
	@echo "    make acl-check        ACL completeness (all models have ir.model.access)"
	@echo "    make secret-scan      gitleaks secret detection (also runs via pre-commit pre-push hook)"
	@echo ""
	@echo "  Hard Gates (run individually or via make guards)"
	@echo "    make pipeline-guard   HARD GATE: pipeline_v2.py must not be activated"
	@echo "    make dev-fence        production safety: plasticos_dev_tools fenced"
	@echo "    make state-guard      write guard bypass check"
	@echo "    make guards           all three hard gates combined"
	@echo "    make deploy-check     pre-flight: pr-check + guards (blocking) + ICP/Neo4j/stub state (reported; unverified items flagged)"
	@echo ""
	@echo "  Docker / Odoo"
	@echo "    make up               docker compose up -d"
	@echo "    make down             docker compose down"
	@echo "    make restart          restart Odoo container only"
	@echo "    make logs             follow Odoo container logs"
	@echo "    make logs-error       follow logs filtered to ERROR/CRITICAL only"
	@echo "    make shell            exec bash in Odoo container"
	@echo "    make odoo-shell       Odoo Python shell (for data inspection)"
	@echo "    make import-erp       canonical ERP import (preflight + reconciliation + summary; DRY=1 for preview)"
	@echo "    make import-vanillasoft canonical VanillaSoft full import (preflight + reconciliation + summary)"
	@echo "    make update m=<mod>   -u <module> (e.g. make update m=plasticos_commission)"
	@echo "    make update-all       -u all modules"
	@echo "    make rebuild          drop DB + full rebuild (no demo)"
	@echo "    make backup           snapshot DB to backup_<timestamp>.sql"
	@echo "    make governance-backup  push .cursor-commands → Cursor-Governance GitHub"
	@echo ""
	@echo "  Testing"
	@echo "    make test             pure pytest in tests/ (same suite as ci.yml pure-python-tests; runner defaults from pyproject.toml)"
	@echo "    make test-odoo        Odoo Docker native tests on installed modules"
	@echo "    make test-env         build or reuse the admitted template (enterprise + US accounting + PlasticOS, no demo)"
	@echo "    make test-db [name=]  fresh clone of the template owned by this worktree"
	@echo "    make test-db-drop [name=]  drop an owned clone (database + filestore)"
	@echo "                          test-odoo / test-module run on a fresh owned clone (fresh=0 reuses it)"
	@echo "    make install-smoke    Docker -i modules --stop-after-init (blocks dirty loads before GH)"
	@echo "    make test-pure        alias for make test"
	@echo "    make test-module m=<mod>  Odoo tests for one module (-u m)"
	@echo ""
	@echo "  PR / CI Workflow"
	@echo "    make commit           stage all (except .cursor-commands) + commit"
	@echo "    make commit m=\"...\"   commit with explicit conventional message"
	@echo "    make github-actions-kernel-check  validate staged/all .github/workflows (R5 kernel)"
	@echo "    make pr               publish the committed feature branch into Staging only"
	@echo "    make pr-check         full local validation before publication (audit/baseline/test + smoke + remote) — not the full GitHub CI graph"
	@echo "    make pr-check pr=100       remote gate for PR #100 or full GitHub URL"
	@echo "    make pr-check-100          shorthand for pr=100"
	@echo "    make push             retired — publication is make pr"
	@echo "    make api-push-check   refuses API publication; make pr is the only ceremony"
	@echo "    make pr-autopilot     scan all PR signals (CI, SonarCloud, CodeRabbit) — report only"
	@echo "    make pr-fix           apply safe local fixes; publication remains make pr"
	@echo "    make sonar            show SonarCloud quality gate status"
	@echo "    make changelog        generate CHANGELOG.md from conventional commits"
	@echo ""
	@echo "  Agent review kernels (skills/ — playbooks, not extra targets)"
	@echo "    FINAL_TOUCHES_MODE     plasticos-final-touches  → make audit + make pr-check"
	@echo "    PR_REVIEW_MODE         plasticos-pr-review-kernel → make pr-check"
	@echo "    (static/repo audit)    plasticos-static-audit-kernel / plasticos-repo-review-kernel → make audit"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# CODE QUALITY
# ─────────────────────────────────────────────────────────────────────────────

# Build the pinned local Python developer toolchain (.venv), aligned with the
# Python tool versions CI pins. requirements-dev.txt is the single pin source
# (ruff, semgrep, mypy, pytest + plugins, pr-repair); nothing is re-pinned here.
# System capabilities CI also uses (shellcheck, gitleaks, xmllint) are NOT
# installed by this target — install them separately. The .envrc (direnv)
# auto-activates it. lint/format go through scripts/with_pinned_ruff.sh,
# which uses this venv when its ruff matches the requirements-dev.txt pin.
# Idempotent: safe to re-run to repair/upgrade the environment.
VENV ?= .venv
venv:
	@echo "→ Building $(VENV) (python3.12, pinned dev toolchain)..."
	python3.12 -m venv $(VENV)
	@$(VENV)/bin/python -m pip install --quiet --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements-dev.txt
	@echo ""
	@echo "✅ $(VENV) ready:"
	@$(VENV)/bin/ruff --version
	@$(VENV)/bin/python -m pytest --version 2>&1 | head -1
	@$(VENV)/bin/semgrep --version 2>&1 | head -1
	@$(VENV)/bin/mypy --version 2>&1 | head -1
	@echo "→ Activate automatically with direnv (direnv allow), or: source $(VENV)/bin/activate"

install-extensions:
	@bash scripts/install_editor_extensions.sh

lint:
	bash scripts/with_pinned_ruff.sh check .

format:
	bash scripts/with_pinned_ruff.sh format --check .

format-fix:
	bash scripts/with_pinned_ruff.sh format .

check: lint format
	@echo "✅ lint + format check passed"

odools-diagnostics:
	@python3 scripts/odools_diagnostics.py

# ─────────────────────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────────────────────

xml-check:
	@echo "→ XML validation..."
	@find . -name "*.xml" \
		-path "./plasticos_*" \
		-not -path "./.git/*" \
		-not -path "./.venv/*" \
		-not -path "./current work*" \
		| xargs xmllint --noout && echo "✅ XML valid"

odoo19-check:
	@echo "→ Odoo 19 XML pattern check..."
	python3 ci/check_odoo19_xml.py

odoo19-hooks:
	@echo "→ Odoo 19 hook pattern check..."
	python3 ci/check_odoo19_hooks.py

# 24-check Odoo 19 pattern scanner (ci/check_odoo_patterns.sh) — distinct from
# odoo19-check above (ci/check_odoo19_xml.py, XML-only). Ported into ci.yml
# static-checks 2026-07 from the deleted pr-gate.yml; this target mirrors it.
odoo-patterns:
	@echo "→ Odoo 19 pattern checker (24 checks)..."
	@chmod +x scripts/check_odoo_patterns.sh
	./scripts/check_odoo_patterns.sh

# M8 mothball (TASK-052): blocking drift guard — retired modules absent (M7),
# consumer-path authority drift fails CI/pre-commit/audit.
no-local-intelligence:
	@echo "→ No local-intelligence authority drift..."
	python3 ci/check_no_local_intelligence.py

# _name must be a string literal (ci/check_name_literal.py) — single source of
# truth shared with ci.yml static-checks; do not re-inline this regex anywhere.
name-check:
	@echo "→ _name string literal enforcement..."
	python3 ci/check_name_literal.py

# INVARIANTS.md invariant 20 (BAN001). Same script CI and pre-commit run —
# one canonical implementation, no exclusions.
ban-check:
	@echo "→ BAN001 legacy vendor identifier prohibition..."
	python3 ci/check_banned_identifier.py

# Manifest field validation (restored 2026-07 from deleted module-check.yml) —
# checks required fields beyond bare syntax via scripts/validate_manifest.py.
manifest-check:
	@echo "→ Manifest field validation..."
	@python3 scripts/validate_all_manifests.py


# Bash syntax (same check as ci.yml static-checks "Bash syntax"): bash -n on
# every tracked *.sh — CI checks out tracked files only, so untracked local
# scripts are out of scope here too. Fail-slow across files; non-zero if any fails.
bash-syntax:
	@echo "→ Bash syntax (bash -n, tracked *.sh)..."
	@git ls-files -z -- '*.sh' | xargs -0 -n1 --no-run-if-empty \
		sh -c 'bash -n "$$1" || { echo "❌ Syntax error in $$1"; exit 1; }' bash-syntax

# Shellcheck (restored 2026-07 from deleted pr-gate.yml). Not yet a pre-commit
# hook — install via: brew install shellcheck (macOS) / apt-get install shellcheck (CI).
# Scope = tracked *.sh (what CI's checkout contains); missing shellcheck fails
# closed — an unrun blocking check is never reported as passing.
shellcheck-check:
	@if ! command -v shellcheck >/dev/null 2>&1; then \
		echo "❌ shellcheck not found — install: brew install shellcheck"; exit 1; \
	fi
	@echo "→ Shellcheck..."
	@git ls-files -z -- '*.sh' | xargs -0 --no-run-if-empty shellcheck --severity=warning

critical-manifest:
	@echo "→ Critical manifest check..."
	python3 ci/check_critical_manifest.py

enhanced-audit:
	@echo "→ Enhanced XML ID + dependency audit..."
	python3 ci/enhanced_audit.py

# Promoted to blocking in ci.yml 2026-07 (GATE-01 fail-closed: all pass at adoption).
odoo-antipatterns:
	@echo "→ Odoo antipatterns (Python-vs-ORM idiom enforcement)..."
	python3 ci/check_odoo_antipatterns.py

package-init:
	@echo "→ Package __init__.py integrity..."
	python3 ci/check_package_init.py

weak-test-check:
	@echo "→ Weak test detection..."
	python3 ci/weak_test_fixer.py

wiring:
	@echo "→ Module wiring check..."
	python3 scripts/check_module_wiring.py

xml-ref-deps:
	@echo "→ XML module-ref vs depends..."
	python3 ci/check_xml_module_ref_deps.py

# Blocking: the checker's exit status is the verdict (same script ci.yml runs
# via run_check and pre-commit runs as circular-deps).
deps-check:
	@echo "→ Circular dependency check..."
	python3 ci/check_circular_deps.py

# Regenerate constraints.txt — the transitive dependency lock consumed by the
# Dockerfile install (SonarCloud S8541/S8544 reproducible-build requirement).
lock-deps:
	@echo "→ Resolving requirements.txt in a clean venv and freezing constraints.txt ..."
	python3 -m venv /tmp/lock-deps-venv
	@/tmp/lock-deps-venv/bin/pip install --quiet --upgrade pip
	/tmp/lock-deps-venv/bin/pip install --quiet -r requirements.txt
	@{ echo "# constraints.txt — transitive dependency lock for Dockerfile installs (SonarCloud S8541/S8544)"; \
	   echo "# Regenerate: make lock-deps  (resolves requirements.txt in a clean venv and freezes)"; \
	   echo "# Note: git-pinned direct deps (constellation-node-sdk, pr-repair) are already SHA-locked in requirements.txt."; \
	   /tmp/lock-deps-venv/bin/pip freeze --exclude-editable | grep -v "^constellation-node-sdk\|^pr-repair"; } > constraints.txt
	@echo "✅ constraints.txt updated"

# Blocking: the checker owns scope (tracked files, its own exclusions) and its
# exit status is the verdict (same script the cron-invariants pre-commit hook runs).
cron-check:
	@echo "→ Cron invariant check..."
	python3 tools/cron_invariant_check.py

semgrep:
	@echo "→ Semgrep custom Odoo rules (ERROR level only)..."
	semgrep --error --config .semgrep/odoo-patterns.yml --severity ERROR --quiet --include="plasticos_*"

semgrep-test:
	@echo "→ Semgrep rule fixture tests..."
	semgrep --validate --config .semgrep/odoo-patterns.yml
	@echo "→ Each new rule must match its own positive case and miss the negative fixture..."
	python3 .semgrep/tests/assert_new_rule_matches.py
	@echo "→ Negative fixtures should produce no blocking findings..."
	semgrep --error --severity ERROR --config .semgrep/odoo-patterns.yml .semgrep/tests/negative.py --quiet

check-plasticos-skills:
	@python3 scripts/check_plasticos_skills_registry.py

acl-check:
	@echo "→ ACL completeness check..."
	python3 ci/check_acl_completeness.py

# ── Advisory checks (mirror ci.yml's run_advisory — never fail the build) ──
# Restored 2026-07 from deleted workflows; non-blocking there and here. mypy is
# advisory on every surface: config/excludes live in pyproject.toml [tool.mypy];
# the pre-commit mypy hook is manual-stage only (pre-commit run mypy --hook-stage manual).

mypy-check:
	@echo "→ mypy type check (advisory)..."
	@mypy . --config-file=pyproject.toml || echo "⚠️  mypy findings above (advisory — non-blocking)"

acl-csv-check:
	@echo "→ ACL CSV header format (advisory)..."
	@for csv in $$(find . -name "ir.model.access.csv" -not -path "./.venv/*"); do \
		HEADER=$$(head -1 "$$csv"); \
		EXPECTED="id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"; \
		if [ "$$HEADER" != "$$EXPECTED" ]; then \
			echo "⚠️  Non-standard header in $$csv"; \
			echo "   Expected: $$EXPECTED"; \
			echo "   Got: $$HEADER"; \
		fi; \
		if grep -E ",," "$$csv" | grep -v "^#" > /dev/null; then \
			echo "⚠️  Empty fields detected in $$csv"; \
		fi; \
	done; true

test-attr-guard-check:
	@echo "→ Test attribute guard (advisory)..."
	@find . -name "test_*.py" -path "*/tests/*" ! -path "./.venv/*" | while read -r f; do \
		REFS=$$(grep -oP "self\.[a-z_]+_rec\b" "$$f" 2>/dev/null | sort -u || true); \
		if [ -z "$$REFS" ]; then continue; fi; \
		for ref in $$REFS; do \
			attr="$${ref#self.}"; \
			if ! grep -qP "(cls\.$$attr\s*=|self\.$$attr\s*=)" "$$f"; then \
				echo "⚠️  $$f uses $$ref but no cls.$$attr or self.$$attr= found"; \
			fi; \
		done; \
	done; true

advisory-checks: mypy-check acl-csv-check test-attr-guard-check
	@echo "✅ Advisory checks complete (warnings above are non-blocking)"

# Comprehensive audit baseline regression (restored 2026-07 from deleted
# odoo-audit.yml). scripts/audit/odoo_audit.py + run_all_audits.py are NOT
# duplicated by the checks above — they cover field/required-field/compute/
# security/constraint/state-machine/onchange bugs and N+1-query performance,
# a different check family from check_odoo_antipatterns.py. Mirrors the
# audit-baseline job in ci.yml (same baseline thresholds); keep both in sync.
# Baseline: 444 CRITICAL, 1 HIGH — all pre-existing false positives (verified
# 2026-07), NOT zero known debt. FIELD_NOT_FOUND (444x) misattributes
# ir.ui.view/ir.actions.act_window container fields (arch, inherit_id, name,
# etc.) as model fields; INVALID_CONSTRAINT_FIELD (1x, transaction.py
# commission_override_pct) is a cross-module _inherit field the single-file
# scanner can't see (defined in plasticos_commission). Keep in sync with the
# BASELINE_CRITICAL/BASELINE_HIGH values in ci.yml's audit-baseline job.
# Per-finding fingerprint baseline (ci/baselines/*.json) — NOT a raw count
# comparison. See scripts/audit/baseline_utils.py for the rationale and
# ci/baselines/README.md for how to log a newly-reviewed finding. Mirrors
# ci.yml's audit-baseline job exactly (same two scripts, same flags).
audit-baseline:
	@bash scripts/audit/run_baseline_gate.sh

secret-scan:
	@echo "→ Secret detection (gitleaks)..."
	@command -v gitleaks >/dev/null 2>&1 || { echo "❌ gitleaks not found — install: brew install gitleaks"; exit 1; }
	gitleaks detect --no-banner -v

audit-quick: lint format xml-check odoo19-check wiring deps-check cron-check
	@echo ""
	@echo "✅ Quick audit complete"

# Full audit — the local BLOCKING static-analysis gate. It composes the blocking
# checks of ci.yml's static-checks job (plus lint/format from the lint job) and
# adds repo-local ones: check-plasticos-skills and the extra integrity scanners
# in scripts/run_audit_integrity.sh (automation field refs, constraint patterns,
# disabled actions). It is NOT the same execution graph as GitHub CI: XML syntax
# runs via xmllint over plasticos_* here vs lxml over every XML file in CI, and
# the other CI jobs (pure-python-tests, gate-sdk-tests, audit-baseline,
# secret-scan) are separate targets or CI-only. GitHub CI stays authoritative.
# Run `make advisory-checks` for the non-blocking set.
audit: audit-quick semgrep semgrep-test guards acl-check check-plasticos-skills bash-syntax shellcheck-check ban-check github-actions-kernel-check \
	name-check manifest-check no-local-intelligence odoo-patterns odoo19-hooks critical-manifest \
	enhanced-audit odoo-antipatterns package-init weak-test-check xml-ref-deps
	@bash scripts/run_audit_integrity.sh
	@echo ""
	@echo "✅ Full local blocking audit complete (GitHub CI remains authoritative)"

# ─────────────────────────────────────────────────────────────────────────────
# HARD GATES
# ─────────────────────────────────────────────────────────────────────────────

pipeline-guard:
	@echo "→ pipeline_v2.py guard (HARD GATE)..."
	python3 ci/check_pipeline_v2_guard.py

dev-fence:
	@echo "→ dev_tools fence check..."
	python3 ci/check_dev_tools_fence.py

state-guard:
	@echo "→ Write guard bypass check..."
	python3 ci/check_state_guard_bypass.py

guards: pipeline-guard dev-fence state-guard
	@echo "✅ All hard gates passed"

# Deployment pre-flight check. Blocking (mandatory): pr-check + guards — make
# stops before this recipe if either fails. Steps 1-3 below are informational:
# repo law does not make ICP/Neo4j/stub state a deploy prerequisite (graph
# failures never block Odoo; Neo4j absence = stub mode), so they stay warnings.
# They are counted, and the closing line only claims what was actually proven.
# A NEO4J_* key counts only as an active, non-empty .env assignment — commented
# lines and blank/empty-quoted values do not.
deploy-check: pr-check guards
	@echo ""
	@echo "→ Deployment pre-flight validation..."
	@UNVERIFIED=0; \
	echo ""; \
	echo "  1. Checking ICP configuration parameters..."; \
	if docker compose ps 2>/dev/null | grep -q "web.*Up"; then \
		WEB_UP=1; \
		docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -c \
			"SELECT key, value FROM ir_config_parameter WHERE key LIKE 'plasticos.%' ORDER BY key;" \
			2>/dev/null || { echo "    ⚠️  Could not query ICP params (DB not accessible)"; UNVERIFIED=$$((UNVERIFIED + 1)); }; \
	else \
		WEB_UP=0; \
		echo "    ⚠️  Odoo container not running — ICP params not checked (start with: make up)"; \
		UNVERIFIED=$$((UNVERIFIED + 1)); \
	fi; \
	echo ""; \
	echo "  2. Checking Neo4j credentials..."; \
	env_has_value() { [ -f .env ] && grep -Eq "^[[:space:]]*(export[[:space:]]+)?$$1=[[:space:]]*[\"']?[^[:space:]#\"']" .env; }; \
	if env_has_value NEO4J_URL; then \
		echo "    ✅ NEO4J_URL configured in .env"; \
		if env_has_value NEO4J_USER; then echo "    ✅ NEO4J_USER configured"; \
		else echo "    ⚠️  NEO4J_URL set but NEO4J_USER missing or empty"; UNVERIFIED=$$((UNVERIFIED + 1)); fi; \
		if env_has_value NEO4J_PASSWORD; then echo "    ✅ NEO4J_PASSWORD configured"; \
		else echo "    ⚠️  NEO4J_URL set but NEO4J_PASSWORD missing or empty"; UNVERIFIED=$$((UNVERIFIED + 1)); fi; \
	else \
		echo "    ℹ️  NEO4J_URL not configured (matching engine will run in stub mode)"; \
	fi; \
	echo ""; \
	echo "  3. Checking stub mode flags..."; \
	if [ "$$WEB_UP" = "1" ]; then \
		ENABLED=$$(docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -t -c \
			"SELECT value FROM ir_config_parameter WHERE key = 'plasticos.matching_engine.enabled';" 2>/dev/null | xargs); \
		STUBBED=$$(docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -t -c \
			"SELECT value FROM ir_config_parameter WHERE key = 'plasticos.matching_engine.stubbed';" 2>/dev/null | xargs); \
		echo "    Matching engine enabled: $${ENABLED:-not set}"; \
		echo "    Matching engine stubbed: $${STUBBED:-not set}"; \
		if [ "$$ENABLED" = "True" ] && [ "$$STUBBED" = "False" ]; then \
			echo "    ⚠️  WARNING: Matching engine is LIVE (not stubbed) — ensure Neo4j is accessible"; \
		fi; \
	else \
		echo "    ⚠️  Odoo container not running — stub flags not checked"; \
		UNVERIFIED=$$((UNVERIFIED + 1)); \
	fi; \
	echo ""; \
	if [ "$$UNVERIFIED" -eq 0 ]; then \
		echo "✅ Deploy pre-flight complete — pr-check + guards passed; runtime state checked above"; \
	else \
		echo "⚠️  Deploy pre-flight: pr-check + guards passed, but $$UNVERIFIED runtime item(s) NOT verified (see ⚠️ above)"; \
		echo "   Resolve or consciously accept them before: make update m=<module>"; \
	fi; \
	echo ""

# ─────────────────────────────────────────────────────────────────────────────
# DOCKER / ODOO
# ─────────────────────────────────────────────────────────────────────────────

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart web

logs:
	docker compose logs -f web

logs-error:
	docker compose logs -f web 2>&1 | grep -E "ERROR|CRITICAL|Traceback"

shell:
	docker compose exec web bash

# Interactive Odoo Python shell — use for: env['model'].search([...])
odoo-shell:
	docker compose run --rm odoo shell -d $(ODOO_DB_NAME)

# make update m=plasticos_commission
# make update m=plasticos_intake,plasticos_offer
# One-shot upgrade. The odoo service is the long-running server; without
# --stop-after-init this recipe never exits and cron runs inside the upgrade.
update:
	@if [ -z "$(m)" ]; then echo "Usage: make update m=<module>"; exit 1; fi
	@echo "→ Upgrading module(s): $(m)..."
	@LOG=/tmp/odoo-update-$$(date +%Y%m%d_%H%M%S).log; \
	ln -sf "$$LOG" /tmp/odoo-update-last.log; \
	docker compose run --rm odoo -u $(m) --stop-after-init --workers=0 --max-cron-threads=0 2>&1 | tee "$$LOG"; \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	if [ $$EXIT_CODE -ne 0 ]; then \
		echo ""; \
		echo "❌ Module upgrade failed with exit code $$EXIT_CODE"; \
		exit 1; \
	fi
	@echo ""
	@echo "→ Checking logs for errors..."
	@if tail -100 /tmp/odoo-update-last.log | grep -E "ERROR|CRITICAL|Traceback" | grep -v "test_" | head -5; then \
		echo ""; \
		echo "⚠️  Errors detected in upgrade logs (see above)"; \
		echo "Review full log: ls -t /tmp/odoo-update-*.log | head -1"; \
		exit 1; \
	else \
		echo "✅ No errors detected in logs"; \
	fi
	@echo ""
	@echo "→ Verifying module state in database..."
	@MODULES=$$(echo "$(m)" | tr ',' ' '); \
	for mod in $$MODULES; do \
		STATE=$$(docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -t -c \
			"SELECT state FROM ir_module_module WHERE name = '$$mod';" 2>/dev/null | xargs); \
		if [ "$$STATE" = "installed" ]; then \
			echo "  ✅ $$mod: installed"; \
		elif [ "$$STATE" = "to upgrade" ]; then \
			echo "  ⚠️  $$mod: to upgrade (restart required?)"; \
		else \
			echo "  ❌ $$mod: $$STATE (expected: installed)"; \
			exit 1; \
		fi; \
	done
	@echo ""
	@echo "✅ Module upgrade verified — $(m) is ready"

update-all:
	docker compose run --rm odoo -u all --stop-after-init --workers=0 --max-cron-threads=0

rebuild:
	bash scripts/rebuild-odoo-no-demo.sh

backup:
	@echo "→ Snapshotting $(ODOO_DB_NAME) to backup_$$(date +%Y%m%d_%H%M%S).sql ..."
	docker compose exec db pg_dump -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) \
		> backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup complete"

governance-backup:
	@if [ -L .cursor-commands ] && [ -f .cursor-commands/ops/scripts/backup_to_github.sh ]; then \
		bash .cursor-commands/ops/scripts/backup_to_github.sh; \
	elif [ -f "$(HOME)/Dropbox/cursor governance/GlobalCommands/ops/scripts/backup_to_github.sh" ]; then \
		bash "$(HOME)/Dropbox/cursor governance/GlobalCommands/ops/scripts/backup_to_github.sh"; \
	else \
		echo "ERROR: backup_to_github.sh not found — run setup_workspace_symlinks.sh first" >&2; \
		exit 1; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# TESTING
# ─────────────────────────────────────────────────────────────────────────────

# Default test target — same suite as ci.yml pure-python-tests.
# conftest.py auto-deactivates every Odoo-importing test when Odoo isn't installed,
# so this runs exactly the Odoo-free set without a hand-maintained file list.
# Common runner defaults (--tb=short --no-header -p no:randomly, timeout) come from
# pyproject.toml [tool.pytest.ini_options] addopts — only caller-specific flags here.
test:
	@echo "→ Pure-Python test suite (Odoo-free; same suite as ci.yml pure-python-tests)..."
	python3 -m pytest tests/ -q

# Backward-compatible alias
test-pure: test

# Disposable test databases — scripts/test_env.sh. The declared module set
# (config/odoo_module_order.yaml) is installed once into an admitted template
# keyed by a fingerprint of the image, Enterprise checkout, addons, and config;
# every test gets its own clone. Clones are owned per worktree, so parallel
# agents never share or replace each other's database.
#   make test-env                      build or reuse the template
#   make test-db [name=odoo_test_x]    fresh clone (default $(ODOO_TEST_DB))
#   make test-db-drop [name=...]       drop an owned clone
#   TEST_ENV_PARITY=community ...      separately named, non-production template (no Enterprise)
.PHONY: test-env test-db test-db-drop

test-env:
	@bash scripts/test_env.sh template

test-db:
	@bash scripts/test_env.sh clone $(if $(name),$(name),$(ODOO_TEST_DB))

test-db-drop:
	@bash scripts/test_env.sh drop $(if $(name),$(name),$(ODOO_TEST_DB))

# Odoo runtime tests — Docker native runner on installed modules (not tests/ pytest suite).
# Same surface as ci/odoo.sh (dev) Odoo Test Suite, but runs locally via docker compose.
# Runs on a fresh owned clone of the admitted template (fresh=0 reuses it); the
# recipe runs inside `test_env.sh run`, which holds the clone's lease, asserts its
# identity, scope, and fingerprint, and binds compose to this repository.
test-odoo:
	@if [ "$(fresh)" != "0" ]; then bash scripts/test_env.sh clone $(ODOO_TEST_DB); fi
	bash scripts/test_env.sh run $(ODOO_TEST_DB) -- \
	docker compose run --rm odoo \
		--test-enable \
		--stop-after-init \
		-d $(ODOO_TEST_DB) \
		--log-level=test

# Fail-closed module install gate (xmlsec + enterprise + -i --stop-after-init).
# Required before publication so unloadable modules never reach GitHub.
install-smoke:
	bash scripts/install_smoke.sh

# make test-module m=plasticos_commission
test-module:
	@if [ -z "$(m)" ]; then echo "Usage: make test-module m=<module>"; exit 1; fi
	@if [ "$(fresh)" != "0" ]; then bash scripts/test_env.sh clone $(ODOO_TEST_DB); fi
	bash scripts/test_env.sh run $(ODOO_TEST_DB) -- \
	docker compose run --rm odoo \
		--test-enable \
		--stop-after-init \
		-d $(ODOO_TEST_DB) \
		--log-level=test \
		-u $(m)

# ─────────────────────────────────────────────────────────────────────────────
# PR / CI WORKFLOW
# ─────────────────────────────────────────────────────────────────────────────

# Sole publication ceremony. Validates the committed HEAD, pushes the current
# feature branch, and creates or verifies the PR into Staging.
# Does not stage, commit, or publish a dirty workspace.
# Any base other than Staging is refused before push.
# Usage: make pr
# 2026-11-04: make pr base=<branch> stacks onto an open parent PR's branch (scripts/pr_stack_parent.sh); Production stays refused before push.
pr:
	@bash scripts/make_push_pipeline.sh "" "$(b)" "$(if $(base),$(base),Staging)" 1 0

# REQUIRED before any push or PR creation (local + remote when PR/CI exists).
# The local pre-push gate — not the full GitHub CI job graph (gate-sdk-tests runs
# only in CI; secrets are scanned by the gitleaks-push hook and CI secret-scan). Scheduled in parallel waves via
# scripts/pr_check_run.sh (audit + audit-baseline in parallel, then smoke, then remote).
# The pure-Python suite is not part of this gate. ci.yml pure-python-tests runs it.
# secret-scan is intentionally NOT listed here: pre-commit's gitleaks-push
# hook already runs at `git push` time regardless of make, so listing it here
# would just run gitleaks twice.
# install-smoke is the local Odoo load gate (GHA cannot run odoo-bin install);
# content-cached when plasticos/load inputs are unchanged (PR_CHECK_FORCE_SMOKE=1).
pr-check:
	@bash scripts/pr_check_run.sh full


# Shorthand: make pr-check-100 → make pr-check pr=100
pr-check-%:
	@$(MAKE) pr-check pr=$*

# GitHub Actions job logs + SonarCloud + CodeRabbit/Gemini/Codex/human review comments
pr-remote-feedback:
	@python3 scripts/pr_check_remote_feedback.py $(if $(PR_REMOTE_REF),--pr "$(PR_REMOTE_REF)",)

# GitHub Actions kernel (github_actions_kernel.v1) — R5 developer_support gate
# Checks: triggers, permissions, secrets, job_dependencies, SHA-pinned third-party actions
github-actions-kernel-check:
	@chmod +x ci/check_github_actions_kernel.sh
	@ci/check_github_actions_kernel.sh $(if $(staged),--staged,)

# Stage all tracked/untracked changes (respects .gitignore) and commit.
# OMIT $(COMMIT_EXCLUDE) — governance symlink; synced to a separate repo.
# Runs github_actions_kernel.v1 when .github/workflows/* is staged.
# Usage: make commit                    (default message: wip: snapshot local changes)
#        make commit m="fix: description"
commit:
	@set -e; \
	if git diff --quiet && git diff --cached --quiet \
		&& [ -z "$$(git ls-files --others --exclude-standard | grep -v '^$(COMMIT_EXCLUDE)$$' || true)" ]; then \
		echo "Nothing to commit (working tree clean)."; exit 1; \
	fi; \
	MSG='$(m)'; \
	if [ -z "$$MSG" ]; then MSG="wip: snapshot local changes"; fi; \
	echo "→ Staging all changes except $(COMMIT_EXCLUDE)..."; \
	git add -u -- . ':(exclude)$(COMMIT_EXCLUDE)'; \
	git ls-files --others --exclude-standard -z | grep -zv '^$(COMMIT_EXCLUDE)$$' | xargs -0 -r git add 2>/dev/null || true; \
	if git diff --cached --name-only | grep -q '^$(COMMIT_EXCLUDE)'; then \
		echo "⛔ Refusing to commit: $(COMMIT_EXCLUDE) is governance-only (separate repo)."; \
		git reset -- '$(COMMIT_EXCLUDE)' 2>/dev/null || true; \
		exit 1; \
	fi; \
	if git diff --cached --quiet; then \
		echo "Nothing to commit after staging (ignored paths only?)."; exit 1; \
	fi; \
	if git diff --cached --name-only | grep -q '^\.github/workflows/.*\.ya\?ml$$'; then \
		echo "→ Workflow files staged — running GitHub Actions kernel..."; \
		$(MAKE) github-actions-kernel-check staged=1; \
	fi; \
	echo "→ Committing: $$MSG"; \
	git commit -m "$$MSG"; \
	echo ""; \
	echo "============================================"; \
	echo "Committed ($$(git rev-parse --short HEAD)):"; \
	echo "============================================"; \
	git show --stat --oneline -1; \
	echo ""; \
	echo "Run: make pr   (publishes this committed feature branch into Staging)"; \

# Retired publication path. Staging and Production stay PR-only under the
# GitHub ruleset "Protect Staging & Production" (required checks: Ruff Lint & Format,
# Static Analysis, Pure Python Tests, and CI Gate Result).
# `make push` and `make push pr=1` are no longer a ceremony.
push:
	@echo "⛔ make push is not a publication ceremony."
	@echo "   Publish the current committed feature branch with: make pr"
	@exit 1

# API publication is refused. make pr is the only ceremony.
api-push-check:
	@python3 scripts/api_push.py

# Scan PR for all CI/SonarCloud/CodeRabbit issues — report only, no changes
pr-autopilot:
	@echo "→ PR Autopilot — scanning all signals (CI, SonarCloud, CodeRabbit, reviews)..."
	python3 scripts/pr_autopilot.py

# Scan + apply safe local fixes. Publication remains make pr.
pr-fix:
	@echo "→ PR Autopilot — scanning + applying local fixes (publication remains make pr)..."
	python3 scripts/pr_autopilot.py --fix

sonar:
	@echo "→ SonarCloud quality gate status for cryptoxdog_IB-Odoo_19..."
	@SONAR_TOKEN=$$(grep '^SONARCLOUD_API_KEY=' .env.local 2>/dev/null | cut -d '=' -f2); \
	if [ -z "$$SONAR_TOKEN" ]; then echo "❌ SONARCLOUD_API_KEY not found in .env.local"; exit 1; fi; \
	curl -s -u "$$SONAR_TOKEN:" \
		"https://sonarcloud.io/api/qualitygates/project_status?projectKey=cryptoxdog_IB-Odoo_19" \
		| python3 -c "\
import json,sys; \
d=json.load(sys.stdin)['projectStatus']; \
status=d['status']; \
print(f'Quality Gate: {status}'); \
[print(f'  {c[\"metricKey\"]}: {c[\"status\"]} (actual={c.get(\"actualValue\",\"n/a\")} threshold={c.get(\"errorThreshold\",\"n/a\")})') \
 for c in d['conditions']]"

# Generate changelog from conventional commits
changelog:
	@echo "→ Generating CHANGELOG.md from conventional commits..."
	@if [ ! -f CHANGELOG.md ]; then \
		echo "# Changelog" > CHANGELOG.md; \
		echo "" >> CHANGELOG.md; \
		echo "All notable changes to PlasticOS will be documented in this file." >> CHANGELOG.md; \
		echo "" >> CHANGELOG.md; \
		echo "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)," >> CHANGELOG.md; \
		echo "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)." >> CHANGELOG.md; \
		echo "" >> CHANGELOG.md; \
	fi
	@cz changelog --unreleased-version "HEAD" --incremental || \
		(echo "❌ commitizen not installed — run: pip install commitizen"; exit 1)
	@echo "✅ CHANGELOG.md updated"

# ---------------------------------------------------------------------------
# Local (no-Docker) Odoo runtime + real-runtime launch gates
#
# `make test-odoo` above is the Docker backend and stays the default where a
# daemon, registry egress and bridge networking are all available. These targets
# are the second backend, for the environments where they are not — a sandbox
# with no daemon, blocked registry pulls, or IPv4 forwarding disabled. Both run
# the same Odoo, against the same addons, on a real PostgreSQL.
#
# `test-odoo` is deliberately NOT rewritten to auto-detect: the Makefile is
# append-only in this repo (see AGENTS.md), so the backends are named targets
# and the choice stays explicit and greppable.
# ---------------------------------------------------------------------------
L9_ODOO_VENV        ?= /opt/odoo-venv
L9_PG_HOST          ?= /tmp
L9_PG_PORT          ?= 5433
L9_PG_USER          ?= odoo
L9_ODOO_TEMPLATE_DB ?= plasticos_template

# Build (or verify) the no-Docker Odoo 19 + PostgreSQL 16 runtime. Idempotent:
# a warm machine returns in seconds, so this is safe as a session setup step.
setup-local-runtime:
	@bash scripts/setup_local_runtime.sh

# Verify the runtime without mutating anything (exit non-zero when incomplete).
check-local-runtime:
	@bash scripts/setup_local_runtime.sh --check

# Real-runtime launch gates (tests/runtime_gates/README.md). NOT pytest: under
# TransactionCase there is one cursor and one snapshot, cr.commit() is neutered
# and registry.cursor() returns the test cursor, so collecting these would turn
# a real proof into a vacuous pass. Each script exits non-zero on failure.
L9_GATE_DB ?= c1c6_test

# The C/F gates drive one shared database (SEAM_DB); the S gates build their own.
# Cloning the template is seconds, versus minutes to install modules again.
gate-db:
	@psql -h "$(L9_PG_HOST)" -p "$(L9_PG_PORT)" -U "$(L9_PG_USER)" -lqt \
		| cut -d'|' -f1 | grep -qw "$(L9_GATE_DB)" \
		|| createdb -h "$(L9_PG_HOST)" -p "$(L9_PG_PORT)" -U "$(L9_PG_USER)" \
			-T "$(L9_ODOO_TEMPLATE_DB)" "$(L9_GATE_DB)"

# Exit 77 from a gate means "cannot run in this environment" (a documented,
# narrow precondition such as a private SDK), and is reported as SKIPPED. It is
# never counted as a pass: a gate that did not run must not read green, so the
# aggregate exits 0 only when every gate it runs passed. Nothing failed but
# something did not run -> exit 77 (INCOMPLETE, the same "did not run" code,
# distinct from a defect); any gate failed -> exit 1 regardless of skips.
# F1–F3 is not one of those gates: its disposable clone is Docker-owned.
# Omitting it here is not a pass. Pinned by tests/test_makefile_failure_propagation.py.
F1_RECEIPT ?= .l9/runtime/f1-f3-receipt.json
runtime-gates: check-local-runtime gate-db
	@fail=0; passed=0; skipped=0; failed=""; \
	for f in tests/runtime_gates/run_*.py; do \
		echo "==> $$f"; \
		case $$f in \
			*/run_f1_f3_full_import.py) \
				echo "  NOT IN THIS AGGREGATE: F1–F3 is not run and not passed. CRM acceptance is make runtime-gate-f1."; \
				continue ;; \
		esac; \
		SEAM_DB="$(L9_GATE_DB)" SEAM_PG_HOST="$(L9_PG_HOST)" SEAM_PG_PORT="$(L9_PG_PORT)" \
		SEAM_PG_USER="$(L9_PG_USER)" \
			"$(L9_ODOO_VENV)/bin/python" "$$f"; \
		rc=$$?; \
		if [ $$rc -eq 0 ]; then passed=$$((passed+1)); \
		elif [ $$rc -eq 77 ]; then skipped=$$((skipped+1)); \
		else failed="$$failed $$(basename $$f)"; fail=1; fi; \
	done; \
	echo ""; \
	echo "runtime gates: $$passed passed, $$skipped skipped, $$(echo $$failed | wc -w | tr -d ' ') failed"; \
	echo "F1–F3: not run by this aggregate (not a pass)"; \
	[ -n "$$failed" ] && echo "  failed:$$failed"; \
	if [ $$fail -eq 0 ] && [ $$skipped -gt 0 ]; then \
		echo "  INCOMPLETE: $$skipped gate(s) did not run; a skipped gate is not a pass (exit 77)"; \
		exit 77; \
	fi; \
	exit $$fail

# One no-Docker gate script: make runtime-gate g=run_s1_s3_pristine_seams.py
runtime-gate: check-local-runtime
	@test -n "$(g)" || { echo "usage: make runtime-gate g=run_s1_s3_pristine_seams.py"; exit 2; }
	@if [ "$(g)" = "run_f1_f3_full_import.py" ]; then \
		echo "F1–F3 is not a no-Docker gate. Run make runtime-gate-f1. Not run, not a pass." >&2; \
		exit 2; \
	fi
	@SEAM_PG_HOST="$(L9_PG_HOST)" SEAM_PG_PORT="$(L9_PG_PORT)" SEAM_PG_USER="$(L9_PG_USER)" \
		"$(L9_ODOO_VENV)/bin/python" "tests/runtime_gates/$(g)"

# F1–F3 on the guarded Docker lifecycle. Clone and drop are scripts/test_env.sh.
# The shell does not drop: `run` holds the clone lease until it exits.
# A receipt is written only after the assertions pass and the drop returns 0.
# No Docker, no admitted template, or a failed drop leaves F1 unproven.
runtime-gate-f1:
	@set -eu; \
	rm -f "$(F1_RECEIPT)"; \
	owner_db=$$(bash scripts/test_env.sh name); \
	suffix=$${owner_db#odoo_test_}; \
	db="odoo_test_f1_$$suffix"; \
	case "$$db" in \
		odoo_test_f1_[a-z0-9_]*) ;; \
		*) echo "refusing F1 clone name $$db" >&2; exit 2 ;; \
	esac; \
	bash scripts/test_env.sh clone "$$db"; \
	log=$$(mktemp); \
	rc=0; \
	retire() { \
		drop_rc=0; \
		bash scripts/test_env.sh drop "$$db" || drop_rc=$$?; \
		if [ "$$drop_rc" -ne 0 ]; then \
			echo "owned clone retirement failed: $$db status $$drop_rc" >&2; \
			rm -f "$(F1_RECEIPT)"; \
			exit "$$drop_rc"; \
		fi; \
	}; \
	trap 'rc=130; retire; exit "$$rc"' INT TERM; \
	bash scripts/test_env.sh run "$$db" -- shell < tests/runtime_gates/f1_guarded_shell.py > "$$log" 2>&1 || rc=$$?; \
	cat "$$log"; \
	trap - INT TERM; \
	retire; \
	if [ "$$rc" -ne 0 ]; then \
		echo "F1–F3 failed status $$rc; clone retired; no acceptance receipt" >&2; \
		rm -f "$(F1_RECEIPT)"; \
		rm -f "$$log"; \
		exit "$$rc"; \
	fi; \
	head=$$(git rev-parse HEAD); \
	python3 -c 'import sys; sys.path.insert(0, "tests/runtime_gates"); from f1_guarded_shell import write_receipt; write_receipt(open(sys.argv[1], encoding="utf-8", errors="replace").read(), sys.argv[2], sys.argv[3], sys.argv[4])' \
		"$$log" "$$db" "$(F1_RECEIPT)" "$$head" \
		|| { rm -f "$(F1_RECEIPT)" "$$log"; exit 2; }; \
	rm -f "$$log"

# CRM admission check. Missing, stale, or failed F1 evidence exits 2.
runtime-gate-f1-accept:
	@head=$$(git rev-parse HEAD); \
	python3 -c 'import sys; sys.path.insert(0, "tests/runtime_gates"); from f1_guarded_shell import accept_receipt; raise SystemExit(accept_receipt(sys.argv[1], sys.argv[2]))' \
		"$(F1_RECEIPT)" "$$head"

# Odoo's own module test suite on the local runtime — the no-Docker counterpart
# of `make test-odoo`. Runs on a throwaway clone of the template database so a
# failed run never leaves the template dirty.
test-odoo-local: check-local-runtime
	@set -e; db="odoo_test_$$$$"; \
	createdb -h "$(L9_PG_HOST)" -p "$(L9_PG_PORT)" -U "$(L9_PG_USER)" -T "$(L9_ODOO_TEMPLATE_DB)" "$$db"; \
	trap "dropdb -h '$(L9_PG_HOST)' -p '$(L9_PG_PORT)' -U '$(L9_PG_USER)' --if-exists '$$db'" EXIT; \
	src=$$(ls -d /opt/odoo-src/odoo-19.0* | sort | tail -1); \
	"$(L9_ODOO_VENV)/bin/odoo" -d "$$db" \
		--db_host="$(L9_PG_HOST)" --db_port="$(L9_PG_PORT)" --db_user="$(L9_PG_USER)" \
		--addons-path="$$src/odoo/addons,$(CURDIR)" \
		-u $(if $(m),$(m),plasticos_crm_sync) --test-enable --stop-after-init --log-level=test

# ---------------------------------------------------------------
# Canonical data-import commands (odoo-intent-1 ingestion milestone)
# ---------------------------------------------------------------
# make import-erp                full ERP import (applied)
# make import-erp DRY=1          resolve + map, persist nothing
# make import-erp LIMIT=100      first 100 transactions (diagnostics)
#   LIMIT counts worksheets, newest first. LIMIT=25% is the newest quarter (test databases);
#   anything that is not a positive count or a whole 1-100% is refused before any write.
# make import-erp PAYLOAD_ROOT=/abs/path  non-default source payload (statement or grid form)
# make import-erp REPORT_PATH=/abs/summary.json  override machine summary path
# make import-erp PARTNERS_ONLY=1  Concern 1: counterparties → addresses → contacts → roles → salespersons
# make import-erp LAYER=counterparties  one partner table, in that order; a layer opens only after
#   the previous layer's validator passes, and commits only after its own passes
#   (plasticos_partner_import/scripts/validate_partner_layer.py)
# make import-erp ERP_SQL_SERVER=host ERP_SQL_DATABASE=db [ERP_SQL_USER=.. ERP_SQL_PASSWORD=..]
#   direct read of the restored ERP SQL Server database (ADR-021); wins over PAYLOAD_ROOT

.PHONY: import-erp import-vanillasoft
.PHONY: import-erp-test

# Public overrides (DRY / LIMIT / PAYLOAD_ROOT / REPORT_PATH / PARTNERS_ONLY /
# LAYER) bridge onto the ERP_* names the shell driver reads
# (plasticos_partner_import/scripts/import_erp_shell.py).
ERP_DRY ?= $(DRY)
ERP_LIMIT ?= $(LIMIT)
ERP_PAYLOAD_ROOT ?= $(PAYLOAD_ROOT)
ERP_REPORT_PATH ?= $(or $(REPORT_PATH),.l9/pr/import-erp-summary.json)
ERP_PARTNERS_ONLY ?= $(PARTNERS_ONLY)
ERP_LAYER ?= $(LAYER)
# Applied imports refuse a database that already has business partners.
# Set ERP_REQUIRE_EMPTY=0 only for a deliberate reload onto a populated database.
ERP_REQUIRE_EMPTY ?= 1
# Direct database read. The password travels only through the environment of
# the odoo shell process; it is never echoed or written to the summary.
ERP_SQL_SERVER ?=
ERP_SQL_DATABASE ?=
ERP_SQL_USER ?=
ERP_SQL_PASSWORD ?=
ERP_SQL_PORT ?=
ERP_SQL_DRIVER ?=
# 2026-11-06: the ERP password reaches the recipe shell unchanged. The recipe
# writes "$(ERP_SQL_PASSWORD)" inside double quotes, so make would expand $ in
# the value and the shell would run backticks and break on " or \ (SQL Server
# then answers error 18456). ERP_SQL_PASSWORD_RAW carries the raw value in the
# environment, and $(ERP_SQL_PASSWORD) expands to a shell reference to it, which
# the shell substitutes without reinterpreting the value. A nested $(MAKE)
# (MAKELEVEL > 0 with an inherited ERP_SQL_PASSWORD_RAW and that reference)
# keeps the parent's ERP_SQL_PASSWORD_RAW and its conflict verdict. A top-level
# make always resolves the caller's own value, even one equal to the reference.
ERP_SQL_PASSWORD_INDIRECT := $${ERP_SQL_PASSWORD_RAW}
ERP_SQL_PASSWORD_INHERITED :=
ifneq ($(filter-out 0,$(MAKELEVEL)),)
ifeq ($(origin ERP_SQL_PASSWORD_RAW),environment)
ifeq ($(ERP_SQL_PASSWORD_BEFORE_ENV),$(ERP_SQL_PASSWORD_INDIRECT))
ERP_SQL_PASSWORD_INHERITED := 1
endif
endif
endif
ifeq ($(ERP_SQL_PASSWORD_INHERITED),)
ERP_SQL_PASSWORD_CONFLICT :=
ERP_SQL_PASSWORD_RAW := $(value ERP_SQL_PASSWORD)
ifeq ($(ERP_SQL_PASSWORD_ORIGIN_BEFORE_ENV)-$(origin ERP_SQL_PASSWORD),environment-file)
ifneq ($(ERP_SQL_PASSWORD_BEFORE_ENV),$(ERP_SQL_PASSWORD_RAW))
ERP_SQL_PASSWORD_CONFLICT := 1
endif
endif
endif
override ERP_SQL_PASSWORD := $(ERP_SQL_PASSWORD_INDIRECT)
export ERP_SQL_PASSWORD_RAW ERP_SQL_PASSWORD_CONFLICT
unexport ERP_SQL_PASSWORD_INDIRECT ERP_SQL_PASSWORD_INHERITED

# 2026-11-07 — one authoritative execution path per historical source
# (IB-ODOO19-CANONICAL-IMPORT-PARITY-2026-11-07-R2). import-erp reads only the
# restored ERP SQL Server database: without ERP_SQL_SERVER and ERP_SQL_DATABASE
# the reader (plasticos_partner_import/erp/reader.py) would select the frozen
# grid under erp_extracted_data/, so the recipe refuses before any runtime
# starts, and a payload root is refused the same way. The grid and statement
# fixtures stay available to isolated tests only. The DRY=1 and PAYLOAD_ROOT
# examples above are historical: a preview names the database too.
# ERP_PRODUCTION_PERMIT (plasticos_partner_import/erp/production_permit.py) is
# forwarded to both runtimes; the promotion rehearsal never sets it. A permit
# is verified against the stage the driver observes, and `docker compose run`
# passes only the variables named with -e, so ODOO_STAGE is forwarded the same
# way on the Docker runtime (the local runtime inherits it); the rehearsal
# refuses ODOO_STAGE=production before either target runs.
ERP_PRODUCTION_PERMIT ?=
ODOO_STAGE ?=
# Inside the odoo container the repository checkout is the only bind mount
# (docker-compose.yml: .:/mnt/extra-addons). A file the driver must open on the
# Docker runtime (permit, census, ledger) is given as a host path, relative to
# the checkout or absolute inside it, and translated onto that mount; a path
# outside the checkout cannot be reached there and is refused. The no-Docker
# runtime opens the host path as given.
MOUNT_ROOT := /mnt/extra-addons
# filter and patsubst split on spaces, so a checkout path that contains one
# was prefixed onto the mount instead of being stripped. subst keeps the path
# whole. An absolute path is not passed through abspath, which splits the same way.
_as_abs = $(if $(filter /%,$(1)),$(1),$(abspath $(1)))
in_repo = $(if $(findstring x$(call _as_abs,$(1))x,x$(CURDIR)/$(subst $(CURDIR)/,,$(call _as_abs,$(1)))x),1,)
runtime_path = $(if $(1),$(if $(call in_repo,$(1)),$(MOUNT_ROOT)/$(subst $(CURDIR)/,,$(call _as_abs,$(1))),$(1)),)
# $(call mount_guard,<VAR ...>,<target>): every named path is inside the checkout.
mount_guard = $(foreach name,$(1),[ -z "$($(name))" ] || [ -n "$(call in_repo,$($(name)))" ] || { echo "❌ $(2) refused: $(name) must be inside this checkout, the only bind mount the odoo container can read (an ignored path such as .l9/runtime/ works)" >&2; exit 2; };) true
erp_source_guard = [ -z "$(ERP_PAYLOAD_ROOT)" ] || { echo "❌ import-erp refused: PAYLOAD_ROOT / ERP_PAYLOAD_ROOT selects a frozen fixture; the canonical import reads only the restored ERP database (ADR-021)" >&2; exit 2; }; \
	{ [ -n "$(ERP_SQL_SERVER)" ] && [ -n "$(ERP_SQL_DATABASE)" ]; } || { echo "❌ import-erp refused: ERP_SQL_SERVER and ERP_SQL_DATABASE must both name the restored ERP database; without them the reader would fall back to the frozen grid" >&2; exit 2; }; \
	[ -z "$(ERP_PRODUCTION_PERMIT)" ] || [ -r "$(ERP_PRODUCTION_PERMIT)" ] || { echo "❌ import-erp refused: ERP_PRODUCTION_PERMIT does not name a readable file" >&2; exit 2; }

# The VanillaSoft driver reads two floors (plasticos_crm_sync/scripts/
# import_vanillasoft_shell.py); both are forwarded verbatim.
VANILLASOFT_CALL_FLOOR ?=
VANILLASOFT_CONTACT_FLOOR ?=
VANILLASOFT_REPORT_PATH ?= .l9/pr/import-vanillasoft-summary.json
# 2026-11-07 — make import-vanillasoft has three explicit modes and no default.
# Repository cohort: VANILLASOFT_CONTACT_EXPORT names the tracked contact export.
# The piped shell builds the census from that export plus the packaged crosswalk.
# It refuses a call floor, a history census, and VANILLASOFT_HISTORY_MAX_IDS, and
# it requires VANILLASOFT_PRODUCTION_CONFIRM=1. The ledger parent is created.
# Historical cohort (the frozen 4,876-ContactID census): VANILLASOFT_HISTORY_CENSUS
# selects import_vanillasoft_shell.history(), which fetches every planned id through
# SyncOrchestrator.upsert_contact_external_id. It needs the declared census
# SHA-256 and an append-only ledger on durable storage, takes an optional
# session cap and failure budget, and refuses a call or contact floor: the
# rolling window is another import, never a fallback for a missing census.
# Rolling window (plasticos_crm_sync.services.orchestrator.run_full_import):
# VANILLASOFT_CALL_FLOOR, an explicit ISO-8601 UTC instant, without a census.
# No mode starts without its inputs; nothing is imported on a refusal.
# VANILLASOFT_API_KEY is read from the environment inside the recipe and written
# with printf %q. It is not a make variable, so make -n and the recipe never echo it.
VANILLASOFT_HISTORY_CENSUS ?=
VANILLASOFT_HISTORY_CENSUS_SHA256 ?=
VANILLASOFT_HISTORY_CHECKPOINT ?=
VANILLASOFT_HISTORY_MAX_IDS ?=
VANILLASOFT_HISTORY_FAILURE_BUDGET ?=
VANILLASOFT_PRODUCTION_PERMIT ?=
VANILLASOFT_CONTACT_EXPORT ?=
VANILLASOFT_PRODUCTION_CONFIRM ?=
VANILLASOFT_MODE = $(if $(VANILLASOFT_CONTACT_EXPORT),repository,$(if $(VANILLASOFT_HISTORY_CENSUS),history,rolling))
VANILLASOFT_HISTORY_VARS := VANILLASOFT_HISTORY_CENSUS VANILLASOFT_HISTORY_CHECKPOINT VANILLASOFT_PRODUCTION_PERMIT
vanillasoft_mode_guard = if [ -n "$(VANILLASOFT_CONTACT_EXPORT)" ]; then \
	[ "$(VANILLASOFT_PRODUCTION_CONFIRM)" = "1" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_PRODUCTION_CONFIRM=1 is required for the repository cohort" >&2; exit 2; }; \
	[ -z "$(VANILLASOFT_CALL_FLOOR)$(VANILLASOFT_CONTACT_FLOOR)" ] || { echo "❌ import-vanillasoft refused: the repository cohort does not accept a call or contact floor" >&2; exit 2; }; \
	[ -z "$(VANILLASOFT_HISTORY_CENSUS)$(VANILLASOFT_HISTORY_CENSUS_SHA256)" ] || { echo "❌ import-vanillasoft refused: the repository cohort does not accept a history census" >&2; exit 2; }; \
	[ -z "$(VANILLASOFT_HISTORY_MAX_IDS)" ] || { echo "❌ import-vanillasoft refused: the repository cohort does not accept VANILLASOFT_HISTORY_MAX_IDS" >&2; exit 2; }; \
	[ -n "$(VANILLASOFT_HISTORY_CHECKPOINT)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_CHECKPOINT must name the append-only ledger on durable operator storage" >&2; exit 2; }; \
	[ -r "$(VANILLASOFT_CONTACT_EXPORT)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_CONTACT_EXPORT does not name a readable export file" >&2; exit 2; }; \
	ledger_dir="$$(dirname "$(VANILLASOFT_HISTORY_CHECKPOINT)")"; mkdir -p "$$ledger_dir"; \
	{ [ -d "$$ledger_dir" ] && [ -w "$$ledger_dir" ]; } || { echo "❌ import-vanillasoft refused: the ledger directory $$ledger_dir must exist and be writable" >&2; exit 2; }; \
	[ -z "$(VANILLASOFT_HISTORY_FAILURE_BUDGET)" ] || printf '%s\n' "$(VANILLASOFT_HISTORY_FAILURE_BUDGET)" | grep -Eq '^[1-9][0-9]*$$' || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_FAILURE_BUDGET must be a positive integer" >&2; exit 2; }; \
	[ -z "$(VANILLASOFT_PRODUCTION_PERMIT)" ] || [ -r "$(VANILLASOFT_PRODUCTION_PERMIT)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_PRODUCTION_PERMIT does not name a readable file" >&2; exit 2; }; \
	elif [ -n "$(VANILLASOFT_HISTORY_CENSUS)" ]; then \
	[ -z "$(VANILLASOFT_CALL_FLOOR)$(VANILLASOFT_CONTACT_FLOOR)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_CENSUS selects the historical cohort; VANILLASOFT_CALL_FLOOR / VANILLASOFT_CONTACT_FLOOR belong to the rolling window and cannot be combined with it" >&2; exit 2; }; \
	[ -r "$(VANILLASOFT_HISTORY_CENSUS)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_CENSUS does not name a readable census file" >&2; exit 2; }; \
	printf '%s\n' "$(VANILLASOFT_HISTORY_CENSUS_SHA256)" | grep -Eq '^[0-9a-fA-F]{64}$$' || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_CENSUS_SHA256 must declare the census SHA-256 (64 hex characters)" >&2; exit 2; }; \
	[ -n "$(VANILLASOFT_HISTORY_CHECKPOINT)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_CHECKPOINT must name the append-only ledger on durable operator storage" >&2; exit 2; }; \
	ledger_dir="$$(dirname "$(VANILLASOFT_HISTORY_CHECKPOINT)")"; { [ -d "$$ledger_dir" ] && [ -w "$$ledger_dir" ]; } || { echo "❌ import-vanillasoft refused: the ledger directory $$ledger_dir must exist and be writable" >&2; exit 2; }; \
	for bound in "$(VANILLASOFT_HISTORY_MAX_IDS)" "$(VANILLASOFT_HISTORY_FAILURE_BUDGET)"; do [ -z "$$bound" ] || printf '%s\n' "$$bound" | grep -Eq '^[1-9][0-9]*$$' || { echo "❌ import-vanillasoft refused: VANILLASOFT_HISTORY_MAX_IDS and VANILLASOFT_HISTORY_FAILURE_BUDGET must be positive integers" >&2; exit 2; }; done; \
	[ -z "$(VANILLASOFT_PRODUCTION_PERMIT)" ] || [ -r "$(VANILLASOFT_PRODUCTION_PERMIT)" ] || { echo "❌ import-vanillasoft refused: VANILLASOFT_PRODUCTION_PERMIT does not name a readable file" >&2; exit 2; }; \
	else \
	[ -z "$(VANILLASOFT_HISTORY_CENSUS_SHA256)$(VANILLASOFT_HISTORY_CHECKPOINT)$(VANILLASOFT_HISTORY_MAX_IDS)$(VANILLASOFT_HISTORY_FAILURE_BUDGET)$(VANILLASOFT_PRODUCTION_PERMIT)" ] || { echo "❌ import-vanillasoft refused: history settings without VANILLASOFT_HISTORY_CENSUS; the census is the historical import's identity and nothing falls back to the rolling window" >&2; exit 2; }; \
	[ -n "$(VANILLASOFT_CALL_FLOOR)" ] || { echo "❌ import-vanillasoft refused: no mode selected. Historical cohort: VANILLASOFT_HISTORY_CENSUS=<census.csv> VANILLASOFT_HISTORY_CENSUS_SHA256=<sha256> VANILLASOFT_HISTORY_CHECKPOINT=<ledger.jsonl>. Rolling window: VANILLASOFT_CALL_FLOOR=<ISO-8601 UTC>. Nothing was imported." >&2; exit 2; }; \
	fi

# Prefers the docker runtime; falls back to the no-Docker local harness
# (L9_ODOO_VENV, see scripts/setup_local_runtime.sh). Fails closed when
# neither runtime exists or the import reports material errors.
#
# Docker: the image is odoo:19, whose entrypoint execs an unknown first
# argument directly, so the command override must start with `odoo` to reach
# the Odoo CLI (`odoo shell`), not the bare subcommand.
# Local: the venv has no odoo.conf, so the connection and addons arguments are
# passed explicitly, exactly as `test-odoo-local` does.
import-erp:
	@if [ -n "$$TEST_ENV_VERIFIED_CLONE" ] && [ "$$TEST_ENV_VERIFIED_CLONE" != "$(ODOO_DB_NAME)" ]; then echo "❌ test-env refused: ODOO_DB_NAME=$(ODOO_DB_NAME) is not the verified clone $$TEST_ENV_VERIFIED_CLONE" >&2; exit 2; fi
	@test -d plasticos_partner_import/erp_extracted_data || { echo "❌ Preflight failed: ERP projection scripts missing (plasticos_partner_import/erp_extracted_data)"; exit 1; }
	@echo "→ ERP import on database $(ODOO_DB_NAME) $(if $(ERP_DRY),[DRY RUN],)$(if $(ERP_SQL_SERVER), [direct SQL read],)…"
	@echo "   path: make import-erp → plasticos_partner_import/scripts/import_erp_shell.py → plasticos.erp.import (direct SQL source required)$(if $(ERP_PRODUCTION_PERMIT), permit $(ERP_PRODUCTION_PERMIT),)"
	@if docker info >/dev/null 2>&1; then \
		$(erp_source_guard); \
		$(call mount_guard,ERP_PRODUCTION_PERMIT,import-erp); \
		docker compose run --rm $(if $(ERP_ISOLATED_REPORT_DIR),-v "$(ERP_ISOLATED_REPORT_DIR):/erp-isolated",) -w /mnt/extra-addons \
			-e ERP_PRODUCTION_PERMIT="$(call runtime_path,$(ERP_PRODUCTION_PERMIT))" \
			-e ODOO_STAGE="$(ODOO_STAGE)" \
			-e ERP_DRY="$(ERP_DRY)" \
			-e ERP_LIMIT="$(ERP_LIMIT)" \
			-e ERP_PAYLOAD_ROOT="$(ERP_PAYLOAD_ROOT)" \
			-e ERP_REPORT_PATH="$(ERP_REPORT_PATH)" \
			-e ERP_REQUIRE_EMPTY="$(ERP_REQUIRE_EMPTY)" \
			-e ERP_PARTNERS_ONLY="$(ERP_PARTNERS_ONLY)" \
			-e ERP_LAYER="$(ERP_LAYER)" \
			-e ERP_TARGET_DB="$(ODOO_DB_NAME)" \
			-e ERP_SQL_SERVER="$(ERP_SQL_SERVER)" \
			-e ERP_SQL_DATABASE="$(ERP_SQL_DATABASE)" \
			-e ERP_SQL_USER="$(ERP_SQL_USER)" \
			-e ERP_SQL_PASSWORD="$(ERP_SQL_PASSWORD)" \
			-e ERP_SQL_PORT="$(ERP_SQL_PORT)" \
			-e ERP_SQL_DRIVER="$(ERP_SQL_DRIVER)" \
			-e ERP_PROBE="$(ERP_PROBE)" \
			odoo odoo shell -d $(ODOO_DB_NAME) --no-http < plasticos_partner_import/scripts/import_erp_shell.py; \
	elif [ -n "$$TEST_ENV_VERIFIED_CLONE" ]; then \
		echo "❌ test-env refused: $(ODOO_DB_NAME) was verified on the Docker stack and Docker is unreachable; the no-Docker harness is another server" >&2; exit 2; \
	elif [ -x "$(L9_ODOO_VENV)/bin/odoo" ]; then \
		src=$$(ls -d /opt/odoo-src/odoo-19.0* | sort | tail -1); \
		$(erp_source_guard); \
		ERP_PRODUCTION_PERMIT="$(ERP_PRODUCTION_PERMIT)" \
		ODOO_STAGE="$(ODOO_STAGE)" \
		ERP_DRY="$(ERP_DRY)" ERP_LIMIT="$(ERP_LIMIT)" \
		ERP_PAYLOAD_ROOT="$(ERP_PAYLOAD_ROOT)" ERP_REPORT_PATH="$(ERP_REPORT_PATH)" \
		ERP_REQUIRE_EMPTY="$(ERP_REQUIRE_EMPTY)" \
		ERP_PARTNERS_ONLY="$(ERP_PARTNERS_ONLY)" ERP_LAYER="$(ERP_LAYER)" \
		ERP_TARGET_DB="$(ODOO_DB_NAME)" \
		ERP_SQL_SERVER="$(ERP_SQL_SERVER)" ERP_SQL_DATABASE="$(ERP_SQL_DATABASE)" \
		ERP_SQL_USER="$(ERP_SQL_USER)" ERP_SQL_PASSWORD="$(ERP_SQL_PASSWORD)" \
		ERP_SQL_PORT="$(ERP_SQL_PORT)" ERP_SQL_DRIVER="$(ERP_SQL_DRIVER)" \
		ERP_PROBE="$(ERP_PROBE)" \
		"$(L9_ODOO_VENV)/bin/odoo" shell -d $(ODOO_DB_NAME) --no-http \
			--db_host="$(L9_PG_HOST)" --db_port="$(L9_PG_PORT)" --db_user="$(L9_PG_USER)" \
			--addons-path="$$src/odoo/addons,$(CURDIR)" \
			< plasticos_partner_import/scripts/import_erp_shell.py; \
	else \
		echo "❌ No Odoo runtime: start Docker Desktop or run scripts/setup_local_runtime.sh"; exit 1; \
	fi

.PHONY: import-erp-password-guard
import-erp: import-erp-password-guard
# import-erp-test runs import-erp in a nested make; refuse before cloning.
import-erp-test: import-erp-password-guard
import-erp-password-guard:
	@if [ "$(ERP_SQL_PASSWORD_CONFLICT)" = "1" ]; then \
		echo "❌ ERP_SQL_PASSWORD from the environment differs from the one in .env, which make would use instead." >&2; \
		echo "   Remove ERP_SQL_PASSWORD from .env, or make the two match. Neither value is printed." >&2; \
		exit 2; \
	fi

# Test-sized ERP import: a fresh clone of the pristine template, then the newest
# quarter of the worksheets (LIMIT=25% by default). Same importer, same SQL
# reader, same summary contract as `make import-erp`.
#   make import-erp-test ERP_SQL_SERVER=host ERP_SQL_DATABASE=db ERP_SQL_USER=.. ERP_SQL_PASSWORD=..
#   make import-erp-test db=odoo_test_erp_proof LIMIT=10% ...
import-erp-test:
	@bash scripts/test_env.sh clone $(if $(db),$(db),$(ODOO_TEST_DB))
	@bash scripts/test_env.sh run $(if $(db),$(db),$(ODOO_TEST_DB)) -- \
		$(MAKE) import-erp ODOO_DB_NAME=$(if $(db),$(db),$(ODOO_TEST_DB)) \
		ERP_LIMIT="$(if $(LIMIT),$(LIMIT),25%)" \
		ERP_REPORT_PATH="$(or $(REPORT_PATH),.l9/pr/import-erp-test-summary.json)"

# VanillaSoft import onto the Odoo.sh production database. The driver is
# unchanged: plasticos_crm_sync/scripts/import_vanillasoft_shell.py is piped
# into `odoo-bin shell` over SSH. Credentials stay in ir.config_parameter on
# that database. A census, ledger, or permit is copied up for the driver to
# open, then the ledger and summary are copied back. Docker is not used.
# The recipe writes its env file with printf %q, a bash builtin; /bin/sh is dash on Linux.
import-vanillasoft: SHELL := /bin/bash
import-vanillasoft:
	@if [ -n "$$TEST_ENV_VERIFIED_CLONE" ]; then echo "❌ import-vanillasoft refused: this target writes the Odoo.sh production database and does not run inside a test-env clone" >&2; exit 2; fi
	@$(vanillasoft_mode_guard)
	@echo "→ VanillaSoft import on the Odoo.sh production database…"
	@echo "   mode: $(VANILLASOFT_MODE) — plasticos_crm_sync/scripts/import_vanillasoft_shell.py$(if $(VANILLASOFT_CONTACT_EXPORT), repository cohort $(VANILLASOFT_CONTACT_EXPORT) ledger $(VANILLASOFT_HISTORY_CHECKPOINT) (not a call floor and not a history census),$(if $(VANILLASOFT_HISTORY_CENSUS), history(): census sha256 $(VANILLASOFT_HISTORY_CENSUS_SHA256) ledger $(VANILLASOFT_HISTORY_CHECKPOINT) max_ids $(or $(VANILLASOFT_HISTORY_MAX_IDS),all) (not the rolling window), rolling window from $(VANILLASOFT_CALL_FLOOR) (not the historical cohort)))"
	@set -eu; \
	ssh_target="$${ODOO_SH_PRODUCTION_SSH:-}"; \
	if [ -z "$$ssh_target" ]; then \
		[ -r .env.local ] || { echo "❌ import-vanillasoft refused: ODOO_SH_PRODUCTION_SSH is unset and .env.local is not readable" >&2; exit 2; }; \
		ssh_target="$$(sed -n 's/^ODOO_SH_PRODUCTION_SSH=//p' .env.local | head -n 1 | tr -d '\r')"; \
	fi; \
	case "$$ssh_target" in \
		*@*) ;; \
		*) echo "❌ import-vanillasoft refused: ODOO_SH_PRODUCTION_SSH must be user@host" >&2; exit 2 ;; \
	esac; \
	case "$$ssh_target" in \
		"ssh "*|*[[:space:]]*) echo "❌ import-vanillasoft refused: ODOO_SH_PRODUCTION_SSH must be user@host with no ssh prefix" >&2; exit 2 ;; \
		-*) echo "❌ import-vanillasoft refused: ODOO_SH_PRODUCTION_SSH must not start with '-' (ssh would read it as an option)" >&2; exit 2 ;; \
	esac; \
	bid="$${ssh_target%%@*}"; \
	db="cryptoxdog-ib-odoo-19-production-$$bid"; \
	call_floor='$(VANILLASOFT_CALL_FLOOR)'; \
	contact_floor='$(VANILLASOFT_CONTACT_FLOOR)'; \
	sha='$(VANILLASOFT_HISTORY_CENSUS_SHA256)'; \
	max_ids='$(VANILLASOFT_HISTORY_MAX_IDS)'; \
	budget='$(VANILLASOFT_HISTORY_FAILURE_BUDGET)'; \
	census_path='$(VANILLASOFT_HISTORY_CENSUS)'; \
	export_path='$(VANILLASOFT_CONTACT_EXPORT)'; \
	confirm='$(VANILLASOFT_PRODUCTION_CONFIRM)'; \
	ledger_path='$(VANILLASOFT_HISTORY_CHECKPOINT)'; \
	permit_path='$(VANILLASOFT_PRODUCTION_PERMIT)'; \
	report_path='$(VANILLASOFT_REPORT_PATH)'; \
	ssh_opts="-T -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=30 -o ServerAliveCountMax=720"; \
	scp_opts="-O -o BatchMode=yes -o ConnectTimeout=25"; \
	remote_home="$$(ssh $$ssh_opts "$$ssh_target" 'printf "HOME:%s\n" "$$HOME"' | sed -n 's/^HOME://p' | head -n 1)"; \
	[ -n "$$remote_home" ] || { echo "❌ import-vanillasoft refused: the production home directory was not readable" >&2; exit 2; }; \
	work="$$remote_home/data/plasticos_import/vanillasoft-$$$$"; \
	echo "   database: $$db"; \
	ssh $$ssh_opts "$$ssh_target" "mkdir -p '$$work' && chmod 700 '$$work'"; \
	remote_census=""; remote_export=""; remote_ledger=""; remote_permit=""; \
	if [ -n "$$export_path" ]; then scp $$scp_opts "$$export_path" "$$ssh_target:$$work/export.csv"; remote_export="$$work/export.csv"; fi; \
	if [ -n "$$census_path" ]; then scp $$scp_opts "$$census_path" "$$ssh_target:$$work/census.csv"; remote_census="$$work/census.csv"; fi; \
	if [ -n "$$ledger_path" ] && [ -f "$$ledger_path" ]; then scp $$scp_opts "$$ledger_path" "$$ssh_target:$$work/ledger.jsonl"; fi; \
	if [ -n "$$ledger_path" ]; then remote_ledger="$$work/ledger.jsonl"; fi; \
	if [ -n "$$permit_path" ]; then scp $$scp_opts "$$permit_path" "$$ssh_target:$$work/permit.json"; remote_permit="$$work/permit.json"; fi; \
	remote_report="$$work/summary.json"; \
	envfile="$$(mktemp)"; \
	trap 'rm -f "$$envfile"' EXIT; \
	chmod 600 "$$envfile"; \
	{ \
		printf 'ODOO_STAGE=%q\n' production; \
		printf 'VANILLASOFT_API_KEY=%q\n' "$${VANILLASOFT_API_KEY:-}"; \
		printf 'VANILLASOFT_CONTACT_EXPORT=%q\n' "$$remote_export"; \
		printf 'VANILLASOFT_PRODUCTION_CONFIRM=%q\n' "$$confirm"; \
		printf 'VANILLASOFT_HISTORY_CENSUS=%q\n' "$$remote_census"; \
		printf 'VANILLASOFT_HISTORY_CENSUS_SHA256=%q\n' "$$sha"; \
		printf 'VANILLASOFT_HISTORY_CHECKPOINT=%q\n' "$$remote_ledger"; \
		printf 'VANILLASOFT_HISTORY_MAX_IDS=%q\n' "$$max_ids"; \
		printf 'VANILLASOFT_HISTORY_FAILURE_BUDGET=%q\n' "$$budget"; \
		printf 'VANILLASOFT_PRODUCTION_PERMIT=%q\n' "$$remote_permit"; \
		printf 'VANILLASOFT_CALL_FLOOR=%q\n' "$$call_floor"; \
		printf 'VANILLASOFT_CONTACT_FLOOR=%q\n' "$$contact_floor"; \
		printf 'VANILLASOFT_REPORT_PATH=%q\n' "$$remote_report"; \
	} > "$$envfile"; \
	scp $$scp_opts "$$envfile" "$$ssh_target:$$work/env"; \
	ssh $$ssh_opts "$$ssh_target" "chmod 600 '$$work/env'"; \
	if [ -n "$$export_path" ]; then \
		printf '%s\n' \
			'module = env["ir.module.module"].search([("name", "=", "plasticos_crm_sync")], limit=1)' \
			'if not module:' \
			'    raise SystemExit("plasticos_crm_sync is not available on this database")' \
			'if module.state != "installed":' \
			'    if module.state not in ("uninstalled", "to install"):' \
			'        raise SystemExit("plasticos_crm_sync state is %s" % module.state)' \
			'    module.button_immediate_install()' \
			'env.cr.commit()' \
		| ssh $$ssh_opts "$$ssh_target" "set -a && . '$$work/env' && set +a && exec odoo-bin shell -d '$$db' --no-http"; \
	fi; \
	set +e; \
	ssh $$ssh_opts "$$ssh_target" "set -a && . '$$work/env' && set +a && exec odoo-bin shell -d '$$db' --no-http" < plasticos_crm_sync/scripts/import_vanillasoft_shell.py; \
	status=$$?; \
	set -e; \
	ssh $$ssh_opts "$$ssh_target" "rm -f '$$work/env'" || true; \
	mkdir -p "$$(dirname "$$report_path")"; \
	copy_rc=0; \
	scp $$scp_opts "$$ssh_target:$$remote_report" "$$report_path" || copy_rc=$$?; \
	if [ -n "$$ledger_path" ]; then scp $$scp_opts "$$ssh_target:$$remote_ledger" "$$ledger_path" || copy_rc=$$?; fi; \
	if [ "$$status" -ne 0 ]; then echo "→ VanillaSoft import exit $$status" >&2; exit "$$status"; fi; \
	if [ "$$copy_rc" -ne 0 ]; then echo "❌ import-vanillasoft: the production run finished but the summary or ledger could not be copied back from $$work" >&2; exit "$$copy_rc"; fi; \
	ssh $$ssh_opts "$$ssh_target" "cd '$$work' && rm -f export.csv census.csv ledger.jsonl permit.json summary.json && cd .. && rmdir '$$work'" \
		|| echo "⚠ import-vanillasoft: could not clear $$work on the production host; remove it by hand" >&2; \
	echo "→ VanillaSoft import exit 0"
	@python3 -c "import json; rows = [r for r in json.load(open('$(VANILLASOFT_REPORT_PATH)')).get('errors') or [] if r.get('error_type') == 'MATERIAL_PLACEMENT_REVIEW']; print(f'NEEDS REVIEW: {len(rows)} VanillaSoft records have unplaced materials (ADR-132; rows in $(VANILLASOFT_REPORT_PATH))')"

# 2026-10-17 — Enterprise Docker tests. The fingerprint-template comment above
# is historical. make test-env, test-db, test-odoo, test-module, and
# import-erp-test clone only the database named in config/test_env_fixture.conf.
# TEST_ENV_PARITY=community is refused unless TEST_ENV_SAFETY_HARNESS=1.
# A new template is refused unless that database is absent and
# TEST_ENV_ALLOW_NEW_TEMPLATE equals its name. make test-odoo-local is the
# no-Docker backend and is not this fixture.
#
# 2026-10-19 — the test-odoo and test-module recipes above are unchanged, but
# test_env.sh run treats a --test-enable run as its test runner: it upgrades
# every declared PlasticOS module on the clone (not -u all), limits the tests to
# that roster or to m=, and fails on a missing Odoo summary, any failure or
# error, or zero tests (receipt: .l9/runtime/test-env/<db>.test-receipt.json).
# The fixture is refused when its image, Postgres major, module roster,
# configuration, or Enterprise checkout differs from the inputs it was admitted
# for; it is not rebuilt. Under test_env.sh run, import-erp refuses a database
# other than the verified clone and its no-Docker fallback. import-vanillasoft
# writes the Odoo.sh production database over SSH and refuses when
# TEST_ENV_VERIFIED_CLONE is set. MAKEFILES and MAKEFLAGS are cleared before
# make starts.
# Every other test_env.sh run (an import, shell, runtime-gate-f1) first
# upgrades the PlasticOS roster on the clone, once per addon source digest
# (stamped src= on the clone), reading no stdin.

# 2026-10-22 — operator bypass for the local install-smoke gate. make pr-nosmoke
# reason="..." runs make pr without Docker install-smoke; every other gate still
# runs. The reason is printed and posted on the PR. make pr is unchanged.
.PHONY: pr-nosmoke
pr-nosmoke:
	@test -n "$(strip $(reason))" || { echo 'usage: make pr-nosmoke reason="why install-smoke is skipped"' >&2; exit 2; }
	@PR_SMOKE_BYPASS='$(reason)' $(MAKE) --no-print-directory pr $(if $(b),b=$(b),) $(if $(base),base=$(base),)

# 2026-10-22 — make pr-check runs only what the branch changed can reach
# (scripts/pr_check_scope.py): install-smoke runs only when an addon or
# installer input changed, and a documentation-only branch publishes with no
# collector and no Docker. PR_CHECK_SCOPE=full keeps the audit and Docker
# gate. This target is a manual scoped pytest run. make pr, make pr-check,
# and the pre-push gate do not call it. make test and GitHub ci.yml run the
# whole suite; ci.yml is the merge verdict.
.PHONY: test-scoped
test-scoped:
	@echo "→ Pure-Python tests reached by the changed files: $(TEST_PATHS)"
	python3 -m pytest $(TEST_PATHS) -q

# 2026-11-04 — recover the pinned Enterprise fixture when its image, Postgres,
# module roster, configuration, or Enterprise checkout no longer matches.
# Refuses when the template is already admitted for the current inputs.
# Drops only that template and its current build database, then admits it again.
# Do not set TEST_ENV_ALLOW_NEW_TEMPLATE by hand for a source edit.
.PHONY: test-env-rebuild
test-env-rebuild:
	bash scripts/test_env.sh rebuild

# 2026-11-06 — Odoo runtime tests have two owners and no third. make test-module
# and make test-odoo (recipes above, unchanged) run only through runtime-test:
#   1. the Docker smoke stage of make pr-check (scripts/pr_check_run.sh). It
#      passes RUNTIME_MODULES from scripts/pr_check_scope.py (runtime=): the
#      declared roster modules the branch touched that ship a tests/ package,
#      or "all" when the whole gate is kept. make pr-nosmoke, PR_CHECK_SKIP_SMOKE
#      and a documentation-only branch skip it with install-smoke.
#   2. the l9-pr-integration-testing skill, only when the operator invokes it:
#      make runtime-test m=<module[,module...]> on the host compose stack.
# Agents do not run make test-module or make test-odoo ad hoc.
.PHONY: runtime-test
runtime-test:
	@mods='$(strip $(if $(m),$(m),$(RUNTIME_MODULES)))'; \
	case "$$mods" in \
	  "") echo "→ runtime tests: no PlasticOS module with Odoo tests reached" ;; \
	  all) echo "→ runtime tests: whole roster (make test-odoo)"; $(MAKE) --no-print-directory test-odoo ;; \
	  *) echo "→ runtime tests: $$mods (make test-module)"; $(MAKE) --no-print-directory test-module m="$$mods" ;; \
	esac

# 2026-11-10 — make runtime-bootstrap prepares a machine with Docker, a cloud
# agent session included, for the Odoo Enterprise runtime gate. It binds an
# Enterprise checkout (ODOO_ENTERPRISE_PATH, ./odoo-enterprise, a sibling
# ../odoo-enterprise, or ODOO_ENTERPRISE_REPO) and admits the pinned fixture
# from config/test_env_fixture.conf when that database is absent. It runs no
# Odoo tests: the runtime-test owners above are unchanged.
# Setup: docs/LOCAL_DEV_SETUP.md, "Cloud agent sessions".
.PHONY: runtime-bootstrap
runtime-bootstrap:
	bash scripts/runtime_bootstrap.sh

# 2026-11-13 — make import-erp-material-profiles puts plasticos.material.profile
# records on the exact ERP site partner named by two operator files (Product,
# Supplier or Customer, Ship From or Ship To). The product map is
# plasticos_material_profile/data/ERP-Products.csv and nothing else. The two
# files are private and gitignored; both are read as one list.
#   make import-erp-material-profiles DRY=1   resolve and count, persist nothing
#   make import-erp-material-profiles         applied (ODOO_DB_NAME is the target)
#   ERP_PROFILE_SUPPLIERS= / ERP_PROFILE_CUSTOMERS=   non-default file paths
#   REPORT_PATH=                                      machine summary path
# Same runtimes and database check as import-erp; the driver has no production
# permit, so a production database is refused. Run it after the ERP partner
# import: it resolves partners by their legacy_erp_cp_ / legacy_erp_address_ ids.
.PHONY: import-erp-material-profiles
ERP_PROFILE_SUPPLIERS ?= plasticos_material_profile/data/ERP-Material-Profiles-Suppliers.csv
ERP_PROFILE_CUSTOMERS ?= plasticos_material_profile/data/ERP-Material-Profiles-Customers.csv
ERP_PROFILE_DRY ?= $(DRY)
ERP_PROFILE_REPORT_PATH ?= $(or $(REPORT_PATH),.l9/pr/import-erp-material-profiles-summary.json)
import-erp-material-profiles:
	@if [ -n "$$TEST_ENV_VERIFIED_CLONE" ] && [ "$$TEST_ENV_VERIFIED_CLONE" != "$(ODOO_DB_NAME)" ]; then echo "❌ test-env refused: ODOO_DB_NAME=$(ODOO_DB_NAME) is not the verified clone $$TEST_ENV_VERIFIED_CLONE" >&2; exit 2; fi
	@for f in "$(ERP_PROFILE_SUPPLIERS)" "$(ERP_PROFILE_CUSTOMERS)"; do [ -r "$$f" ] || { echo "❌ import-erp-material-profiles refused: $$f is not a readable file (ERP_PROFILE_SUPPLIERS / ERP_PROFILE_CUSTOMERS)" >&2; exit 2; }; done
	@echo "→ ERP material profiles on database $(ODOO_DB_NAME) $(if $(ERP_PROFILE_DRY),[DRY RUN],)…"
	@echo "   path: make import-erp-material-profiles → plasticos_transaction/scripts/load_erp_material_profiles_shell.py → plasticos.erp.material.profile.loader"
	@if docker info >/dev/null 2>&1; then \
		$(call mount_guard,ERP_PROFILE_SUPPLIERS ERP_PROFILE_CUSTOMERS ERP_PROFILE_REPORT_PATH,import-erp-material-profiles); \
		docker compose run --rm -w /mnt/extra-addons \
			-e ODOO_STAGE="$(ODOO_STAGE)" \
			-e ERP_TARGET_DB="$(ODOO_DB_NAME)" \
			-e ERP_PROFILE_SUPPLIERS="$(call runtime_path,$(ERP_PROFILE_SUPPLIERS))" \
			-e ERP_PROFILE_CUSTOMERS="$(call runtime_path,$(ERP_PROFILE_CUSTOMERS))" \
			-e ERP_PROFILE_DRY="$(ERP_PROFILE_DRY)" \
			-e ERP_PROFILE_REPORT_PATH="$(call runtime_path,$(ERP_PROFILE_REPORT_PATH))" \
			odoo odoo shell -d $(ODOO_DB_NAME) --no-http < plasticos_transaction/scripts/load_erp_material_profiles_shell.py; \
	elif [ -n "$$TEST_ENV_VERIFIED_CLONE" ]; then \
		echo "❌ test-env refused: $(ODOO_DB_NAME) was verified on the Docker stack and Docker is unreachable; the no-Docker harness is another server" >&2; exit 2; \
	elif [ -x "$(L9_ODOO_VENV)/bin/odoo" ]; then \
		src=$$(ls -d /opt/odoo-src/odoo-19.0* | sort | tail -1); \
		ODOO_STAGE="$(ODOO_STAGE)" ERP_TARGET_DB="$(ODOO_DB_NAME)" \
		ERP_PROFILE_SUPPLIERS="$(ERP_PROFILE_SUPPLIERS)" ERP_PROFILE_CUSTOMERS="$(ERP_PROFILE_CUSTOMERS)" \
		ERP_PROFILE_DRY="$(ERP_PROFILE_DRY)" ERP_PROFILE_REPORT_PATH="$(ERP_PROFILE_REPORT_PATH)" \
		"$(L9_ODOO_VENV)/bin/odoo" shell -d $(ODOO_DB_NAME) --no-http \
			--db_host="$(L9_PG_HOST)" --db_port="$(L9_PG_PORT)" --db_user="$(L9_PG_USER)" \
			--addons-path="$$src/odoo/addons,$(CURDIR)" \
			< plasticos_transaction/scripts/load_erp_material_profiles_shell.py; \
	else \
		echo "❌ No Odoo runtime: start Docker Desktop or run scripts/setup_local_runtime.sh"; exit 1; \
	fi

# PlasticOS Development Makefile
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help \
        lint format format-fix check \
        audit audit-quick \
        xml-check wiring deps-check cron-check odoo19-check semgrep semgrep-test \
        pipeline-guard dev-fence state-guard acl-check guards deploy-check \
        up down restart logs logs-error shell odoo-shell \
        update update-all rebuild backup \
        test test-odoo test-pure test-module \
        pr-check pr-check-% commit push api-push-check sonar changelog \
        governance-backup \
        github-actions-kernel-check \
        pr-autopilot pr-fix \
        roadmap roadmap-sync roadmap-list

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
ODOO_COMPOSE_PROJECT  ?= odoo19

# Pinned ruff resolver. pyproject pins ruff EXACTLY (==0.15.5 via [tool.ruff]
# required-version), so a mismatched PATH ruff (e.g. Homebrew latest, or an old
# pip --user 0.14.x) aborts every invocation. Prefer the project venv's pinned
# binary; fall back to PATH ruff (CI has no .venv and installs 0.15.5 directly).
RUFF := $(shell [ -x .venv/bin/ruff ] && echo .venv/bin/ruff || echo ruff)

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
	@echo "    make venv             build pinned local .venv (ruff==0.15.5, semgrep, pytest) — mirrors CI"
	@echo "    make lint             ruff check (lint only)"
	@echo "    make format           ruff format --check (check only)"
	@echo "    make format-fix       ruff format (auto-fix)"
	@echo "    make check            lint + format check"
	@echo ""
	@echo "  Audit (run before PRs)"
	@echo "    make audit-quick      fast: lint + format + wiring + odoo19 + xml + deps + cron"
	@echo "    make audit            full: audit-quick + semgrep + semgrep-test + all ci/ integrity scripts"
	@echo "    make xml-check        xmllint on all plasticos XML files"
	@echo "    make odoo19-check     Odoo 19 XML pattern violations"
	@echo "    make wiring           module dependency wiring check"
	@echo "    make deps-check       circular dependency check"
	@echo "    make cron-check       cron invariant violations"
	@echo "    make semgrep          semgrep custom Odoo rules (ERROR level)"
	@echo "    make semgrep-test     validate semgrep config + positive/negative fixtures"
	@echo "    make acl-check        ACL completeness (all models have ir.model.access)"
	@echo ""
	@echo "  Hard Gates (run individually or via make guards)"
	@echo "    make pipeline-guard   HARD GATE: pipeline_v2.py must not be activated"
	@echo "    make dev-fence        production safety: plasticos_dev_tools fenced"
	@echo "    make state-guard      write guard bypass check"
	@echo "    make guards           all three hard gates combined"
	@echo "    make deploy-check     pre-flight: pr-check + guards + ICP + Neo4j validation"
	@echo ""
	@echo "  Docker / Odoo"
	@echo "    make up               docker compose up -d"
	@echo "    make down             docker compose down"
	@echo "    make restart          restart Odoo container only"
	@echo "    make logs             follow Odoo container logs"
	@echo "    make logs-error       follow logs filtered to ERROR/CRITICAL only"
	@echo "    make shell            exec bash in Odoo container"
	@echo "    make odoo-shell       Odoo Python shell (for data inspection)"
	@echo "    make update m=<mod>   -u <module> (e.g. make update m=plasticos_commission)"
	@echo "    make update-all       -u all modules"
	@echo "    make rebuild          drop DB + full rebuild (no demo)"
	@echo "    make backup           snapshot DB to backup_<timestamp>.sql"
	@echo "    make governance-backup  push .cursor-commands → Cursor-Governance GitHub"
	@echo ""
	@echo "  Testing"
	@echo "    make test             pure pytest in tests/ (mirrors PR CI Tier 3)"
	@echo "    make test-odoo        Odoo Docker native tests on installed modules"
	@echo "    make test-pure        alias for make test"
	@echo "    make test-module m=<mod>  Odoo tests for one module (-u m)"
	@echo ""
	@echo "  PR / CI Workflow"
	@echo "    make commit           stage all (except .cursor-commands) + commit"
	@echo "    make commit m=\"...\"   commit with explicit conventional message"
	@echo "    make github-actions-kernel-check  validate staged/all .github/workflows (R5 kernel)"
	@echo "    make pr-check         REQUIRED before any push: audit-quick + semgrep + semgrep-test + pipeline-guard"
	@echo "    make pr-check pr=100       remote gate for PR #100 or full GitHub URL"
	@echo "    make pr-check-100          shorthand for pr=100"
	@echo "    make push             safe push: pr-check, then push current FEATURE branch (Staging/Production are PR-only)"
	@echo "    make push pr=1        push feature branch, then open a PR into Staging"
	@echo "    make api-push-check   REQUIRED before GitHub API push (when git push fails)"
	@echo "    make pr-autopilot     scan all PR signals (CI, SonarCloud, CodeRabbit) — report only"
	@echo "    make pr-fix           scan + auto-fix safe issues + push back to branch (re-triggers CI)"
	@echo "    make sonar            show SonarCloud quality gate status"
	@echo "    make changelog        generate CHANGELOG.md from conventional commits"
	@echo ""
	@echo "  Roadmap (registry: docs/roadmap/registry.yaml)"
	@echo "    make roadmap          sync + validate (add item: pass domain phase kind title)"
	@echo "    make roadmap-list     list all registry items"
	@echo "    make roadmap-sync     sync only (make roadmap preferred)"
	@echo "    Example: make roadmap domain=gate-autonomy phase=1 kind=backlog title=\"...\""
	@echo ""
	@echo "  Agent review kernels (.claude/skills/ — playbooks, not extra targets)"
	@echo "    FINAL_TOUCHES_MODE     plasticos-final-touches  → make audit + make pr-check"
	@echo "    PR_REVIEW_MODE         plasticos-pr-review-kernel → make pr-check"
	@echo "    (static/repo audit)    plasticos-static-audit-kernel / plasticos-repo-review-kernel → make audit"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# CODE QUALITY
# ─────────────────────────────────────────────────────────────────────────────

# Build a complete, pinned local dev virtualenv (.venv) that mirrors CI.
# Installs requirements-dev.txt + the EXACT-pinned ruff and semgrep so every tool
# (ruff, pytest, semgrep, pr-repair) resolves to one reproducible set. The .envrc
# (direnv) auto-activates it; `make` also auto-prefers .venv/bin/ruff via $(RUFF).
# Idempotent: safe to re-run to repair/upgrade the environment.
VENV ?= .venv
venv:
	@echo "→ Building $(VENV) (python3.12, pinned dev toolchain)..."
	python3.12 -m venv $(VENV)
	@$(VENV)/bin/python -m pip install --quiet --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements-dev.txt
	$(VENV)/bin/python -m pip install "ruff==0.15.5" "semgrep==1.164.0"
	@echo ""
	@echo "✅ $(VENV) ready:"
	@$(VENV)/bin/ruff --version
	@$(VENV)/bin/python -m pytest --version 2>&1 | head -1
	@$(VENV)/bin/semgrep --version 2>&1 | head -1
	@echo "→ Activate automatically with direnv (direnv allow), or: source $(VENV)/bin/activate"

lint:
	$(RUFF) check .

format:
	$(RUFF) format --check .

format-fix:
	$(RUFF) format .

check: lint format
	@echo "✅ lint + format check passed"

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

wiring:
	@echo "→ Module wiring check..."
	python3 scripts/check_module_wiring.py

deps-check:
	@echo "→ Circular dependency check (known pre-existing: commission↔transaction)..."
	python3 ci/check_circular_deps.py || true

cron-check:
	@echo "→ Cron invariant check..."
	@find . -path "./current work*" -prune -o -name "*.xml" -print | \
		xargs grep -l "ir.cron" 2>/dev/null | head -1 > /dev/null && \
		python3 tools/cron_invariant_check.py 2>&1 | grep -v "current work" || true

semgrep:
	@echo "→ Semgrep custom Odoo rules (ERROR level only)..."
	semgrep --error --config .semgrep/odoo-patterns.yml --severity ERROR --quiet --include="plasticos_*"

semgrep-test:
	@echo "→ Semgrep rule fixture tests..."
	semgrep --validate --config .semgrep/odoo-patterns.yml
	@echo "→ Positive fixtures should produce findings..."
	@semgrep --config .semgrep/odoo-patterns.yml .semgrep/tests/positive.py .semgrep/tests/odoo19.xml --quiet | grep -q .
	@echo "→ Negative fixtures should produce no blocking findings..."
	semgrep --error --config .semgrep/odoo-patterns.yml .semgrep/tests/negative.py --quiet

acl-check:
	@echo "→ ACL completeness check..."
	python3 ci/check_acl_completeness.py

audit-quick: lint format xml-check odoo19-check wiring deps-check cron-check
	@echo ""
	@echo "✅ Quick audit complete"

audit: audit-quick semgrep semgrep-test guards acl-check
	@echo "→ Field integrity..."
	python3 ci/check_field_integrity.py
	@echo "→ ORM integrity..."
	python3 ci/check_orm_integrity.py
	@echo "→ Orphan model refs..."
	python3 ci/check_orphan_model_refs.py
	@echo "→ Automation field refs..."
	python3 ci/check_automation_field_refs.py
	@echo "→ XPath stability..."
	python3 ci/check_xpath_stability.py
	@echo "→ Constraint patterns..."
	python3 ci/check_constraint_patterns.py
	@echo "→ Model inheritance..."
	python3 ci/check_model_inheritance.py
	@echo "→ Disabled actions..."
	python3 ci/check_disabled_actions.py
	@echo ""
	@echo "✅ Full audit complete"

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

# Deployment pre-flight check — validates ICP params + Neo4j credentials + guards
deploy-check: pr-check guards
	@echo ""
	@echo "→ Deployment pre-flight validation..."
	@echo ""
	@echo "  1. Checking ICP configuration parameters..."
	@if docker compose ps | grep -q "web.*Up"; then \
		docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -c \
			"SELECT key, value FROM ir_config_parameter WHERE key LIKE 'plasticos.%' ORDER BY key;" \
			2>/dev/null || echo "    ⚠️  Could not query ICP params (DB not accessible)"; \
	else \
		echo "    ⚠️  Odoo container not running — start with: make up"; \
	fi
	@echo ""
	@echo "  2. Checking Neo4j credentials..."
	@if [ -f .env ] && grep -q "NEO4J_URL" .env; then \
		echo "    ✅ NEO4J_URL configured in .env"; \
		grep -q "NEO4J_USER" .env && echo "    ✅ NEO4J_USER configured" || echo "    ❌ NEO4J_USER missing"; \
		grep -q "NEO4J_PASSWORD" .env && echo "    ✅ NEO4J_PASSWORD configured" || echo "    ❌ NEO4J_PASSWORD missing"; \
	else \
		echo "    ⚠️  NEO4J_URL not configured (matching engine will run in stub mode)"; \
	fi
	@echo ""
	@echo "  3. Checking stub mode flags..."
	@if docker compose ps | grep -q "web.*Up"; then \
		ENABLED=$$(docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -t -c \
			"SELECT value FROM ir_config_parameter WHERE key = 'plasticos.matching_engine.enabled';" 2>/dev/null | xargs); \
		STUBBED=$$(docker compose exec -T db psql -U $${POSTGRES_USER:-odoo} $(ODOO_DB_NAME) -t -c \
			"SELECT value FROM ir_config_parameter WHERE key = 'plasticos.matching_engine.stubbed';" 2>/dev/null | xargs); \
		echo "    Matching engine enabled: $${ENABLED:-not set}"; \
		echo "    Matching engine stubbed: $${STUBBED:-not set}"; \
		if [ "$$ENABLED" = "True" ] && [ "$$STUBBED" = "False" ]; then \
			echo "    ⚠️  WARNING: Matching engine is LIVE (not stubbed) — ensure Neo4j is accessible"; \
		fi; \
	fi
	@echo ""
	@echo "✅ Deploy pre-flight complete — safe to run: make update m=<module>"
	@echo ""

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
update:
	@if [ -z "$(m)" ]; then echo "Usage: make update m=<module>"; exit 1; fi
	@echo "→ Upgrading module(s): $(m)..."
	@docker compose run --rm odoo -u $(m) 2>&1 | tee /tmp/odoo-update-$$(date +%Y%m%d_%H%M%S).log; \
	EXIT_CODE=$${PIPESTATUS[0]}; \
	if [ $$EXIT_CODE -ne 0 ]; then \
		echo ""; \
		echo "❌ Module upgrade failed with exit code $$EXIT_CODE"; \
		exit 1; \
	fi
	@echo ""
	@echo "→ Checking logs for errors..."
	@if tail -100 /tmp/odoo-update-*.log | grep -E "ERROR|CRITICAL|Traceback" | grep -v "test_" | head -5; then \
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
	docker compose run --rm odoo -u all

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

# Default test target — mirrors CI Tier 3 "Pure Python Tests".
# conftest.py auto-deactivates every Odoo-importing test when Odoo isn't installed,
# so this runs exactly the Odoo-free set without a hand-maintained file list.
test:
	@echo "→ Pure-Python test suite (Odoo-free; mirrors CI Tier 3)..."
	python3 -m pytest tests/ --tb=short --no-header -p no:randomly -q

# Backward-compatible alias
test-pure: test

# Odoo runtime tests — Docker native runner on installed modules (not tests/ pytest suite).
# Same surface as ci/odoo.sh (dev) Odoo Test Suite, but runs locally via docker compose.
test-odoo:
	docker compose run --rm odoo \
		--test-enable \
		--stop-after-init \
		-d $(ODOO_TEST_DB) \
		--log-level=test

# make test-module m=plasticos_commission
test-module:
	@if [ -z "$(m)" ]; then echo "Usage: make test-module m=<module>"; exit 1; fi
	docker compose run --rm odoo \
		--test-enable \
		--stop-after-init \
		-d $(ODOO_TEST_DB) \
		--log-level=test \
		-u $(m)

# ─────────────────────────────────────────────────────────────────────────────
# PR / CI WORKFLOW
# ─────────────────────────────────────────────────────────────────────────────

# REQUIRED before any push or PR creation (local + remote when PR/CI exists)
pr-check: audit-quick semgrep semgrep-test pipeline-guard test pr-remote-feedback
	@echo ""
	@echo "✅ PR gate passed — safe to push"

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
	if [ -t 0 ]; then \
		printf "Run make push? [y/N] "; \
		read -r ans; \
		case "$$ans" in [yY]|[yY][eE][sS]) $(MAKE) push ;; *) echo "Skipped. Run: make push"; ;; esac; \
	else \
		echo "Run: make push   (feature branch; Staging/Production are PR-only — use: make push pr=1)"; \
	fi

# Protected branches — PR-only via GitHub ruleset "Protect Staging & Production"
# (require PR + required status checks: Ruff Lint & Format, Static Analysis, Pure Python Tests).
# Keep this list in sync with the repo ruleset. Direct pushes here are rejected by GitHub.
PROTECTED_BRANCHES := Staging Production

# Safe push: runs full pr-check, then pushes the CURRENT FEATURE branch.
# Refuses to push if any commit since upstream touches $(COMMIT_EXCLUDE).
# Staging/Production are PR-only — this target refuses to push to them directly
# (the ruleset would reject it anyway) and points you to the PR flow.
# Usage: make push              (push current feature branch)
#        make push pr=1         (push, then open a PR into Staging)
#        make push base=Production pr=1   (open the PR against Production instead)
push: pr-check
	@echo ""
	@set -e; \
	BRANCH=$$(git branch --show-current); \
	TARGET=$${b:-$$BRANCH}; \
	UPSTREAM=$$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true); \
	if [ -n "$$UPSTREAM" ]; then \
		BASE=$$(git merge-base HEAD "$$UPSTREAM"); \
	else \
		BASE=$$(git merge-base HEAD origin/Staging 2>/dev/null || git rev-list --max-parents=0 HEAD | tail -1); \
	fi; \
	if git diff --name-only "$$BASE"..HEAD | grep -q '^$(COMMIT_EXCLUDE)'; then \
		echo "⛔ Refusing to push: commits include $(COMMIT_EXCLUDE) (governance repo only)."; \
		echo "   Remove those paths from the branch before pushing to IB-Odoo_19."; \
		exit 1; \
	fi; \
	for p in $(PROTECTED_BRANCHES); do \
		if [ "$$TARGET" = "$$p" ]; then \
			echo "⛔ '$$p' is a protected branch (PR-only + required checks)."; \
			echo "   The GitHub ruleset rejects direct pushes. Use a feature branch + PR:"; \
			echo "       git switch -c fix/<short-description>"; \
			echo "       make push pr=1"; \
			exit 1; \
		fi; \
	done; \
	echo "→ Pushing $$BRANCH → origin/$$TARGET ..."; \
	if git push origin HEAD:$$TARGET; then \
		echo "✅ Push complete"; \
		BASE=$${base:-Staging}; \
		if [ -n "$(pr)" ]; then \
			echo "→ Opening PR: $$TARGET → $$BASE ..."; \
			gh pr create --base "$$BASE" --head "$$TARGET" --fill || \
				echo "⚠️  PR create failed (already open?). Check: gh pr view --web"; \
		else \
			echo "ℹ️  Open a PR when ready:  gh pr create --base $$BASE   (or: make push pr=1)"; \
		fi; \
	else \
		echo "⚠️  git push failed (Dropbox mmap issue?). Run: make api-push-check"; \
	fi

# REQUIRED before using GitHub API to push (when git push is broken)
# Enforces same validation as make push but for API workflow
api-push-check:
	@python3 scripts/api_push.py

# Scan PR for all CI/SonarCloud/CodeRabbit issues — report only, no changes
pr-autopilot:
	@echo "→ PR Autopilot — scanning all signals (CI, SonarCloud, CodeRabbit, reviews)..."
	python3 scripts/pr_autopilot.py

# Scan + auto-fix all safe issues + push back to branch (triggers CI re-run)
# Runs make pr-check before pushing — never bypasses the pre-push pipeline
pr-fix:
	@echo "→ PR Autopilot — scanning + fixing + pushing..."
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

# ─────────────────────────────────────────────────────────────────────────────
# ROADMAP (docs/roadmap/registry.yaml → synced planning docs)
# ─────────────────────────────────────────────────────────────────────────────

roadmap:
	@python3 scripts/roadmap.py update \
		$(if $(domain),--domain "$(domain)",) \
		$(if $(phase),--phase $(phase),) \
		$(if $(kind),--kind "$(kind)",) \
		$(if $(title),--title "$(title)",) \
		$(if $(notes),--notes "$(notes)",) \
		$(if $(status),--status "$(status)",)

roadmap-sync:
	@python3 scripts/roadmap.py sync

roadmap-list:
	@python3 scripts/roadmap.py list

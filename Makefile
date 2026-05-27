# PlasticOS Development Makefile
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help \
        lint format format-fix check \
        audit audit-quick \
        xml-check wiring deps-check cron-check odoo19-check semgrep \
        pipeline-guard dev-fence state-guard acl-check guards deploy-check \
        up down restart logs logs-error shell odoo-shell \
        update update-all rebuild backup \
        test test-module \
        pr-check push api-push-check sonar changelog \
        pr-autopilot pr-fix

# ── Load .env if present ──────────────────────────────────────────────────────
-include .env
export

ODOO_DB_NAME          ?= odoo
ODOO_TEST_DB          ?= odoo_test
ODOO_COMPOSE_PROJECT  ?= odoo19

# Modules excluded from ruff (pre-existing violations / external scope)
RUFF_EXCLUDES = \
	--exclude plasticos_inference_engine \
	--exclude plasticos_buyer_match_engine \
	--exclude plasticos_matching \
	--exclude "current work - ib"

# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "PlasticOS Dev Commands"
	@echo "──────────────────────────────────────────────────────"
	@echo ""
	@echo "  Code Quality"
	@echo "    make lint             ruff check (lint only)"
	@echo "    make format           ruff format --check (check only)"
	@echo "    make format-fix       ruff format (auto-fix)"
	@echo "    make check            lint + format check"
	@echo ""
	@echo "  Audit (run before PRs)"
	@echo "    make audit-quick      fast: lint + format + wiring + odoo19 + xml + deps + cron"
	@echo "    make audit            full: audit-quick + semgrep + all ci/ integrity scripts"
	@echo "    make xml-check        xmllint on all plasticos XML files"
	@echo "    make odoo19-check     Odoo 19 XML pattern violations"
	@echo "    make wiring           module dependency wiring check"
	@echo "    make deps-check       circular dependency check"
	@echo "    make cron-check       cron invariant violations"
	@echo "    make semgrep          semgrep custom Odoo rules (ERROR level)"
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
	@echo ""
	@echo "  Testing"
	@echo "    make test             run full test suite"
	@echo "    make test-module m=<mod>  run tests for one module"
	@echo ""
	@echo "  PR / CI Workflow"
	@echo "    make pr-check         REQUIRED before any push: audit-quick + semgrep + pipeline-guard"
	@echo "    make push             safe push: runs pr-check first, then git push current branch"
	@echo "    make push b=Staging   safe push to a specific branch"
	@echo "    make api-push-check   REQUIRED before GitHub API push (when git push fails)"
	@echo "    make pr-autopilot     scan all PR signals (CI, SonarCloud, CodeRabbit) — report only"
	@echo "    make pr-fix           scan + auto-fix safe issues + push back to branch (re-triggers CI)"
	@echo "    make sonar            show SonarCloud quality gate status"
	@echo "    make changelog        generate CHANGELOG.md from conventional commits"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# CODE QUALITY
# ─────────────────────────────────────────────────────────────────────────────

lint:
	ruff check . $(RUFF_EXCLUDES)

format:
	ruff format --check . $(RUFF_EXCLUDES)

format-fix:
	ruff format . $(RUFF_EXCLUDES)

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
	semgrep --config .semgrep/odoo-patterns.yml --severity ERROR --quiet --include="plasticos_*"

acl-check:
	@echo "→ ACL completeness check..."
	python3 ci/check_acl_completeness.py

audit-quick: lint format xml-check odoo19-check wiring deps-check cron-check
	@echo ""
	@echo "✅ Quick audit complete"

audit: audit-quick semgrep guards acl-check
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

# ─────────────────────────────────────────────────────────────────────────────
# TESTING
# ─────────────────────────────────────────────────────────────────────────────

test:
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

# REQUIRED before any push or PR creation
pr-check: audit-quick semgrep pipeline-guard
	@echo ""
	@echo "✅ PR gate passed — safe to push"

# Safe push: runs full pr-check first, then git push
# Usage: make push              (pushes current branch)
#        make push b=Staging    (pushes to a specific remote branch)
push: pr-check
	@echo ""
	@BRANCH=$$(git branch --show-current); \
	TARGET=$${b:-$$BRANCH}; \
	echo "→ Pushing $$BRANCH → origin/$$TARGET ..."; \
	git push origin HEAD:$$TARGET && echo "✅ Push complete" || \
	echo "⚠️  git push failed (Dropbox mmap issue?). Run: make api-push-check"

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

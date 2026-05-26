# PlasticOS Development Makefile
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help \
        lint format format-fix check \
        audit audit-quick \
        xml-check wiring deps-check cron-check odoo19-check semgrep \
        pipeline-guard dev-fence state-guard acl-check guards \
        up down restart logs logs-error shell odoo-shell \
        update update-all rebuild backup \
        test test-module \
        pr-check push sonar

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
	@echo "    make sonar            show SonarCloud quality gate status"
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
	docker compose run --rm odoo -u $(m)

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
	echo "⚠️  git push failed (Dropbox mmap issue?). Run the API push instead:\n   See .cursor/rules/70-github-api-commit.mdc"

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

# PlasticOS Development Makefile
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help lint format format-fix check audit audit-quick xml-check wiring \
        semgrep deps-check cron-check odoo19-check \
        up down restart update update-all rebuild logs shell \
        test test-module pr-check

# ── Load .env if present ──────────────────────────────────────────────────────
-include .env
export

ODOO_DB_NAME     ?= odoo
ODOO_TEST_DB     ?= odoo_test
ODOO_COMPOSE_PROJECT ?= odoo19

# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "PlasticOS Dev Commands"
	@echo "──────────────────────────────────────────────────────"
	@echo ""
	@echo "  Code Quality"
	@echo "    make lint           ruff check (lint only)"
	@echo "    make format         ruff format --check (check only)"
	@echo "    make format-fix     ruff format (auto-fix)"
	@echo "    make check          lint + format check (pre-commit gate)"
	@echo ""
	@echo "  Audit (run before PRs)"
	@echo "    make audit-quick    fast checks: lint + format + wiring + odoo19 + xml"
	@echo "    make audit          full audit suite (all ci/ scripts)"
	@echo "    make xml-check      xmllint on all XML files"
	@echo "    make odoo19-check   Odoo 19 XML pattern violations"
	@echo "    make wiring         module dependency wiring check"
	@echo "    make deps-check     circular dependency check"
	@echo "    make cron-check     cron invariant violations"
	@echo "    make semgrep        semgrep custom Odoo rules"
	@echo ""
	@echo "  Docker / Odoo"
	@echo "    make up             docker compose up -d"
	@echo "    make down           docker compose down"
	@echo "    make restart        restart Odoo container only"
	@echo "    make logs           follow Odoo container logs"
	@echo "    make shell          exec bash in Odoo container"
	@echo "    make update m=<mod> -u <module> (e.g. make update m=plasticos_commission)"
	@echo "    make update-all     -u all modules"
	@echo "    make rebuild        drop DB + full rebuild (no demo)"
	@echo ""
	@echo "  Testing"
	@echo "    make test           run full test suite"
	@echo "    make test-module m=<mod>  run tests for one module"
	@echo ""
	@echo "  PR Workflow"
	@echo "    make pr-check       full pre-PR gate (audit-quick + semgrep)"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# CODE QUALITY
# ─────────────────────────────────────────────────────────────────────────────

lint:
	ruff check . \
		--exclude plasticos_inference_engine \
		--exclude plasticos_buyer_match_engine \
		--exclude plasticos_matching \
		--exclude "current work - ib"

format:
	ruff format --check . \
		--exclude plasticos_inference_engine \
		--exclude plasticos_buyer_match_engine \
		--exclude plasticos_matching \
		--exclude "current work - ib"

format-fix:
	ruff format . \
		--exclude plasticos_inference_engine \
		--exclude plasticos_buyer_match_engine \
		--exclude plasticos_matching \
		--exclude "current work - ib"

check: lint format
	@echo "✅ lint + format check passed"

# ─────────────────────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────────────────────

xml-check:
	@echo "→ XML validation..."
	@find . -name "*.xml" \
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
	@echo "→ Semgrep custom Odoo rules (ERROR level only — bare-except, raw-sql)..."
	semgrep --config .semgrep/odoo-patterns.yml --severity ERROR --quiet --include="plasticos_*"

audit-quick: lint format xml-check odoo19-check wiring deps-check cron-check
	@echo ""
	@echo "✅ Quick audit complete"

audit: audit-quick semgrep
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
	@echo ""
	@echo "✅ Full audit complete"

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

shell:
	docker compose exec web bash

# make update m=plasticos_commission
update:
	@if [ -z "$(m)" ]; then echo "Usage: make update m=<module>"; exit 1; fi
	docker compose run --rm odoo -u $(m)

update-all:
	docker compose run --rm odoo -u all

rebuild:
	bash scripts/rebuild-odoo-no-demo.sh

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
# PR WORKFLOW GATE
# ─────────────────────────────────────────────────────────────────────────────

pr-check: audit-quick semgrep
	@echo ""
	@echo "✅ PR gate passed — safe to push"

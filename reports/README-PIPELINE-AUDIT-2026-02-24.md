# /readme Pipeline Audit — 2026-02-24

## Executive Summary

Audit of the `/readme` slash command and README generation pipeline. Improvements implemented for:
1. **Repo-agnostic** operation (Odoo, Python, generic)
2. **AST-heavy parsing** for accurate structure extraction
3. **Core docs discovery** — read 18 standard docs when present to enrich module READMEs

---

## Current State (Pre-Audit)

| Component | Location | Status |
|-----------|----------|--------|
| Command | `.cursor-commands/commands/readme-dag.md` | Exists, references DAG |
| DAG | `.cursor/workflows-synced/dags/readme_pipeline_dag.py` | **Not in repo** (governance-synced) |
| Generator | `.cursor/workflows-synced/scripts/generate_subsystem_readmes.py` | **Not in repo** |
| Config | `config/subsystems/readme_config.yaml` | Exists, Odoo-specific |
| Fallback script | `scripts/` (per 02-slash-commands) | **Did not exist** |

### Gaps Identified

1. **No local generator** — Pipeline depends on governance-synced files; Odoo repo has no fallback.
2. **No AST parsing** — `export_odoo_index.py` has rich AST/regex extraction but is not used by README pipeline.
3. **No core docs injection** — Standard docs (ARCHITECTURE.md, DEPLOYMENT.md, etc.) not read when generating READMEs.
4. **Odoo-specific config** — Template and structure assume Odoo modules; not reusable for generic Python.

---

## Core Docs Catalog (from ai files to harvest)

When present in the repo, these files are read and used to enrich README content:

### Core Documentation (10)
- ARCHITECTURE.md, API_REFERENCE.md, DATA_MODEL.md, WORKFLOW_GUIDE.md
- TEST_STRATEGY.md, DEPLOYMENT.md, MIGRATION_GUIDE.md, SECURITY_MODEL.md
- CHANGELOG.md, ROADMAP.md

### Configuration (2)
- ENVIRONMENT_SPEC.yaml, NEO4J_ONTOLOGY.yaml

### User Guides (6)
- README.md, QUICK_START.md, CONTRIBUTING.md, GLOSSARY.md, FAQ.md, LICENSE

**Search paths:** repo root, `docs/`, `doc/`, `.cursor/docs/`

---

## Improvements Implemented

1. **`scripts/generate_subsystem_readmes.py`** — Repo-agnostic generator with:
   - AST parsing for Python modules (classes, functions, docstrings)
   - Odoo detection: `__manifest__.py` + model extraction (reuses export_odoo_index patterns)
   - Core docs discovery and snippet injection
   - Auto-config creation when missing

2. **`readme_config.yaml` schema extension** — Optional `core_docs` and `doc_search_paths`

3. **`readme-dag.md`** — Updated with AST behavior, core docs list, and fallback script path

---

## AST Parsing Strategy

| Repo Type | AST/Parse Usage |
|-----------|-----------------|
| Odoo | `ast.literal_eval` for `__manifest__.py`; regex + AST for model `_name`, `_description`, fields |
| Python | `ast.parse()` → visit `Module`, `ClassDef`, `FunctionDef`; extract docstrings |
| Generic | Directory scan + file-type detection; minimal AST for `.py` files |

---

## Success Criteria

- [ ] Generator runs in Odoo repo without governance-synced files
- [ ] Generator runs in generic Python repo (creates minimal config)
- [ ] Core docs found in `docs/` or root are read and injected
- [ ] Model/class/function lists derived from AST, not regex-only

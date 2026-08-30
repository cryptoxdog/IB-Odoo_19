# INVARIANTS.md — PlasticOS System Invariants

**Purpose**: Unchangeable rules that govern the PlasticOS codebase.
**Status**: Constitutional
**Enforcement**: Machine + Human
**Version**: 2.2.0
**Last Updated**: 2026-08-30

## Meta-Rule

**If code violates an invariant, code is wrong — not invariant.**

---

## Core Invariants

### 1. Odoo 19 Compliance

**Rule**: No deprecated Odoo patterns.

**Forbidden Patterns**:
- ❌ `_sql_constraints` → Use `models.Constraint` / `UniqueConstraint`
- ❌ `@api.depends("id")` → Remove `"id"` from depends
- ❌ `@api.one` / `@api.multi` → Removed in Odoo 13
- ❌ `category_id` on `res.groups` → Removed in Odoo 19
- ❌ `numbercall` on `ir.cron` → Deprecated
- ❌ `<tree>` in views → Use `<list>`
- ❌ `string="..."` on `<search>` → Remove it
- ❌ `attrs="{...}"` on fields → Use `invisible="..."` / `readonly="..."` / `required="..."` directly
- ❌ `states={"done": [("readonly", True)]}` → Use `readonly="state == 'done'"`
- ❌ `t-esc=` in templates → Use `t-out=`
- ❌ `decoration-secondary=` on list columns → Removed
- ❌ `x_` prefixed fields → Use proper field names

**Detection**: `scripts/check_odoo_patterns.sh` (24 checks), `ci/check_odoo19_xml.py`, `ci/check_odoo19_hooks.py`

**Enforcement**: Pre-commit hook + CI pipeline (`static-checks` in `test-quality.yml` and `odoo-audit.yml`)

---

### 2. Dependency Graph Acyclicity

**Rule**: Module dependency graph must be a DAG (Directed Acyclic Graph).

**Prohibited**:
- ❌ Circular dependencies: A → B → A
- ❌ Transitive cycles: A → B → C → A
- ❌ Import from module not listed in `depends` in `__manifest__.py`

**Detection**:
```bash
python3 scripts/check_module_wiring.py     # dependency + __init__.py wiring
python3 ci/check_circular_deps.py          # circular dependency detection
```

**Enforcement**: Pre-commit hooks (`module-wiring`, `circular-deps`) + CI (`static-checks`)

---

### 3. Namespace Consistency

**Rule**: Use `plasticos_` prefix universally.

**Required**:
- ✅ Module names: `plasticos_<module>`
- ✅ Model names: `plasticos.<model>`
- ✅ External IDs: `plasticos_<module>.<external_id>`
- ✅ Class names: `Plasticos<Model>` (not `Plastos<Model>`)

**Forbidden**:
- ❌ `plastos_` (namespace drift — caught by CI check #8)
- ❌ `plast_` (abbreviation)
- ❌ Mixed conventions
- ❌ `self.env.get("model.name")` anti-pattern (caught by CI check #24)

**Detection**: `scripts/check_odoo_patterns.sh` checks #8 and #24

---

### 4. Deterministic Seed Doctrine

**Rule**: All reference data versioned in XML with `noupdate="1"`.

**Required**:
- ✅ Partner tags, material taxonomy, payment terms, chart of accounts in XML
- ✅ External IDs on all seed records
- ✅ Module-prefixed `ref()` calls: `ref('plasticos_module.record_id')`

**Forbidden**:
- ❌ Runtime CSV bootstrap
- ❌ Python seed generation (except migrations)
- ❌ Hardcoded database IDs
- ❌ `ref="record_id"` without module prefix (caught by CI check #10)
- ❌ Unescaped `&` in XML (caught by CI check #6)
- ❌ Nested double quotes in `eval` (caught by CI check #11)

**Enforcement**: Code review, `ci/check_odoo19_xml.py`, `scripts/check_odoo_patterns.sh`

---

### 5. Graph Isolation Boundary

**Rule**: Neo4j integration must not break Odoo registry.

**Required**:
- ✅ Neo4j imports wrapped in try/except
- ✅ Graph failures return empty results
- ✅ No Neo4j imports in `__init__.py` registry load
- ✅ Connection timeout defined
- ✅ Lazy driver initialization (not at import time)

**Forbidden**:
- ❌ Graph failures raise unhandled exceptions
- ❌ Neo4j driver imported at module load (`from neo4j import ...` at top level)
- ❌ Blocking Odoo startup on Neo4j availability
- ❌ Writing canonical business data only to Neo4j
- ❌ Using graph results inside `@api.constrains` as authority

**Enforcement**: Code review, integration tests, `ci/check_pipeline_v2_guard.py`

---

### 6. Partner Architecture Integrity

**Rule**: Use native Odoo partner fields + isolated capability profiles.

**Required**:
- ✅ `company_type` for entity type
- ✅ `customer_rank` / `supplier_rank` for business role
- ✅ `category_id` for partner tags
- ✅ `plasticos.facility.profile` for capabilities (One2many)

**Forbidden**:
- ❌ Custom partner role booleans (`is_buyer`, `is_supplier`)
- ❌ Material profiles attached directly to `res.partner`
- ❌ Capability fields on `res.partner` model

**Enforcement**: Architectural review, module wiring check

---

### 7. Layer Dependency Direction

**Rule**: Higher layers depend on lower layers, never reverse.

**Dependency Flow**:
```
Transaction Layer (5)
    ↓ depends on
Compliance Layer (4)
    ↓ depends on
Commercial Layer (3)
    ↓ depends on
Capability Layer (2)
    ↓ depends on
Material Layer (1)
```

**Forbidden**:
- ❌ Material layer depending on transaction layer
- ❌ Intake depending on documents
- ❌ Capability depending on commercial

**Enforcement**: Dependency graph analysis, `scripts/check_module_wiring.py`

---

### 8. Security Model Completeness

**Rule**: Every model requires ACL and record rules.

**Required**:
- ✅ `security/ir.model.access.csv` in every module with models
- ✅ CSV included in `__manifest__.py` `data` list
- ✅ Record rules for multi-company isolation
- ✅ Group-based access control (manager CRUD, user CRU, readonly R)

**Forbidden**:
- ❌ Models without ACL file
- ❌ `sudo()` without explicit justification comment
- ❌ World-readable sensitive fields

**Enforcement**: `ci/check_acl_completeness.py` (warn-only), `ci/enhanced_audit.py`

---

### 9. External ID Referential Integrity

**Rule**: All `ref="..."` must point to existing external IDs.

**Required**:
- ✅ External IDs defined before use
- ✅ No duplicate external IDs across modules
- ✅ Seed data loading order enforced by dependencies

**Forbidden**:
- ❌ `ref="module.nonexistent_id"`
- ❌ Duplicate external IDs
- ❌ Orphaned XML records

**Detection**: `ci/check_orphan_model_refs.py`

---

### 10. Test Isolation

**Rule**: Tests must not mutate seed data or production database.

**Required**:
- ✅ Use dedicated test database (`odoo_test`)
- ✅ Transactional rollback after tests
- ✅ No test data committed to seed XML

**Forbidden**:
- ❌ Tests writing to production database
- ❌ Test data in `data/*.xml` files
- ❌ Tests assuming specific database state

**Enforcement**: Test suite configuration, code review

---

### 11. API Dependency Isolation

**Rule**: External API failures must not crash Odoo.

**Required**:
- ✅ OpenAI API wrapped in try/except
- ✅ API failures return safe defaults (e.g., COLD classification)
- ✅ Rate limiting handled
- ✅ API keys in environment variables (never hardcoded)
- ✅ `temperature=0.0` for deterministic LLM outputs

**Forbidden**:
- ❌ Unhandled OpenAI exceptions
- ❌ Hardcoded API keys (caught by `gitleaks` + `secret-scan` CI)
- ❌ Blocking operations without timeout

**Enforcement**: Code review, integration tests, `security.yml` CI

---

### 12. Model Name Uniqueness

**Rule**: No duplicate `_name` across all modules.

**Required**:
- ✅ Unique `_name` for each model
- ✅ Use `_inherit` for extensions (no new `_name`)
- ✅ `_name` MUST be a string literal — never a variable or constant

**Forbidden**:
- ❌ Two modules defining `plasticos.intake`
- ❌ Model name collision with Odoo core
- ❌ `_name = SOME_CONSTANT` (caught by `odoo-audit.yml` `_name` check)

**Detection**: `scripts/check_module_wiring.py`, `odoo-audit.yml` enforce-string-literal step

---

### 13. Field Reference Safety

**Rule**: All field references must exist before use.

**Required**:
- ✅ Fields defined before `@api.depends`
- ✅ Related fields point to existing paths
- ✅ Computed fields reference valid fields
- ✅ Every `@api.constrains(...)` field name must exist on the model
- ✅ Every `fields.Many2one` MUST have `ondelete=` parameter

**Forbidden**:
- ❌ `@api.depends("nonexistent_field")`
- ❌ `related="missing.path"`
- ❌ Undefined field in compute method
- ❌ Related fields using old intake paths without `_id` suffix (caught by CI check #18)

**Detection**: Odoo registry load errors, `ci/check_field_integrity.py`, `ci/check_automation_field_refs.py`

---

### 14. Migration Safety

**Rule**: Migrations must be idempotent and safe.

**Required**:
- ✅ Migrations check before modify
- ✅ No data loss on rollback
- ✅ Version numbering enforced

**Forbidden**:
- ❌ Destructive migrations without backup
- ❌ Non-idempotent operations
- ❌ Missing version tags

**Enforcement**: Code review, staging environment testing

---

### 15. Cron Job Discipline

**Rule**: Cron jobs must have safe failure modes.

**Required**:
- ✅ Cron failures logged, not raised
- ✅ Idempotent operations
- ✅ `active="False"` by default for production safety
- ✅ `model_id` refs must include module prefix: `ref="plasticos_module.model_plasticos_model"`
- ✅ No `numbercall` attribute (deprecated)

**Forbidden**:
- ❌ Crons crashing on failure
- ❌ Non-idempotent batch operations
- ❌ Auto-enabled crons in production
- ❌ `ref="model_plasticos_load"` without module prefix (caught by CI check #10)

**Enforcement**: `tools/cron_invariant_check.py`, `scripts/check_odoo_patterns.sh` check #5 and #10

---

### 16. Cross-Addon Import Safety

**Rule**: No top-level cross-addon imports in model files.

**Required**:
- ✅ All `from odoo.addons.plasticos_*` imports must be inside functions (lazy loading)
- ✅ Use `_get_<thing>()` helper functions for deferred imports

**Forbidden**:
- ❌ `from odoo.addons.plasticos_other.models.file import Class` at top level
- ❌ Top-level imports that depend on module initialization order

**Pattern**:
```python
def _get_inference_classes():
    from odoo.addons.plasticos_inference_engine.engine import InferenceEngine
    return InferenceEngine
```

**Enforcement**: `ci/check_pipeline_v2_guard.py`, code review

---

### 17. File Wiring Completeness

**Rule**: Every Python file in a module must be registered.

**Required**:
- ✅ Every `.py` file in `models/` has a `from . import <file>` in `models/__init__.py`
- ✅ Every `.py` file in `controllers/` has a `from . import <file>` in `controllers/__init__.py`
- ✅ Every `.py` file in `wizards/` has a `from . import <file>` in `wizards/__init__.py`
- ✅ No empty `__init__.py` in `plasticos_*` module roots

**Forbidden**:
- ❌ Python file exists but no import in `__init__.py` (models won't load)
- ❌ Empty `__init__.py` in module root (caught by CI check #7)

**Detection**: `scripts/check_module_wiring.py`, `ci/check_package_init.py`

---

### 18. XML View Compatibility

**Rule**: Views must use Odoo 19 syntax exclusively.

**Required**:
- ✅ `<list>` not `<tree>` (CI check #12)
- ✅ No `string=` on `<search>` (CI check #13)
- ✅ No `string=` on `<group>` in search views (CI check #14)
- ✅ No `attrs=` attribute (CI check #19) — use `invisible=`, `readonly=`, `required=` directly
- ✅ No `states=` attribute (CI check #20)
- ✅ Font Awesome `<i>` tags must have `title=` (CI check #21, accessibility)
- ✅ XPath anchored to stable nodes

**Forbidden**:
- ❌ `<tree>`, `attrs=`, `states=`, `string=` on search, `decoration-secondary=`, `t-esc=`

**Detection**: `scripts/check_odoo_patterns.sh` checks #12–21, `ci/check_odoo19_xml.py`, `ci/check_xpath_stability.py`

---

## CI Enforcement Map

Every invariant is enforced by one or more automated tools:

| Invariant | Pre-commit Hook | CI Workflow | Script |
|-----------|----------------|-------------|--------|
| 1. Odoo 19 Compliance | `odoo-patterns` | `static-checks` | `check_odoo_patterns.sh` |
| 2. DAG Dependencies | `module-wiring`, `circular-deps` | `static-checks` | `check_module_wiring.py`, `check_circular_deps.py` |
| 3. Namespace | `odoo-patterns` | `static-checks` | `check_odoo_patterns.sh` #8 |
| 5. Graph Isolation | `pipeline-v2-guard` | — | `check_pipeline_v2_guard.py` |
| 8. Security/ACL | `acl-completeness` (warn) | `audit` | `check_acl_completeness.py`, `enhanced_audit.py` |
| 9. External IDs | `orphan-model-refs` | `static-checks` | `check_orphan_model_refs.py` |
| 11. Secret Safety | — | `secret-scan` | `gitleaks` |
| 12. `_name` Literal | — | `odoo-audit.yml` | grep `_name = [A-Z]` |
| 13. Field Refs | `field-integrity`, `automation-field-refs` | `static-checks` | `check_field_integrity.py` |
| 15. Cron Safety | `cron-invariants` | — | `cron_invariant_check.py` |
| 17. File Wiring | `package-init`, `module-wiring` | `static-checks` | `check_package_init.py` |
| 18. XML Views | `odoo19-xml`, `xpath-stability` | `static-checks` | `check_odoo19_xml.py`, `check_xpath_stability.py` |
| 20. Legacy Vendor Identifier (BAN001) | `banned-identifier` | `static-checks` | `check_banned_identifier.py` |

---

### 19. Single External Intelligence Authority

**Rule**: Matching and enrichment **intelligence authority** is external and Gate-mediated.
Local Odoo algorithmic engines are not architectural authority.

**Authority** (binding):
[`docs/adr/ADR-003-single-external-intelligence-authority.md`](docs/adr/ADR-003-single-external-intelligence-authority.md)
(supersedes ADR-002 §2 fallback-as-authority). Hub topology and “never Odoo → CEG/EIE direct”
from ADR-002 remain in force.

**Required**:
- ✅ Odoo intelligence egress only through `plasticos_gate` → Constellation.Gate (`TransportPacket`)
- ✅ CEG owns match semantics; EIE owns converge/enrichment intelligence
- ✅ Cite the full ADR filename — numeric `ADR-003` alone is ambiguous (contact-import ADR shares the prefix)

**Forbidden**:
- ❌ Treating `plasticos_buyer_match_engine`, local Neo4j matcher paths, or in-Odoo enrichment
  crawl/extract/inference as the product authority for match/enrichment quality
- ❌ Direct Odoo → CEG/EIE HTTP or SDK bypass of Gate
- ❌ Restoring “local fallback as design” language in constitutional docs after this invariant

**Note**: M7 physically retired `plasticos_buyer_match_engine` and `plasticos_inference_engine`
from the repository. M8 (TASK-052) activates **blocking** drift guards in Makefile, pre-commit,
and CI via `ci/check_no_local_intelligence.py` — reintroduction of retired modules or
consumer-path local authority fails the build.

**Detection**: `tests/contracts/test_external_intelligence_authority.py`, `tests/contracts/test_no_local_intelligence.py`, `ci/check_no_local_intelligence.py`

**Enforcement**: Blocking contract tests + CI/pre-commit/Makefile drift guard + Gate consumer docs (`docs/track_b/04_*`)

---

### 20. Legacy Vendor Identifier Prohibition (BAN001)

**Rule**: The legacy vendor identifier designated **BAN001** is permanently prohibited from
every tracked repository path and every tracked repository content byte, in **every casing**.

BAN001 denotes the 8-character ASCII sequence with code points
`99, 105, 101, 116, 114, 97, 100, 101`. This document, the guard, the CI wiring, and the
guard's tests deliberately never spell that sequence contiguously — a policy that named its
own banned string would violate itself.

**Scope** (no carve-outs): application source, tests, fixtures, documentation, comments,
configuration, manifests, Odoo metadata (models, fields, views, external IDs, security files,
data files), migrations, generated artifacts, filenames, directory names, symlink targets, and
binary files.

**Exceptions**: **NONE.** BAN001 has no exclusion list, no allowlist, no ignore comment, and no
per-file waiver. It does not appear in the *Known False Positives* table below and must never be
added to it. Satisfying this invariant by suppressing the scanner is itself a violation.

**Generated content**: generated output is fully in scope. Repair the canonical source or the
generator and regenerate — never hand-patch a generated artifact that would reintroduce the
sequence on the next run, and never exempt it.

**Historical content**: files that are old, archival, captured from an external system, or kept
for compatibility are **not** exempt while they are in the active tracked tree.

**Deployed legacy identifiers**: where a real external server, database, or column name must be
addressed, supply it at run time (environment variable, parameter, or programmatic
reconstruction). Do not store the contiguous sequence in repository bytes to preserve a
connection default.

**Detection**: `ci/check_banned_identifier.py` — the single canonical implementation, invoked
identically by CI, `make ban-check`, and the `banned-identifier` pre-commit hook. It reads
every tracked path and its content from the **git index** — not the worktree, so a staged
violation cannot be hidden by deleting the file, and an unrelated deletion in a dirty tree
cannot false-block the build. It inspects every path component, resolves every symlink target
from the same index, and matches raw bytes, so binary files are covered. It fails closed: an
unreadable index or object exits non-zero rather than reporting clean.

**Enforcement**: blocking. `ci.yml` → `static-checks` (aggregated by `ci-gate-result`), plus
`tests/test_banned_identifier_guard.py`, which proves the guard rejects lowercase, uppercase,
capitalized and mixed-case content matches, filename-only matches, directory-name-only matches,
symlink-target matches (including a symlink absent from the worktree), binary matches, and
content staged then deleted on disk — while allowing near-miss lookalikes and not
false-blocking on an unrelated deletion. Violating fixtures are built at run time in a temporary repository, so no
prohibited literal is ever committed.

**Violation effect**: CI failure.

---

## Known False Positives

These patterns are excluded from CI checks because they are valid code, not violations:

| Check | Excluded File/Path | Reason |
|-------|-------------------|--------|
| Many2one string write (#22) | `ai_normalizer.py` | LLM prompt JSON schema, not field assignment |
| Many2one string write (#22) | `graph_service.py`, `matcher.py` | Dict/API payloads, not ORM writes |
| Many2one string write (#22) | `enrichment_service.py`, `material_profile.py` | Dict construction, not ORM writes |
| `self.env.get()` (#24) | `ci/*.py` | CI scripts contain detection patterns |
| Unescaped `&` (#6) | Lines with `&amp;`, `&lt;`, `&gt;`, `&quot;` | Valid XML entities |
| `<tree>` (#12) | `tree.txt` | Index file, not Odoo view |
| Ruff lint | `plasticos_inference_engine`, `plasticos_buyer_match_engine`, `plasticos_matching` | Excluded in `pr-gate.yml` ruff step |
| mypy | `plasticos_web_leads`, `plasticos_enrichment`, `plasticos_buyer_match_engine` | Complex recordset patterns, gradual typing |
| ACL completeness | all modules | Non-blocking (warn-only hook) |
| Odoo patterns script | all workflows | `|| true` — tracked separately, non-blocking in CI |

---

## Enforcement Strategy

### Automated Checks
- **Pre-commit hooks**: 36 hooks including ruff, module wiring, XML validation, cron invariants, secret scan (gitleaks)
- **CI/CD pipeline**: 11 workflow files; `ci.yml` is the single blocking gate (lint → static-checks → pure-python-tests)
- **Module wiring script**: Dependency graph + `__init__.py` validation

### Manual Reviews
- **Architectural review**: Layer violations, partner model changes
- **Security audit**: ACL completeness, sensitive data exposure
- **Code review**: API isolation, error handling

### Violation Response
1. **Block merge**: If automated check fails
2. **Request remediation**: If manual review finds violation
3. **Document exception**: If invariant must be violated (rare, requires approval)

---

## Invariant Change Process

**Invariants are constitutional.**

To modify an invariant:
1. Propose change with justification
2. Architectural review and approval
3. Update INVARIANTS.md
4. Update enforcement tooling
5. Remediate existing codebase

**No silent invariant violations.**

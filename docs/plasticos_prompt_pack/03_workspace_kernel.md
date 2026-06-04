# PlasticOS Odoo 19 — Workspace Kernel (Git-Max, Warning-Driven)
# Kernel ID: plasticos.workspace.odoo19.git_max.v4
# Supersedes: prompt.action.odoo-5.md
# Refinements: Docker/make commands; pipeline_v2 HARD ABORT; PlasticOS ontology updated;
#              web lead regression hotspots; Odoo 19 compliance table.

## Execution Mode

- Git-first, repo-index aware, documentation-aligned
- Warning-driven: emit INFO / WARNING / BLOCKER — never abort silently
- No fail-closed abort except HARD BLOCKERs

---

## Pre-Code Requirements (Mandatory, Non-Blocking Unless Stated)

### 1. Git as Primary Source of Truth

Priority order:
1. MCP `get_file_contents`, `search_code` on `cryptoxdog/IB-Odoo_19`
2. `git ls-tree -r`, `git grep`, `git show`, `git diff`
3. `reports/repo-index/*` inventory fallback

If repo visibility limited:
```
WARNING: REPO VISIBILITY LIMITED — continuing in guarded mode
```

### 2. Repo Index Reconciliation

Reconcile against before any code:
- Model registry (all `_name` and `_inherit` declarations)
- External ID registry (all `<record id=...>`)
- Dependency graph (`__manifest__.py` `depends`)
- Test catalog (`tests/test_*.py` and `tests/plasticos_*/`)
- Space system prompt (module map, hard rules, active TODOs)

If conflict detected:
```
BLOCKER:
  Type: <missing model / broken ref / circular dep>
  File: <path>
  Impact: <what breaks>
  Recommended Fix: <specific action>
```

### 3. Odoo 19 Compliance

| Check | Correct Pattern |
|---|---|
| View arch root | `<list>` not `<tree>` |
| QWeb escaping | `t-out` not `t-esc` |
| SQL constraints | `models.Constraint` class |
| Group field | `groups_id` not `group_ids` |
| XPath anchors | Named only — no positional `//field[1]` |

If deprecated pattern detected:
```
WARNING: ODOO19_DEPRECATION_DETECTED
  Pattern: <what was found>
  File: <path>
  Fix: <correct pattern>
```

### 4. PlasticOS Ontology Boundary Enforcement

Layer boundaries — do NOT cross-wire:

| Layer | Modules |
|---|---|
| Material | `plasticos_material_profile`, `plasticos_intake_normalizer` |
| Capability | `plasticos_buyer_match_engine`, `plasticos_facility_profile` |
| Commercial | `plasticos_offer`, `plasticos_transaction`, `plasticos_commission` |
| Compliance | `plasticos_claims`, `plasticos_security_base` |
| Transaction | `plasticos_transaction`, `plasticos_accounting`, `plasticos_logistics` |
| AI/Inference | `plasticos_inference_engine` (pure-Python only), `plasticos_enrichment` (stub) |
| Intake | `plasticos_intake`, `plasticos_web_leads` |

If cross-layer drift introduced:
```
WARNING: LAYER_BOUNDARY_VIOLATION
  Layers: <source> → <target>
  File: <path>
  Reason: <what constraint is violated>
```

### 5. Pipeline v2 Hard Block (HARD ABORT)

```python
# This check runs BEFORE any code generation involving inference engine
if "pipeline_v2" in changed_files or "pipeline_v2" in any_import:
    HARD_ABORT: "pipeline_v2.py has broken imports and is explicitly deferred. "
               "DO NOT import, activate, or reference it. "
               "CI gate: ci/check_pipeline_v2_guard.py will reject any deploy touching this file."
```

This is the only condition that causes a HARD ABORT with no continue option.

---

## Namespace Policy

Standard prefix: `plasticos_*`

Known drift (emit `WARNING: NAMESPACE_DRIFT_DETECTED`):
- `PlastosFacilityCapability` → should be `plasticos_facility_capability`
- `PlastosMaterialProfile` → should be `plasticos_material_profile`
- Old-style `_sql_constraints` tuples → should use `models.Constraint`

---

## Web Lead Regression Hotspots (AGENT: DO NOT REWIRE)

Three patterns in `plasticos_web_leads/models/web_lead.py` that agents consistently mis-fix:

1. **`self.intake_id` single write** — `# AGENT: DO NOT REWIRE` in file. PR #83 fixed double-write. Single write is correct.
2. **Partner-deferral write block** — `# AGENT: DO NOT REWIRE` in file. Intentional guard on `intake_created` records; not a bug.
3. **`_find_or_create_partner()`** — DEPRECATED 2026-02-23. Do not re-introduce in any code path.

Before ANY change to `web_lead.py`: run `tests/test_web_lead*.py` first.

---

## Test Safety Layer

Before modifying these critical modules, cross-check test catalog:

| Module | Risk |
|---|---|
| `plasticos_transaction` | Commission lifecycle, sequence integrity |
| `plasticos_commission` | Circular dep with transaction; non-fatal but sensitive |
| `plasticos_web_leads` | HOT/COLD classification, write guard, sudo path |
| `plasticos_intake` | Matching trigger, offer flow |
| `plasticos_buyer_match_engine` | Stub gates, Neo4j scoring |

If test impact risk:
```
WARNING: TEST_IMPACT_RISK
  Affected tests: <list>
  Risk: <behavior that might break>
```

---

## Migration Awareness

If module has migration scripts:
```
INFO: MIGRATION_CHAIN_PRESENT
  Module: <module>
  Version: <from> → <to>
```

For DB migrations, always use:
```bash
make update m=<module>
```
Never alter version logic or migration scripts without explicit instruction.

---

## Seed Data Rule

- XML-first with deterministic external IDs
- Avoid runtime CSV in post-install hooks
- Dependency order: security → data → views → cron
- No external ID collisions

If collision risk:
```
BLOCKER: EXTERNAL_ID_COLLISION_RISK
  File: <path>
  Collision: <xmlid>
  Resolution: <rename strategy>
```

---

## Execution Priority

1. Git repo visibility
2. Repo-index reconciliation
3. Odoo 19 compliance
4. Ontology boundary enforcement
5. Pipeline v2 guard — HARD ABORT if triggered
6. Namespace normalization
7. External ID collision prevention
8. Seed determinism
9. Test safety

---

## Warning / Blocker Format

```
INFO:    <non-actionable observation>
WARNING: <risk detected, continuing>
BLOCKER: <must resolve before output is safe>
HARD BLOCKER — MANUAL INTERVENTION REQUIRED: <abort condition>
```

HARD ABORT only for: pipeline_v2.py activation, direct data corruption, irreversible migration, confirmed duplicate `_name`, confirmed unresolvable duplicate XML ID.

---

## End State Signal

```
GIT_INDEX_DOC_VALIDATED_READY_FOR_CODE
```

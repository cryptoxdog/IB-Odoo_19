---
name: "CodeRabbit reviews no IB-Odoo_19 file: path_filters allowlist and dead base branches"
overview: "Make CodeRabbit review the files it is meant to review in cryptoxdog/IB-Odoo_19. .coderabbit.yaml reviews.path_filters carries four include patterns, which CodeRabbit treats as an allowlist; those four files are also excluded by !tests/**, so every PR file is skipped. Rewrite path_filters as exclusions only, keep the intended exclusions narrow, and point auto_review.base_branches at the real pr..."
todos:
  - id: T1
    content: "Replace the reviews.path_filters list with exclusions only: **/.venv/**, **/.mypy_cache/**, **/.pytest_cache/**, **/.ruff_cache/**, **/__pycache__/**, **/*.pyc, **/node_modules/**, odoo-enterprise/**, **/*.zip, plasticos_partner_import/erp_extracted_data/bulk/**, plasticos_partner_import/erp_extracted_data/meta/**, plasticos_partner_import/erp_extracted_data/diagnostics/**, docs/**/*.csv, ERP.WksDetail.Test.csv, each with a leading !. Drop the four include lines, the three test exclusions and the blanket !*.csv. Keep a comment stating that a pattern without ! turns the list into an allowlist."
    status: pending
    phase: execute
    depends_on: []
  - id: T2
    content: "Set reviews.auto_review.base_branches to [Production] (Staging is the default branch and is reviewed without being listed)."
    status: pending
    phase: execute
    depends_on: []
isProject: false
kind: simple
execute_via: cursor-build
status: current
kernel_pass:
  bound_path: "docs/plans/coderabbit_path_filters_c0de4ab1.plan.md"
  improve:
    ran_at: "2026-11-11T15:20:00Z"
    deltas:
      - "V2 replaced a prose description with an executable PurePath.full_match assertion over five keep and four drop sample paths"
      - "V3 made executable against the downloaded schema.v2.json; baseline run on the pre-change file recorded 0 schema errors"
      - "narrowed the ERP exclusion from erp_extracted_data/** to bulk/meta/diagnostics so the runtime SQL projection scripts stay reviewable"
      - "added the glob-semantics risk with V5 as the live witness"
  recursive_alignment:
    ran_at: "2026-11-11T15:21:00Z"
    deltas:
      - "every success criterion maps to a V id; gmp_handoff.may_modify equals scope.in (.coderabbit.yaml only)"
      - "deferred docker-compose/.env.example and the Quantum-L9 work are listed in scope.out and must_not_modify"
  validate_repair:
    ran_at: "2026-11-11T15:22:00Z"
    deltas:
      - "re-ran run_plan_pipeline.py after the Improve edits: PLAN_DOCUMENT and section receipt PASS"
    body_sha256: "0dd3e5380514ceacb2f733e57e4b153a2f91300b07c94358d2ace83d144fa428"
---

# PLAN: CodeRabbit reviews no IB-Odoo_19 file: path_filters allowlist and dead base branches

> **Projected by** `scripts/render_plan_pe_autonomy.py` from validated PLAN_DOCUMENT JSON.

> **First-class SSOT (git):** `environment/contracts/execution/templates/canonical.template.executable_plan.v1.plan.md` · metadata sidecar `*.meta.md` · registered in `environment/contracts/execution/MANIFEST.yaml`. Skill path is a symlink; `.cursor/plans/_TEMPLATE.plan.md` is a local mirror only.
> **Schema:** `canonical.schema.plan_document.v1` (status: fill → `executable` only when law holds)
> **Parameters:** every value is projected from PLAN_DOCUMENT. A value reading `unknown — …` or `unbound — …` is absent from PLAN_DOCUMENT and must be resolved before status becomes `executable`.
> **Execute:** when status is `executable`, press **Build**, stack on the unique open-PR tip if any open PR exists (`PR_STACK=auto`; never `origin/main`), then `PR_STACK=auto PR_REMEDIATE=0 make pr` and display the PR URL. Do **not** run `make campaign`, admit a Program Lock, or free-form mutate from this markdown alone.
> **Cursor todos:** frontmatter `todos` project to Build todos. Body is the binding contract.
> **File name:** `coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches_4620dad5.plan.md`
> **Law:** executable only when baseline matches, capability probes pass, invariants match, and envelope is respected. Markdown completeness alone is insufficient.

## Execute via Cursor Build

Press **Build**. Plan on the current workspace. Execute on the unique open-PR chain tip.

- If any open PR exists: **never** branch from `origin/main`. Start from the unique chain tip (`PR_STACK=auto`). Use `agent_worktree_start.sh` when this checkout is not already that tip. Sibling open-PR chains fail closed.
- If the board is empty: `origin/main` is allowed.
- Do not run `make campaign`.
- Do not admit a Program Lock or Controller lease.
- Do not write `Lock: origin/main = <sha>`.
- Do not open a new worktree from tip as a **planning** requirement.
- After Build todos complete: scoped-commit (pathspecs), `l4_local.py authorize-release`, then `PR_STACK=auto PR_REMEDIATE=0 make pr`. Do not skip `make pr`.
- The finish reply **must** display the opened PR URL as proof. Without that URL the Build is incomplete.

## Metadata

| Field | Value |
|-------|-------|
| plan_id | `plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| name | CodeRabbit reviews no IB-Odoo_19 file: path_filters allowlist and dead base branches |
| overview | Make CodeRabbit review the files it is meant to review in cryptoxdog/IB-Odoo_19. .coderabbit.yaml reviews.path_filters carries four include patterns, which CodeRabbit treats as an allowlist; those four files are also excluded by !tests/**, so every PR file is skipped. Rewrite path_filters as exclusions only, keep the intended exclusions narrow, and point auto_review.base_branches at the real promotion branch Production. |
| schema_version | `1.0.0` |
| status | `draft` — planning convergence is `partial` |
| is_project | `false` |
| owner | igor_beylin |
| created_at | 2026-11-11T15:08:30+00:00 |
| updated_at | 2026-11-11T15:08:30+00:00 |
| depth | `standard` |
| estimate | 1 small PR |

## Architect framing

| Field | Value |
|-------|-------|
| planning_ssot | validated PLAN_DOCUMENT JSON (`validate_plan_document.py`) |
| plan_class | `bounded_execution_contract` — PLAN_DOCUMENT mode `plan` |
| redesign_allowed | `false` |
| follow_on_schema_evolution_separate | `true` |
| framing_notes | Execute via Cursor Build; stacked make pr if any open PR exists; no redesign unless plan_class requires it |

## Immutable baseline

| Field | Value |
|-------|-------|
| captured_at | `2026-11-11T15:08:30+00:00` |
| repository | `cryptoxdog/IB-Odoo_19` |
| workspace | `/home/user/IB-Odoo_19` |
| branch | `ci/coderabbit-path-filters` |
| commit_sha | `64896c7fc976daa67d90ca51ff4570900ce7b0c7` |
| dirty | `true` |
| artifact_hashes | `{}` — none pinned by PLAN_DOCUMENT |
| allowed_local_dirt | none |
| overlap_policy | `stop_if_dirty_overlaps_may_modify` |
| verification_rule | `reverify_at_execution_start` |
| on_drift | `stop_and_replan` |

## Objective

### Mission

Make CodeRabbit review the files it is meant to review in cryptoxdog/IB-Odoo_19. .coderabbit.yaml reviews.path_filters carries four include patterns, which CodeRabbit treats as an allowlist; those four files are also excluded by !tests/**, so every PR file is skipped. Rewrite path_filters as exclusions only, keep the intended exclusions narrow, and point auto_review.base_branches at the real promotion branch Production.

### Scope in

- .coderabbit.yaml: reviews.path_filters and reviews.auto_review.base_branches

### Success properties

Each property's proof is the `final_validation` entry it names (by id or by script/file). A property with no proving validation, or only skipped / not_applicable ones, blocks `executable`.

| id | property | evidence_type | proof | blocking |
|----|----------|---------------|-------|----------|
| SP-01 | .coderabbit.yaml reviews.path_filters contains no pattern without a leading ! (V1) | `quality_gate` | V1: `python3 -c "import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']"` → exits 0; V2: `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"` → exits 0 (Python 3.13 PurePath.full_match approximates CodeRabbit glob matching; V5 is the live witness); V3: `curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c "import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))"` → exits 0; the same command on the pre-change file is the baseline (any pre-existing schema error is reported, not hidden); V5: `after make pr: read the CodeRabbit comment on the new PR` → no 'Review skipped due to path filters' for .coderabbit.yaml | `true` |
| SP-02 | a Python file, a docs/*.md file, a tests/test_*.py file and a security/ir.model.access.csv are not matched by any exclusion, while plasticos_partner_import/erp_extracted_data/bulk/*.csv and odoo-enterprise/** are (V2) | `quality_gate` | V2: `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"` → exits 0 (Python 3.13 PurePath.full_match approximates CodeRabbit glob matching; V5 is the live witness) | `true` |
| SP-03 | plasticos_partner_import/erp_extracted_data/*.sql projection scripts stay reviewable (V2) | `quality_gate` | V2: `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"` → exits 0 (Python 3.13 PurePath.full_match approximates CodeRabbit glob matching; V5 is the live witness) | `true` |
| SP-04 | auto_review.base_branches is exactly [Production] (V1) | `quality_gate` | V1: `python3 -c "import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']"` → exits 0 | `true` |
| SP-05 | the file parses as YAML and validates against https://coderabbit.ai/integrations/schema.v2.json (V3) | `quality_gate` | V3: `curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c "import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))"` → exits 0; the same command on the pre-change file is the baseline (any pre-existing schema error is reported, not hidden) | `true` |
| SP-06 | on the published PR, CodeRabbit no longer reports 'Review skipped due to path filters' for .coderabbit.yaml (V5) | `quality_gate` | V1: `python3 -c "import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']"` → exits 0; V2: `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"` → exits 0 (Python 3.13 PurePath.full_match approximates CodeRabbit glob matching; V5 is the live witness); V3: `curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c "import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))"` → exits 0; the same command on the pre-change file is the baseline (any pre-existing schema error is reported, not hidden); V5: `after make pr: read the CodeRabbit comment on the new PR` → no 'Review skipped due to path filters' for .coderabbit.yaml | `true` |

## Capability preflight

`schema_ref:` `canonical.schema.capability_preflight.v1`
`instance_binding:` `capability_preflight_ref` → `preflight.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1`

| Field | Value |
|-------|-------|
| preflight_id | `preflight.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| source_ref | `plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| phase_id | `preflight` |
| blocking | `true` |
| immutable_baseline_ref | `baseline.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| baseline_verified | `false` — reverify at execution start |
| drift_detected | `false` — baseline captured at render |

### Probes (from PLAN_DOCUMENT `pre_validation`; failed blocking probe → status `preflight_blocked`)

| id | capability | command_or_action | pass_criteria | blocking |
|----|------------|-------------------|---------------|----------|
| P1 | pre-validation (status `passed`) | `Read .coderabbit.yaml lines 56-80 and 235-238 on origin/Staging 64896c7; read CodeRabbit docs 'How path filters combine' via Context7 /websites/coderabbit_ai` | four include lines present; docs state includes restrict scope and exclusions win | `true` |
| P2 | pre-validation (status `passed`) | `git ls-files '*.csv' and ls plasticos_partner_import/erp_extracted_data` | the data grids are bulk/meta/diagnostics CSVs; the projection .sql scripts sit beside them and must stay reviewable; 25 security ACL CSVs exist | `true` |

## Execution envelope

Mutations outside this envelope are forbidden (PLAN-SCHEMA-004).

### Filesystem

- **write_allow:** `.coderabbit.yaml`
- **write_deny:** `docker-compose.yml`, `.env.example`, `any plasticos_* addon file`
- **delete_allow:** none — no Delete todo

### Commands

- **allow:** `V1`, `V2`, `V3`, `python3 -c "import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']"`, `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"`, `curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c "import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))"`, `.pre-commit-config.yaml hooks through make pr (check-yaml, trailing-whitespace, end-of-file-fixer)`, `after make pr: read the CodeRabbit comment on the new PR`
- **deny:** `git push --force`, `git reset --hard`, admin merge, committing secrets

### Network

| Field | Value |
|-------|-------|
| mode | `named_services_only` |
| allowed_services | `coderabbit.ai schema download` |

### Secrets

| Field | Value |
|-------|-------|
| access | `none` |
| redaction_required | `true` |

### Autonomous merge

`autonomous_merge:` `false` always. This plan confers no merge authority.

### Preserved contracts

- all other .coderabbit.yaml settings unchanged

## Side effects and idempotency

Required for every destructive / external-write TODO (PLAN-SCHEMA-005). One row per todo.

| todo_id | side_effects | idempotency | retry | compensation | irreversible |
|---------|--------------|-------------|-------|--------------|--------------|
| T1 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- .coderabbit.yaml` | `false` |
| T2 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- .coderabbit.yaml` | `false` |

## Architecture impact

| todo_id | bounded_context | layer | owning_contract | prohibited |
|---------|-----------------|-------|-----------------|------------|
| T1 | `repository root` | `assurance` | `all other .coderabbit.yaml settings unchanged` | `docker-compose.yml`, `.env.example`, `any plasticos_* addon file` |
| T2 | `repository root` | `assurance` | `all other .coderabbit.yaml settings unchanged` | `docker-compose.yml`, `.env.example`, `any plasticos_* addon file` |

## Rollback

`schema_ref:` `canonical.schema.rollback_contract.v1`
`instance_binding:` `rollback_contract_ref` → `rollback.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1`

| Field | Value |
|-------|-------|
| rollback_id | `rollback.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| source_execution_ref | `plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| supported | `true` |
| automatic_allowed | `false` |
| approval_required | `false` |
| trigger_conditions | C1 fails (V2 prints the expected reviewed/excluded verdict for every sample path) → stop; adjust the exclusion patterns before publishing |

### Strategies (typed — PLAN-SCHEMA-009)

| domain | mode | notes |
|--------|------|-------|
| code | `git_restore_scoped_paths` | revert the single commit |
| data | `none` | PLAN_DOCUMENT declares no data mutation |
| external_state | `none` | PLAN_DOCUMENT declares no external write |
| local_state | `git_restore_scoped_paths` | scoped to todo files |

### Irreversible operations

- none — no todo is marked `irreversible` (PLAN-SCHEMA-010)

### Rollback verification

- re-run `V1`
- re-run `V2`
- re-run `V3`
- re-run `python3 -c "import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']"`
- re-run `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"`
- re-run `curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c "import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))"`
- re-run `.pre-commit-config.yaml hooks through make pr (check-yaml, trailing-whitespace, end-of-file-fixer)`
- re-run `after make pr: read the CodeRabbit comment on the new PR`

## Complexity and uncertainty

| Field | Value |
|-------|-------|
| complexity | `low` — highest todo risk across 2 todo(s) |
| uncertainty | `low` — 0 unknown(s), 0 blocking |
| blast_radius | `low` — CodeRabbit review scope on cryptoxdog/IB-Odoo_19 only; no runtime, CI gate or Odoo code changes |
| architectural_boundaries_crossed | none |
| external_systems_touched | `CodeRabbit` |
| migration_required | `false` |
| unknown_dependency_count | `0` |

## Inventory and classification *(optional — activate if retire/migrate/replace)*

Not activated — PLAN_DOCUMENT declares no retire / migrate / replace inventory.

## Gated write pipeline *(optional — irreversible or external writes)*

Not activated — PLAN_DOCUMENT declares no irreversible or external write.

## Regeneration extinguishment *(optional — retirement/deprecation)*

Not activated — PLAN_DOCUMENT declares no retirement or deprecation.

## Execution DAG

`schema_ref:` `canonical.schema.dependency_topology.v1`
`instance_binding:` `dependency_topology_ref` → `dag.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1`
Must be acyclic before status may become `executable` (PLAN-SCHEMA-007).

| Field | Value |
|-------|-------|
| topology_id | `dag.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| topology_kind | `execution` |
| graph_type | `directed_acyclic_graph` |

### Nodes / edges

| id | task | owner | risk | effort | depends_on | outputs |
|----|------|-------|------|--------|------------|---------|
| T1 | Replace the reviews.path_filters list with exclusions only: **/.venv/**, **/.mypy_cache/**, **/.pytest_cache/**, **/.ruff_cache/**, **/__pycache__/**, **/*.pyc, **/node_modules/**, odoo-enterprise/**, **/*.zip, plasticos_partner_import/erp_extracted_data/bulk/**, plasticos_partner_import/erp_extracted_data/meta/**, plasticos_partner_import/erp_extracted_data/diagnostics/**, docs/**/*.csv, ERP.WksDetail.Test.csv, each with a leading !. Drop the four include lines, the three test exclusions and the blanket !*.csv. Keep a comment stating that a pattern without ! turns the list into an allowlist. | Cursor Build agent | `low` | S | `[]` | `.coderabbit.yaml` |
| T2 | Set reviews.auto_review.base_branches to [Production] (Staging is the default branch and is reviewed without being listed). | Cursor Build agent | `low` | S | `[]` | `.coderabbit.yaml` |

**Critical path:** T1 → T2

**Forbidden edges:** any edge not listed above; any todo writing outside `write_allow`.

### Milestones

| id | outcome | unlocks |
|----|---------|---------|
| M1 | CodeRabbit sees every reviewable file on Staging and Production PRs | summaries and walkthroughs on every PR now; line review once seats are assigned |

### Checkpoints

| id | after | evidence_required | no_go_action |
|----|-------|-------------------|--------------|
| C1 | T2 | V2 prints the expected reviewed/excluded verdict for every sample path | stop; adjust the exclusion patterns before publishing |

### Leverage

- **Ranked todos:** `T1`, `T2`
- **Shared causes:** include patterns misused as exceptions
- **Deletions / consolidations:** removes four include lines, three test exclusions and the blanket CSV exclusion

### Doc / root surface impact

| surface | action | todo_ids | reason |
|---------|--------|----------|--------|
| AGENTS.md / CLAUDE.md / README | `n_a` | — | reviewer-bot configuration only; no documented repository contract names CodeRabbit filters |

## Property evidence matrix

`schema_ref:` `canonical.schema.validation_evidence.v1`
`instance_binding:` `validation_evidence_refs` / `property_evidence_matrix_ref`
Exit-0 alone is insufficient when property needs structural/runtime proof (PLAN-SCHEMA-008).

| evidence_id | claim_id / SP | evidence_kind | method | command | expected_positive | status |
|-------------|---------------|---------------|--------|---------|-------------------|--------|
| E-V1 | SP-01, SP-04, SP-06 | `quality_gate_evidence` | command | `python3 -c "import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']"` | exits 0 | `not_run` |
| E-V2 | SP-01, SP-02, SP-03, SP-06 | `quality_gate_evidence` | command | `python3 -c "import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]"` | exits 0 (Python 3.13 PurePath.full_match approximates CodeRabbit glob matching; V5 is the live witness) | `not_run` |
| E-V3 | SP-01, SP-05, SP-06 | `quality_gate_evidence` | command | `curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c "import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))"` | exits 0; the same command on the pre-change file is the baseline (any pre-existing schema error is reported, not hidden) | `not_run` |
| E-V4 | regression gate (no SP) | `quality_gate_evidence` | command | `.pre-commit-config.yaml hooks through make pr (check-yaml, trailing-whitespace, end-of-file-fixer)` | all hooks pass | `not_run` |
| E-V5 | SP-01, SP-06 | `quality_gate_evidence` | command | `after make pr: read the CodeRabbit comment on the new PR` | no 'Review skipped due to path filters' for .coderabbit.yaml | `not_run` |

## Stress and disconfirm

### Disconfirming cases

- Does CodeRabbit match a bare pattern such as *.zip at every depth? (use **/ prefixes so depth does not matter)
- Do the projection .sql scripts live under the excluded bulk/meta/diagnostics folders? (no: they sit in erp_extracted_data/ itself)
- Is Staging reviewed without being listed in base_branches? (CodeRabbit reviews the default branch; Staging is the default)

### Assumption failure conditions

- If CodeRabbit glob matching differed from fnmatch-style ** semantics, V2 would not predict its verdict; V5 on the live PR is the final witness

### Blast radius notes

- CodeRabbit review scope on cryptoxdog/IB-Odoo_19 only; no runtime, CI gate or Odoo code changes

### Rollback constraints

- revert the single commit

### Risks

| risk | mitigation |
|------|------------|
| large data CSVs outside the listed folders get reviewed and spend review budget | remaining non-security CSVs are small Odoo seed data and business-rule tables that are legitimately reviewable |
| the organization has no free CodeRabbit seats, so only a summary is produced | reported to the operator; out of scope for configuration |
| CodeRabbit glob semantics may differ from Python full_match for edge patterns | every pattern uses an explicit **/ or a fixed repo-relative prefix; V5 reads the live PR verdict |

## Out of scope

- every other .coderabbit.yaml key (profile, tools, path_instructions, labeling)
- CodeRabbit seat assignment (billing, operator)
- Quantum-L9/coderabbit central config and the Quantum-L9/.github seeder renderer: separate repository, handed to its own session
- docker-compose.yml / .env.example L9_SIGNING_ALGORITHM: deferred by the operator
- Architecture redesign (unless plan_class + redesign_allowed)
- Force-push, hard-reset, admin-merge, secret exfil
- Weakening scanners / gates to obtain PASS
- Follow-on schema/platform evolution

## Follow-on milestone *(optional — keep separate; PLAN-SCHEMA-014)*

Not activated — PLAN_DOCUMENT declares no follow-on milestone; separate_plan_required `true` for any follow-on.

## Convergence

`schema_ref:` `canonical.schema.convergence_contract.v1`
`instance_binding:` `convergence_contract_ref` → `conv.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1`
Convergence requires all blocking evidence + gates (PLAN-SCHEMA-015).

| Field | Value |
|-------|-------|
| convergence_id | `conv.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| source_ref | `plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1` |
| current_state | `draft` |
| implementation_ready | `false` |

### Gates

- **executable_when:**
  - baseline locked + reverified
  - blocking capability probes pass
  - DAG acyclic
  - envelope + side-effect matrix complete for mutate todos
  - no blocking unknowns
- **complete_when:**
  - all blocking success-property evidence `passed`
  - rollback contract still valid / unused-or-verified
  - out_of_scope respected (diff hygiene)
- **blocking_conditions:**
  - `preflight_blocked`
  - envelope breach
  - baseline drift
  - failed blocking property

### Evidence

- **required_evidence_refs:** E-V1, E-V2, E-V3, E-V4, E-V5
- **observed_evidence_refs:** none
- **missing_evidence:** E-V1, E-V2, E-V3, E-V4, E-V5

### Blockers / unknowns

| kind | id | note | resolution |
|------|----|------|------------|
| `open_blocker` | stop_reason | plan validated; implementation not yet run | planning convergence `partial` |

### Next

| Field | Value |
|-------|-------|
| next_convergence_gate | `executable_when` |
| minimum_safe_next_action | When law holds and status=`executable`, press **Build**, stack if any open PR exists (`PR_STACK=auto`), then `make pr` and display the PR URL — do not free-form execute |
| execute_via | Cursor Build; stacked PR if any open PR exists; display PR URL |
| next_skill | Build then stacked make pr |
| broader_work_requires_separate_contract | `true` |

---

## Machine stub (optional YAML instance seed)

Projected from PLAN_DOCUMENT; keep in sync with the sections above.

```yaml
schema_id: "canonical.schema.plan_document.v1"
schema_version: "1.0.0"
metadata:
  plan_id: "plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1"
  name: "CodeRabbit reviews no IB-Odoo_19 file: path_filters allowlist and dead base branches"
  overview: "Make CodeRabbit review the files it is meant to review in cryptoxdog/IB-Odoo_19. .coderabbit.yaml reviews.path_filters carries four include patterns, which CodeRabbit treats as an allowlist; those four files are also excluded by !tests/**, so every PR file is skipped. Rewrite path_filters as exclusions only, keep the intended exclusions narrow, and point auto_review.base_branches at the real promotion branch Production."
  status: "draft"
  is_project: false
  owner: "igor_beylin"
architect_framing:
  planning_ssot: "PLAN_DOCUMENT"
  plan_class: "bounded_execution_contract"
  redesign_allowed: false
  follow_on_schema_evolution_separate: true
immutable_baseline:
  repository: "cryptoxdog/IB-Odoo_19"
  commit_sha: "64896c7fc976daa67d90ca51ff4570900ce7b0c7"
  dirty: "true"
  overlap_policy: "stop_if_dirty_overlaps_may_modify"
  verification_rule: "reverify_at_execution_start"
  on_drift: "stop_and_replan"
objective:
  mission: "Make CodeRabbit review the files it is meant to review in cryptoxdog/IB-Odoo_19. .coderabbit.yaml reviews.path_filters carries four include patterns, which CodeRabbit treats as an allowlist; those four files are also excluded by !tests/**, so every PR file is skipped. Rewrite path_filters as exclusions only, keep the intended exclusions narrow, and point auto_review.base_branches at the real promotion branch Production."
  success_properties:
    - id: "SP-01"
      property: ".coderabbit.yaml reviews.path_filters contains no pattern without a leading ! (V1)"
      evidence_type: "quality_gate"
      proof: ["V1", "V2", "V3", "V5"]
      blocking: true
    - id: "SP-02"
      property: "a Python file, a docs/*.md file, a tests/test_*.py file and a security/ir.model.access.csv are not matched by any exclusion, while plasticos_partner_import/erp_extracted_data/bulk/*.csv and odoo-enterprise/** are (V2)"
      evidence_type: "quality_gate"
      proof: ["V2"]
      blocking: true
    - id: "SP-03"
      property: "plasticos_partner_import/erp_extracted_data/*.sql projection scripts stay reviewable (V2)"
      evidence_type: "quality_gate"
      proof: ["V2"]
      blocking: true
    - id: "SP-04"
      property: "auto_review.base_branches is exactly [Production] (V1)"
      evidence_type: "quality_gate"
      proof: ["V1"]
      blocking: true
    - id: "SP-05"
      property: "the file parses as YAML and validates against https://coderabbit.ai/integrations/schema.v2.json (V3)"
      evidence_type: "quality_gate"
      proof: ["V3"]
      blocking: true
    - id: "SP-06"
      property: "on the published PR, CodeRabbit no longer reports 'Review skipped due to path filters' for .coderabbit.yaml (V5)"
      evidence_type: "quality_gate"
      proof: ["V1", "V2", "V3", "V5"]
      blocking: true
capability_preflight_ref: "preflight.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1"
execution_envelope:
  filesystem:
    write_allow: [".coderabbit.yaml"]
    write_deny: ["docker-compose.yml", ".env.example", "any plasticos_* addon file"]
  commands:
    allow: ["V1", "V2", "V3", "python3 -c \"import yaml;c=yaml.safe_load(open('.coderabbit.yaml'));pf=c['reviews']['path_filters'];assert pf and all(p.startswith('!') for p in pf),pf;assert c['reviews']['auto_review']['base_branches']==['Production']\"", "python3 -c \"import yaml,pathlib;pf=[x[1:] for x in yaml.safe_load(open('.coderabbit.yaml'))['reviews']['path_filters']];ex=lambda s:any(pathlib.PurePath(s).full_match(g) for g in pf);keep=['plasticos_gate/services/gate_config.py','docs/GATE_ODOO_WIRING.md','tests/test_odoo19_compat.py','plasticos_gate/security/ir.model.access.csv','plasticos_partner_import/erp_extracted_data/10_counterparty.sql'];drop=['plasticos_partner_import/erp_extracted_data/bulk/x.csv','odoo-enterprise/a/b.py','x/__pycache__/y.pyc','ERP.WksDetail.Test.csv'];assert not any(map(ex,keep)),[k for k in keep if ex(k)];assert all(map(ex,drop)),[k for k in drop if not ex(k)]\"", "curl -sSL https://coderabbit.ai/integrations/schema.v2.json -o $SCRATCH/cr_schema.json && $GOV/.venv/bin/python -c \"import json,yaml,jsonschema;jsonschema.validate(yaml.safe_load(open('.coderabbit.yaml')),json.load(open('$SCRATCH/cr_schema.json')))\"", ".pre-commit-config.yaml hooks through make pr (check-yaml, trailing-whitespace, end-of-file-fixer)", "after make pr: read the CodeRabbit comment on the new PR"]
  network:
    mode: "named_services_only"
  secrets:
    access: "none"
    redaction_required: true
  autonomous_merge: false
side_effects_and_idempotency:
  - todo_id: "T1"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T2"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
rollback_contract_ref: "rollback.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1"
dependency_topology_ref: "dag.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1"
validation_evidence_refs: ["E-V1", "E-V2", "E-V3", "E-V4", "E-V5"]
stress_and_disconfirm:
  disconfirming_cases: ["Does CodeRabbit match a bare pattern such as *.zip at every depth? (use **/ prefixes so depth does not matter)", "Do the projection .sql scripts live under the excluded bulk/meta/diagnostics folders? (no: they sit in erp_extracted_data/ itself)", "Is Staging reviewed without being listed in base_branches? (CodeRabbit reviews the default branch; Staging is the default)"]
  assumption_failure_conditions: ["If CodeRabbit glob matching differed from fnmatch-style ** semantics, V2 would not predict its verdict; V5 on the live PR is the final witness"]
out_of_scope: ["every other .coderabbit.yaml key (profile, tools, path_instructions, labeling)", "CodeRabbit seat assignment (billing, operator)", "Quantum-L9/coderabbit central config and the Quantum-L9/.github seeder renderer: separate repository, handed to its own session", "docker-compose.yml / .env.example L9_SIGNING_ALGORITHM: deferred by the operator"]
convergence_contract_ref: "conv.plan.simple.coderabbit_reviews_no_ib_odoo_19_file_path_filters_allowlist_and_dead_base_branches.v1"
execute_via:
  pipeline: cursor-build
  mention_program: "Cursor Build"
  command_ref: PR_STACK=auto make pr
  authority_order:
    - plan_document
    - cursor_build
todos:
  - id: "T1"
    content: "Replace the reviews.path_filters list with exclusions only: **/.venv/**, **/.mypy_cache/**, **/.pytest_cache/**, **/.ruff_cache/**, **/__pycache__/**, **/*.pyc, **/node_modules/**, odoo-enterprise/**, **/*.zip, plasticos_partner_import/erp_extracted_data/bulk/**, plasticos_partner_import/erp_extracted_data/meta/**, plasticos_partner_import/erp_extracted_data/diagnostics/**, docs/**/*.csv, ERP.WksDetail.Test.csv, each with a leading !. Drop the four include lines, the three test exclusions and the blanket !*.csv. Keep a comment stating that a pattern without ! turns the list into an allowlist."
    status: "pending"
  - id: "T2"
    content: "Set reviews.auto_review.base_branches to [Production] (Staging is the default branch and is reviewed without being listed)."
    status: "pending"
```

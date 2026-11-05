# PlasticOS Update Agent Docs Adapter

Load from **`l9-update-agent-docs`** when working in IB-Odoo_19 / PlasticOS repos.

## Additional When-to-Use Triggers

- A new `plasticos_*` module was added or removed
- `scripts/check_odoo_patterns.sh` checks were added/modified
- `ci/*.py` audit scripts were added/modified

## Step 1 — Inventory Modules

Count installable `plasticos_*` addons:

```bash
find . -maxdepth 3 -name "__manifest__.py" -path "*/plasticos_*/*" | wc -l
```

For each module, extract layer and maturity from `__manifest__.py`:

- **Layer**: from `depends` (see ARCHITECTURE.md layer rules)
- **Maturity**: Production / Beta / New / Dev-only (`installable: False`)

Cross-check with `ARCHITECTURE.md` Module Index.

## Step 4 — Audit check_odoo_patterns.sh

Read `scripts/check_odoo_patterns.sh` and extract every numbered check:

```bash
grep -n "Checking\|Check " scripts/check_odoo_patterns.sh
```

For each check: number, name, detection method, exclusions (with reasons from comments).

## Step 6 — PlasticOS False Positive Sources

| Source | What to search |
|--------|----------------|
| `scripts/check_odoo_patterns.sh` | Every `grep -v` with comment |
| `.github/workflows/*.yml` | `|| true`, `continue-on-error`, baselines |
| `pyproject.toml` | `exclude`, `per-file-ignores`, mypy overrides |
| `.pre-commit-config.yaml` | `exclude:`, `bash -c '... \|\| echo'` |
| `ci/*.py` | `EXCLUDED_DIRS`, `SKIP_DIRS`, whitelist sets |

## Step 7 — PlasticOS Section Updates

### AGENTS.md (7a extensions)

- **Odoo 19 patterns table** — all numbered checks from Step 4
- **Agent Skills** — L9 global table + project skills from `.claude/README.md`
- Verify **`l9-wire-skill-into-repo`** / `.claude/adapters/plasticos-repo-wiring.md` when skills changed

### ARCHITECTURE.md

- **Module Index** — count, add/remove rows, layers, maturity
- **CI/CD Architecture** — workflows, hooks, baselines

### INVARIANTS.md

- Map invariants to new/deleted CI checks
- **CI Enforcement Map** — pre-commit + workflow links

### CLAUDE.md

- **Always/Never** lists match CI-rejected patterns
- **Imports** — `@~/.cursor/skills/l9-structured-reasoning/SKILL.md` (not deprecated `.claude/skills/` paths)

## Validation (PlasticOS)

```bash
grep -c "plasticos_" ARCHITECTURE.md
grep -c "id:" .pre-commit-config.yaml
```

Module counts, hook counts, and CI job lists must match actual repo state.

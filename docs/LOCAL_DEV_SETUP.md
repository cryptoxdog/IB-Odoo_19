# Local Developer Setup — PlasticOS (IB-Odoo_19)

Run this checklist after **every fresh clone** on a new machine (MacBook, MacMini, etc.). Goal: identical editor + lint/test tooling without Docker on the laptop.

**SSOT map:** policy in `pyproject.toml`; Odoo import paths in `.vscode/settings.json`; this doc is the human onboarding runbook.

---

## Prerequisites

| Tool | Version / notes |
|------|-----------------|
| Python | 3.12 (`python3.12 --version`) |
| Git | clone this repo |
| Cursor (or VS Code) | Python extension (bundles Pylance) |
| direnv | optional but recommended (`brew install direnv`) |

This repo is an **Odoo addon suite**, not a pip/uv package. Do **not** use `uv sync` or `pip install -e .` here.

---

## 1. Clone repositories

Use the **same layout on every machine** so `${env:HOME}` paths in `.vscode/settings.json` work without edits.

```bash
# PlasticOS (this repo)
git clone git@github.com:cryptoxdog/IB-Odoo_19.git ~/dev/IB-Odoo_19
cd ~/dev/IB-Odoo_19
git checkout Staging   # or your feature branch

# Odoo 19 CE source — editor import resolution only (not required to run Odoo locally)
git clone --depth 1 -b 19.0 https://github.com/odoo/odoo.git ~/dev/odoo-19
```

If you keep the repo elsewhere, either:

- symlink `~/dev/odoo-19` to your real Odoo clone, or  
- override `python.analysis.extraPaths` in **user** Cursor settings (avoid committing machine-specific paths).

---

## 2. Build the dev virtualenv

```bash
cd ~/dev/IB-Odoo_19   # adjust if your clone path differs
make venv
```

Installs (pinned): **ruff 0.15.5**, **pytest**, **semgrep**, **pr-repair** (+ deps). Does **not** install Odoo into `.venv`.

Activate automatically with direnv:

```bash
# One-time shell hook (add to ~/.zshrc if not already):
# eval "$(direnv hook zsh)"

direnv allow
```

Or manual activation: `source .venv/bin/activate`

---

## 3. Cursor / Pylance

1. Open the repo folder in Cursor.
2. `Cmd+Shift+P` → **Python: Select Interpreter** → choose `.venv/bin/python`.
3. **Developer: Reload Window** (so Pylance picks up `pyproject.toml` + `.vscode/settings.json`).

Committed workspace settings (`.vscode/settings.json`) set:

- `${env:HOME}/dev/odoo-19` and `.../addons` as **extraPaths** for `from odoo import ...`
- Ruff as format-on-save

Verify: open any `plasticos_*/models/*.py` — `from odoo import api, fields, models` should not show “import could not be resolved” once `~/dev/odoo-19` exists.

---

## 4. Secrets and local env (not in git)

These files are **gitignored** — create them on each machine:

| File | Purpose |
|------|---------|
| `.env.local` | Odoo.sh SSH, API keys, machine-specific overrides |
| `~/.cursor/mcp.json` | MCP server keys (e.g. Context7) — user-level, not in repo |

Copy keys from your password manager; do not commit secrets or sync them via the repo.

Optional pattern: maintain `.env.local.template` in repo (keys only, empty values) and fill locally.

---

## 5. Validate tooling

```bash
make lint          # ruff check . — same scope as CI
make check         # lint + format check
make test          # pure-Python pytest tier (no Odoo runtime)
make pr-check      # full pre-push gate (when ready to push)
```

Pyright/Pylance is **editor-only** (`typeCheckingMode = basic` in `pyproject.toml`). It is not run in CI.

---

## 6. Odoo runtime (optional — not required for editor autocomplete)

Running Odoo locally is separate from editor setup:

| Environment | When to use |
|-------------|-------------|
| **Odoo.sh** | Staging/production deploys and ORM tests in cloud |
| **Docker** (`make up`, `make test-odoo`) | Full local ORM test runs if you enable Docker |
| **MacMini native** | Your production-style dev path if configured there |

Editor autocomplete works with only the **Odoo source clone** at `~/dev/odoo-19`; you do not need Docker on the laptop for Pylance.

---

## 7. Two-machine parity checklist

When switching MacBook ↔ MacMini, confirm:

- [ ] Same git branch checked out
- [ ] `~/dev/odoo-19` cloned (same path)
- [ ] `make venv` run in repo root
- [ ] Cursor interpreter = `.venv/bin/python`
- [ ] `.env.local` / MCP keys present locally (not from git)
- [ ] `make lint` passes

---

## Tooling file ownership (quick reference)

| Concern | File |
|---------|------|
| Ruff, pytest, mypy, Pyright policy | `pyproject.toml` |
| Odoo extraPaths, format-on-save | `.vscode/settings.json` |
| Dev pip deps | `requirements-dev.txt` |
| Odoo.sh runtime pip deps | `requirements.txt` |
| Agent/editor rules | `.cursor/rules/88-plasticos-odoo-python-tooling.mdc` |

**Retired:** `pyrightconfig.json` — do not reintroduce.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `from odoo import ...` unresolved | Clone `~/dev/odoo-19`; reload Cursor window |
| Ruff version mismatch | Run `make venv`; ensure `.venv/bin` is first on PATH (`direnv allow`) |
| `make lint` differs from CI | Both use `ruff check .` — no Makefile excludes; check you are on latest branch |
| Pyright too noisy in models | Expected for ORM; keep `basic` mode; see `88-plasticos-odoo-python-tooling.mdc` |

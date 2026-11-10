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

Installs the pinned Python developer toolchain from `requirements-dev.txt` (single pin source, versions aligned with CI): **ruff 0.16.0**, **pytest** (+ timeout/cov plugins), **semgrep**, **mypy**, **pr-repair** (+ deps). Does **not** install Odoo into `.venv`, and does **not** install system tools (`shellcheck` and `gitleaks`, also used by CI; `xmllint`, used by `make xml-check`) — install those separately (e.g. `brew install shellcheck gitleaks`); `make audit` fails closed if `shellcheck` is missing.

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
4. Install the recommended editor extensions (`.vscode/extensions.json` — carries over on every clone since it's git-tracked, but installation itself still requires one manual step per machine; VS Code/Cursor never auto-installs extensions from a cloned repo for security reasons):
   ```bash
   make install-extensions   # scripts/install_editor_extensions.sh — installs via cursor/code CLI
   ```
   Or manually: Extensions panel (`Cmd+Shift+X`) → **Recommended** section → Install.
   Requires the `cursor` CLI on `PATH` (Cmd+Shift+P → "Shell Command: Install 'cursor' command in PATH" if missing).

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

### Odoo.sh Staging SSH (env-first)

```bash
set -a && source .env.local && set +a
ssh "$ODOO_SH_STAGING_SSH"
```

- Set `ODOO_SH_STAGING_SSH=BUILD_ID@…-staging-BUILD_ID.dev.odoo.com` (no leading `ssh `).
- Build IDs rotate on rebuild — refresh from Odoo.sh Connect, then update `.env.local`.
- Rule snapshot: `.cursor/rules/98-odoo-sh-staging.mdc`. Skill: `plasticos-odoo-sh-deploy`.

| `~/.cursor/mcp.json` | MCP server keys (e.g. Context7) — user-level, not in repo |

Copy keys from your password manager; do not commit secrets or sync them via the repo.

Optional pattern: maintain `.env.local.template` in repo (keys only, empty values) and fill locally.

---

## 5. Validate tooling

```bash
make lint          # ruff check . — same scope as CI
make check         # lint + format check
make test          # pure-Python pytest tier (no Odoo runtime)
make pr-check      # full local pre-push gate (when ready to push) — GitHub CI remains the merge verdict
```

Pyright/Pylance is **editor-only** (`typeCheckingMode = basic` in `pyproject.toml`). It is not run in CI. Mypy is **advisory** (CI `run_advisory`, `make mypy-check`, `pre-commit run mypy --hook-stage manual`) and never blocks a commit, push, or merge.

### Git hooks

Install all three hook types once per clone. `make pr` refuses to publish without the pre-push hook.

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
```

The pre-push stage runs file hygiene (`check-xml`, `check-yaml`, end-of-file, trailing whitespace,
large files, merge markers), two contract tests, the full `gitleaks` scan, and `pr-validate`
(`make pr-check`). When `make pr` publishes, it has already run that gate for the exact commit, so the
hook skips the duplicate work. A direct `git push` runs the full gate. It must push the checked-out,
clean `HEAD`, and `make pr-check` calls GitHub for remote feedback, so `gh` must be authenticated.
Direct pushes are validated but are not publication: `make pr` remains the only way to open or update
a PR into `Staging`.

---

## 6. Odoo runtime (optional — not required for editor autocomplete)

Running Odoo locally is separate from editor setup:

| Environment | When to use |
|-------------|-------------|
| **Odoo.sh** | Staging/production deploys and ORM tests in cloud |
| **Docker** (`make up`, `make test-odoo`) | Full local ORM test runs if you enable Docker |
| **MacMini native** | Your production-style dev path if configured there |

Editor autocomplete works with only the **Odoo source clone** at `~/dev/odoo-19`; you do not need Docker on the laptop for Pylance.

### Cloud agent sessions

A Claude Code cloud session has Docker but no Odoo Enterprise source, so the install-smoke and the Odoo runtime tests in the `make pr-check` smoke stage cannot run there until the Enterprise code is reachable. `make runtime-bootstrap` (`scripts/runtime_bootstrap.sh`) binds an Enterprise checkout and admits the pinned fixture from `config/test_env_fixture.conf`. It runs no tests. The two runtime-test owners do not change.

**One-time operator setup.** The Enterprise source is licensed. Keep every copy private.

1. On GitHub, create a **private**, empty repository for it (for example `Quantum-L9/odoo-enterprise`). Naming it `odoo-enterprise` lets sessions find it with no variable.
2. Push the Enterprise 19.0 source (the `odoo-enterprise` folder this repo links to, or an unzipped Enterprise 19.0 archive) to that repository's `main` branch. The folder must have `web_enterprise/__manifest__.py` at its top level:

   ```bash
   cd "<the unzipped odoo-enterprise folder>"
   ls web_enterprise/__manifest__.py   # must exist here, not one level down
   git init -b main                    # skip if it is already a git repository
   git add -A && git commit -m "Odoo Enterprise 19.0"
   git remote add origin https://github.com/<owner>/odoo-enterprise.git
   git push -u origin HEAD:main
   ```

   GitHub refuses a single file over 100 MB; Enterprise source has none, but a stray archive or `.pyc` cache in the folder can. Remove those before `git add`.

3. Make the repository reachable from cloud sessions, either way:
   - add it to the cloud environment's repositories, so each session clones it next to this repository as `../odoo-enterprise`; or
   - set the environment variable `ODOO_ENTERPRISE_REPO=<owner>/odoo-enterprise`. The session must still be allowed to read that repository.

**In each session:** run `make runtime-bootstrap` once. The first run builds the fixture database, which takes several minutes. After that, `make pr` runs the install-smoke and the runtime tests in that session the same way it does on your machine.

| Variable | Meaning |
|----------|---------|
| `ODOO_ENTERPRISE_PATH` | An explicit Enterprise checkout directory; checked first |
| `ODOO_ENTERPRISE_REPO` | `owner/name` or git URL to clone when no checkout is found |
| `ODOO_ENTERPRISE_REF` | Branch to clone; default: the repository's default branch (for example `main`). The Odoo series is always checked as 19.0 |

`make runtime-bootstrap` refuses an `./odoo-enterprise` path that is not an Enterprise checkout, refuses another Odoo series, and never replaces a fixture that exists but is not admitted for the current inputs. That recovery stays `make test-env-rebuild`, an operator decision.

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

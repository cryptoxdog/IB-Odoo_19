---
name: plasticos-odoo-docker-testing
description: run PlasticOS Odoo Docker install-smoke and runtime tests before Odoo.sh. use when staging rebuilds fail, verifying module load order/versions, proving registry green locally, or after Gate-shell / security_base / partner_import changes.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, docker, install-smoke, testing, staging, gate]
owner: igor_beylin
status: active
disable-model-invocation: false
version: 1.0.0
updated: 2026-08-07
---

# PlasticOS Odoo Docker Testing

## Purpose

Prove the current codebase **loads and tests green in local Docker** before
touching Odoo.sh Staging. GitHub Actions cannot run `odoo-bin` install — Docker
`install-smoke` is the load gate.

This skill formalizes the sequence used to recover Staging after module-order /
Gate-shell / security_base regressions (2026-08).

## Core Contract

| Phase | Rule |
|-------|------|
| Env | Docker Desktop up; compose project `odoo19`; `odoo-enterprise` symlink present |
| Order SSOT | `config/odoo_module_order.yaml` + `scripts/get_odoo_module_order.py` must match Gate architecture |
| Load gate | `make install-smoke` must PASS before claiming Staging-ready |
| Runtime | `make test-odoo` / `make test-module m=…` only after install-smoke green |
| Remote | Odoo.sh Staging rebuild / SSH only after local Docker green |
| Architecture | Gate shells (`plasticos_matching`, `plasticos_enrichment`) install; deleted local engines never install |

## Authority Order

1. Explicit user request (smoke vs full e2e vs single module).
2. `config/odoo_module_order.yaml` + module `__manifest__.py` `installable` / `auto_install`.
3. `docs/runbooks/INSTALL_SMOKE.md` + `scripts/install_smoke.sh`.
4. `Makefile` targets: `install-smoke`, `test-odoo`, `test-module`, `pr-check`.
5. Gate law: Odoo → Gate → EIE/CEG → Gate → Odoo — no local matching/IE.
6. `plasticos-odoo-sh-deploy` for SSH after local green only.
7. This skill's references.
8. `Unknown` — stop if Docker daemon down or enterprise symlink missing when required.

## Compact Workflow

1. **Preflight** — [docker-env.md](references/docker-env.md): daemon, `db` healthy, `POSTGRES_PASSWORD`, enterprise symlink.
2. **Align order** — [module-order-ssot.md](references/module-order-ssot.md): Gate shells in order; excluded = deleted / False / Enterprise-only; bump versions that changed.
3. **Static ref check** — `python3 ci/check_xml_module_ref_deps.py` (also runs inside install-smoke).
4. **Install-smoke** — [install-smoke-protocol.md](references/install-smoke-protocol.md):
   - Fast path: `ODOO_ENTERPRISE_MODULES=none make install-smoke`
   - Parity path: `make install-smoke` (enterprise list from yaml)
   - Evidence: every listed module `state=installed` + `✅ install-smoke PASSED`
5. **Runtime tests** (optional / next) — [test-odoo-protocol.md](references/test-odoo-protocol.md).
6. **Staging** — [staging-before-odoo-sh.md](references/staging-before-odoo-sh.md): merge → Odoo.sh rebuild; SSH only if still red after local green.

## Resource Map

- [references/docker-env.md](references/docker-env.md) — containers, env vars, one-time setup.
- [references/module-order-ssot.md](references/module-order-ssot.md) — install order, Gate shells vs excluded, version bumps.
- [references/install-smoke-protocol.md](references/install-smoke-protocol.md) — smoke scopes, fatal filters, failure triage.
- [references/test-odoo-protocol.md](references/test-odoo-protocol.md) — `test-odoo` / `test-module` / pytest tiers.
- [references/staging-before-odoo-sh.md](references/staging-before-odoo-sh.md) — Docker-first promotion ladder.

## Validation

Do **not** claim Staging-ready unless:

- [ ] `docker info` succeeds
- [ ] `python3 ci/check_xml_module_ref_deps.py` passes
- [ ] `make install-smoke` prints `✅ install-smoke PASSED`
- [ ] Log shows `plasticos_matching`, `plasticos_enrichment`, `plasticos_security_base` installed when in scope
- [ ] Excluded deleted engines (`plasticos_buyer_match_engine`, `plasticos_inference_engine`) are **not** in the install list
- [ ] Manifest versions bumped for modules whose data/Python/XML changed

## Failure Handling

| Symptom | Action |
|---------|--------|
| Docker daemon down | `open -a Docker`; wait for `docker info` |
| `odoo-enterprise` missing | Symlink per docker-env.md; or `ODOO_ENTERPRISE_MODULES=none` for custom-only |
| `External ID not found` during `<delete>` | Fresh-DB noise if WARNING + Skipping deletion — not a registry fatal (see install-smoke filter) |
| `ParseError` / `Failed to load registry` | Real blocker — fix XML/depends; re-run smoke |
| Matching fails `plasticos_base.*` xmlid | Add `plasticos_base` to matching `depends` + bump version |
| security_base fails on load-dashboard rules | Rules live in security_base; logistics cannot own group-bound rules |
| partner_import graph ERROR in post_init | Known non-abort; smoke continues if registry loaded |
| Odoo.sh red, Docker green | Use `plasticos-odoo-sh-deploy` SSH on `update.log` — env parity issue |

## Daisy-chain

| Sibling | When |
|---------|------|
| `plasticos-odoo-sh-deploy` | After local green; Staging/Production still failing |
| `plasticos-new-odoo-module` / `plasticos-new-model-field` | After scaffold — run install-smoke before push |
| `plasticos-pr-review-kernel` | Reject PRs that change manifests/XML without smoke evidence when Staging is broken |

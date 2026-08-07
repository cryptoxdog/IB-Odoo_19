# Runbook: Local Odoo install-smoke (pre-GitHub load gate)

## Purpose

GitHub Actions cannot run `odoo-bin` module install. Dirty XML/depends/import
failures therefore ship unless a **local Docker install-smoke** runs first.

`make install-smoke` is the durable environment for:

- full enterprise mount (`odoo-enterprise` → Dropbox enterprise tree)
- `xmlsec` system + Python deps (unblocks `l10n_nl_reports` and peers)
- one-shot `-i <modules> --stop-after-init` with ERROR fail-closed
- static XML `ref(module.id)` vs `__manifest__ depends` check

## One-time setup

```bash
cd /path/to/IB-Odoo_19
ln -s "$HOME/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise" odoo-enterprise
# odoo-enterprise is gitignored — never commit the tree
```

## Run

```bash
make install-smoke
# custom-only (faster, no enterprise list):
ODOO_ENTERPRISE_MODULES=none make install-smoke
# ordered core list only (skip extra installable addons):
ODOO_INSTALL_SMOKE_SCOPE=ordered make install-smoke
```

Default scope installs `default_install_order` **plus** every other
`installable: True` `plasticos_*` addon not listed under `excluded_modules`.

## Wire into push

`make push` depends on `pr-check`, which now depends on `install-smoke`.
A module that does not load cannot be pushed via the Makefile path.

## Ownership note (security groups)

`plasticos_security_base.group_sales_rep` (and peers) are defined **once** in
`plasticos_security_base`. Load-dashboard `ir.rule` records that bind those
groups live in `plasticos_security_base/security/record_rules.xml` — not in
`plasticos_logistics` (logistics cannot depend on security_base without a cycle).


## Agent skill

Load **`plasticos-odoo-docker-testing`** (`skills/plasticos-odoo-docker-testing/`)
for the full Docker-first ladder (env → module-order SSOT → install-smoke →
test-odoo → Staging). This runbook is the short operator cheat sheet.

## Related

- `scripts/install_smoke.sh`
- `ci/check_xml_module_ref_deps.py`
- `scripts/rebuild-odoo-no-demo.sh` (full interactive rebuild)
- `.github/workflows/ci.yml` — Odoo runtime permanently disabled in GHA

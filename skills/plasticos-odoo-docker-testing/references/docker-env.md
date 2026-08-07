# Docker Environment Preflight

## Compose project

| Item | Value |
|------|-------|
| Project name | `odoo19` (`ODOO_COMPOSE_PROJECT`, default) |
| DB service | `db` (Postgres) |
| Smoke runner | `odoo-test` (built from repo `Dockerfile` — includes xmlsec) |
| Smoke DB | `odoo_install_smoke` (`ODOO_INSTALL_SMOKE_DB`) |
| Runtime test DB | `ODOO_TEST_DB` (Makefile `test-odoo`) |

## One-time setup

```bash
cd "$CURSOR_PROJECT_DIR"   # or repo root
# Enterprise addons (gitignored) — required for full parity smoke
ln -s "$HOME/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise" odoo-enterprise

# Password: prefer .env; compose default for local db is usually odoo
# Never commit secrets. install_smoke.sh can read POSTGRES_PASSWORD from
# compose config when unset.
cp .env.example .env   # optional; set POSTGRES_PASSWORD=
```

## Bring-up checklist

```bash
docker info >/dev/null          # daemon must be up
open -a Docker                  # if daemon down (macOS)
docker compose -p odoo19 up -d db
docker compose -p odoo19 exec -T db pg_isready -U odoo -d odoo
```

## Env knobs

| Variable | Purpose |
|----------|---------|
| `POSTGRES_PASSWORD` | Required for smoke; from `.env` or compose |
| `ODOO_ENTERPRISE_MODULES=none` | Skip enterprise `-i` list (faster custom-only) |
| `ODOO_INSTALL_SMOKE_SCOPE=all` | default — ordered + remaining installable (minus excluded) |
| `ODOO_INSTALL_SMOKE_SCOPE=ordered` | `default_install_order` only |
| `ODOO_REBUILD_MODULES` | Override module CSV list entirely |
| `ODOO_COMPOSE_PROJECT` | default `odoo19` |

## Image rebuild

`install_smoke.sh` runs `docker compose -p odoo19 build odoo-test` so xmlsec /
`requirements.txt` changes are present. First build after Docker restart can take
many minutes (base `odoo:19` layer extract). Do not kill mid-extract unless the
daemon died.

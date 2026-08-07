# Install-Smoke Protocol

## Command ladder

```bash
# 1) Static (also inside smoke)
python3 ci/check_xml_module_ref_deps.py

# 2) Fast custom-only (recommended first)
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-odoo}"
ODOO_ENTERPRISE_MODULES=none make install-smoke

# 3) Full Docker↔Odoo.sh enterprise parity (slower)
make install-smoke

# 4) Core ordered list only
ODOO_INSTALL_SMOKE_SCOPE=ordered make install-smoke
```

`make pr-check` and `make push` depend on `install-smoke` — unloadable modules
must not reach GitHub via the Makefile path.

## What smoke does

1. Resolve module CSV via `get_odoo_module_order.py`
2. `ci/check_xml_module_ref_deps.py`
3. Ensure Postgres up (`odoo19` project)
4. `docker compose build odoo-test`
5. Drop/create `odoo_install_smoke`
6. `odoo-test -i <modules> --without-demo=all --stop-after-init`
7. Scan log for **registry** fatals (not post_init application ERRORs)
8. Verify each custom module `ir_module_module.state = installed`
9. Prove `import xmlsec` inside the image

## Success evidence

```
✅ plasticos_matching
✅ plasticos_enrichment
✅ plasticos_security_base
…
✅ install-smoke PASSED — safe to push (modules load cleanly)
```

Capture the log path printed by the script (`/tmp/odoo-install-smoke-*.log`).

## Fatal vs non-fatal

| Pattern | Fatal? |
|---------|--------|
| `Failed to initialize database` | Yes |
| `ParseError` | Yes |
| `odoo.registry: Failed to load registry` | Yes |
| `Invalid field` | Yes |
| `External ID not found` on ERROR/CRITICAL registry path | Yes |
| `Skipping deletion for missing XML ID` + `_tag_delete` Traceback | **No** (fresh DB) |
| partner_import `GRAPH_VALIDATION_FAILURE` ERROR in post_init | **No** if module still loads |
| `User not found: …` during CSV import | No |

Prefer removing obsolete `<delete>` tags; use post-migrate SQL for upgrade
cleanup of retired menus/xmlids.

## Pipefail note

When wrapping smoke with `tee`, use `set -o pipefail` or check make's exit
explicitly — otherwise `tee` exit 0 masks smoke failure.

## Triage order on failure

1. Open the printed log; jump to first `ParseError` / `Failed to load registry`.
2. Identify module name in `Loading module plasticos_*`.
3. Fix depends / XML / migration; bump version.
4. Re-run with `ODOO_ENTERPRISE_MODULES=none` until green, then full smoke if needed.

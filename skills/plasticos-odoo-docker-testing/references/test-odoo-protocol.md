# Odoo Runtime + Pytest Tiers

## Tier map

| Tier | Command | Needs Odoo Docker? | Blocks `make push`? |
|------|---------|--------------------|---------------------|
| Pure pytest | `make test` / `pytest tests/` | No | Yes (`pr-check`) |
| Install-smoke | `make install-smoke` | Yes | Yes (`pr-check`) |
| Odoo native tests | `make test-odoo` | Yes (installed DB) | No (local / Odoo.sh) |
| Single module | `make test-module m=plasticos_X` | Yes | No |
| Odoo.sh suite | Staging/Production rebuild | Remote | External status only |

GHA **does not** run Odoo runtime install. Local Docker is the authority for
registry load.

## After install-smoke green

```bash
# Full native test enable on ODOO_TEST_DB (see Makefile / .env)
make test-odoo

# Scoped
make test-module m=plasticos_security_base
make test-module m=plasticos_matching
```

Use `TransactionCase` fixtures per `.cursor/rules/80-plasticos-testing-rules`
(and AGENTS.md testing section). Never `skipTest` for missing fixtures.

## Gate-shell test focus

- Matching/enrichment tests assert **Gate orchestration / degraded mode**, not
  local Neo4j Stage-1 scoring or `plasticos_inference_engine` imports.
- Contract: `tests/contracts/test_no_local_intelligence.py` +
  `ci/check_no_local_intelligence.py` (`make no-local-intelligence`).

## When to stop at smoke

If the user only needs "Odoo loads green" / Staging rebuild unblock, **install-smoke
PASS is sufficient** before merge. Escalate to `test-odoo` when changing
business logic under test tags or when Odoo.sh test suite is enabled on the branch.

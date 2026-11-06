# Odoo Runtime + Pytest Tiers

## Tier map

| Tier | Command | Needs Odoo Docker? | Blocks `make pr`? |
|------|---------|--------------------|---------------------|
| Pure pytest | `make test` / `pytest tests/` | No | Yes (`pr-check`) |
| Install-smoke | `make install-smoke` | Yes | Yes (`pr-check`) |
| Odoo runtime tests | `make runtime-test` (smoke stage of `pr-check`, or `l9-pr-integration-testing`) → `test-module` / `test-odoo` | Yes (fixture clone) | Yes (`pr-check`) when the branch touched a roster module with Odoo tests; skipped by `make pr-nosmoke` |
| Odoo.sh suite | Staging/Production rebuild | Remote | External status only |

GHA **does not** run Odoo runtime install. Local Docker is the authority for
registry load.

## Owners

Odoo runtime tests (`make test-module` / `make test-odoo`) run only in the `make pr-check` smoke stage or when `l9-pr-integration-testing` is invoked (`make runtime-test m=<modules>`). Do not run them ad hoc.

| Owner | When | Modules |
|-------|------|---------|
| `make pr-check` smoke stage (`scripts/pr_check_run.sh`) | after install-smoke, on every `make pr` / pre-push gate | `runtime=` from `scripts/pr_check_scope.py`: roster modules the branch touched that ship a `tests/` package; `all` when the whole gate is kept |
| `l9-pr-integration-testing` | only when the operator invokes it | `make runtime-test m=<modules>` on the host compose stack |

`make pr-nosmoke reason=...` and `PR_CHECK_SKIP_SMOKE=1` skip the runtime tests with smoke. A scope of `smoke=0` does not: a change to an addon's own tests still runs them.

## Fixture

Enterprise runtime tests clone the database named by `TEMPLATE` in
`config/test_env_fixture.conf` (`odoo_test_tpl_ee_c9e8a81f52f23680`).
`scripts/test_env.sh` refuses a different template. It does not rename another
template onto that name. A rebuild runs only when the database is absent and
`TEST_ENV_ALLOW_NEW_TEMPLATE` equals the fixture name. The value `1` is refused.
Do not set the variable for a source edit. `TEST_ENV_PARITY=community` is refused
unless `TEST_ENV_SAFETY_HARNESS=1`, which belongs to the safety suite.
`make test-odoo-local` is the no-Docker backend, not this fixture.
`make install-smoke` remains the load gate; it is not a second runtime-test template.

The fixture is used only for the inputs it was admitted for (Odoo image,
Postgres major, module roster, runtime configuration, Enterprise checkout).
A fixture admitted for other inputs, or one that no recorded inputs file proves,
is refused with the changed inputs named. It is not rebuilt. PlasticOS addon
source is not one of those inputs.

## Test runner

`make runtime-test` dispatches to `make test-odoo` (`all`) or `make test-module m=…`, which run inside `scripts/test_env.sh run`.
That treats a `--test-enable` run as its test runner:

| Step | Behaviour |
|------|-----------|
| Upgrade | `-u` every declared PlasticOS module on the clone (`scripts/get_odoo_module_order.py`); never `-u all` |
| Tests | `--test-tags` limits them to the roster, or to `m=` |
| Verdict | Odoo's `N failed, N error(s) of N tests when loading database '<db>'` line. A missing line, any failure or error, a non-zero exit, or **zero tests** fails |
| Receipt | `.l9/runtime/test-env/<db>.test-receipt.json` (tests, failed, errors, exit, scope, fixture, and the tested source: `source` addon digest, Git `head`, `dirty` when the worktree differs from that head). Addon source that changes during the run gets no receipt |

Any other `scripts/test_env.sh run` (`make import-erp-test`, a guarded
`make import-vanillasoft`, `shell`, `make runtime-gate-f1`) first upgrades the
roster on the clone, once per addon source digest (stamped `src=` on the clone).
That step reads no stdin. Every option that starts Odoo's tests (`--test*`, `-t`)
goes to the runner, and prefixed redirect options (`--db_h=`, `--datab`, `-cFILE`)
are refused.

Without `-u`, Odoo runs at_install and post_install tests of every loaded module,
core and Enterprise included, against the fixture's schema. That is why the
runner always upgrades the roster.

## Under l9-pr-integration-testing

```bash
# Only when the operator invoked l9-pr-integration-testing; the smoke stage passes the modules itself
make runtime-test m=plasticos_security_base,plasticos_matching
make runtime-test m=all   # whole roster (make test-odoo)
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
PASS is sufficient** before merge. The runtime tests for touched modules already run
in the same smoke stage; a wider run is an explicit `l9-pr-integration-testing` invocation.

<!-- L9_META
schema: 1
parent: plasticos-pr-integration
layer: reference
role: enterprise-smoke
version: 1.1.0
status: active
-->

# Enterprise fixture and full smoke

Run status, smoke, and runtime in one shell from the disposable worktree. `make install-smoke` and `make runtime-test` run one at a time. Keep each attached for at least 600000 ms and for longer than it runs. A wait of 0 backgrounds the shell and kills the command.

The compose project is the `name:` in `docker-compose.yml` (`odoo19`). Do not start a second project. The smoke database is `odoo_test_smoke_` plus this worktree's owner (`scripts/test_env.sh smoke-name`). Do not set `ODOO_INSTALL_SMOKE_DB` to another name. Do not copy `.env` into the worktree. Do not put a password into the command.

## Enterprise checkout

If `odoo-enterprise/web_enterprise/__manifest__.py` is missing in the worktree, set `ODOO_ENTERPRISE_PATH` to the realpath of the primary checkout's `odoo-enterprise` link, and export it for the rest of the shell. Do not clone Enterprise. Do not set `TEST_ENV_PARITY=community`.

## Admission

```bash
bash scripts/test_env.sh status
```

Continue only when parity is `ee` and the template named by `TEMPLATE=` in `config/test_env_fixture.conf` is printed as `ready`. The fingerprint in that output is the one smoke must keep.

When the template line says it is not admitted, stop. Quote the `input` lines. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE`. Do not run `make test-env-rebuild` unless the operator asks to recover the fixture. A roster change in `config/odoo_module_order.yaml` is testable only when this status already says `ready` for the merged tree.

## Full smoke

```bash
make install-smoke
```

The command clones the pinned template into this worktree's smoke database and upgrades the canonical Enterprise modules plus the PlasticOS roster from the merged source. It does not install from an empty database.

Pass is exit 0 and either `install-smoke PASSED` or `install-smoke evidence matches; not upgrading`. The second line is printed only after this worktree's receipt matches the live fingerprint, the addon source digest, the image, and the installed states. A receipt file that this command did not just accept is not a pass.

`install-smoke refused: lock busy` means this compose project is already held. Stop. Do not delete the lock file and do not start another smoke beside it.

Every module the command lists must be installed. Duplicate field-label warnings do not fail the gate by themselves. A non-zero exit does.

## Modules the diff changed

Read `git diff --name-only <staging-sha> HEAD`.

Keep a `plasticos_*` directory when that diff touches it, it contains a tests package, and `scripts/get_odoo_module_order.py` prints its name. Join those names with commas and no spaces:

```bash
make runtime-test m=<modules>
```

That upgrades the full declared PlasticOS roster on a fresh clone of the same template and runs Odoo tests for that list only. Pass is a receipt with `tests` greater than 0, `failed` 0, and `errors` 0.

If no directory qualifies, do not run `make runtime-test`. Runtime is not applicable. Smoke is still required. `m=all` is not full smoke.

If the diff adds a tests package whose module name is absent from the roster output, stop. Do not omit that module to make the command accept the list.

Do not invoke the recipes under `make runtime-test` directly.

## Pure Python

For each `test_*.py` file under the repository tests directory that the same diff touches, run it with the primary clone's `.venv/bin/python -m pytest` and the worktree as the working directory. Those results do not replace smoke. If the primary `.venv` interpreter is absent, record the tests as not run.

## One observed run

On 2026-11-10, open pull requests #447–#453 merged onto `Staging` `1ae3b06f` as `95e8333d`. Smoke on `odoo_test_smoke_wd491fe6860`, cloned from `odoo_test_tpl_ee_c9e8a81f52f23680` at fingerprint `0c209d2e…`, exited 0 with the Enterprise roster and 26 PlasticOS modules installed. That run does not certify a later head.

# Linda logistics open PRs | Docker pre-merge pack v1

Test the open Linda logistics pull requests on the admitted Enterprise fixture before any merge. This pack does not merge, rebase, or edit product code.

## Scope

| PR | Branch | Head | What it adds |
|---|---|---|---|
| #302 | `feat/linda-po-issuance` | `c3eaed74671092cc68b07cc54d793993d5952fb8` | PO issuance. Its new tests sit at `tests/test_linda_po_issuance.py` and are not imported by the addon. |
| #304 | `feat/linda-so-issuance` | `e6e463f5031d3b011986444a8ae59d3b4fdc630f` | SO issuance. Contains #302. PO and SO tests are registered on `plasticos_logistics`. |
| #305 | `feat/linda-wp02-native-inbound` | `cfffe4527948b9ba77c09bc18d1026252300b86b` | Inbound reply evidence. Contains #304. Adds `test_linda_inbound.py`. |

Base for all three is `Staging` `83f6ff9516e99fd8d2f864dab16078103e231e42`. #302 is an ancestor of #304, and #304 is an ancestor of #305. Open PRs #308 and #309 are not Linda logistics and are out of scope.

## Command

From a clean detached worktree at that PR head, with `ODOO_ENTERPRISE_PATH` pointed at the admitted Enterprise tree:

```bash
make test-module m=plasticos_logistics
```

That clones `odoo_test_tpl_ee_c9e8a81f52f23680`, upgrades the declared PlasticOS roster on the new owned clone, and runs only `plasticos_logistics` tests. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE` or `TEST_ENV_PARITY=community`. Do not drop another owner's clone.

Record image content identity before and after. A changed content hash stops the lane. An index-digest change with the same content hash is the runner's cached build. A template comment re-stamp stops the lane.

## How to read a result

A green receipt proves the tests the addon imports on that head. It does not prove a clean merge into `Staging`, and it does not prove tests that live under `tests/` or `tests/integration/` outside the addon. Those files are not loaded by `--test-tags /plasticos_logistics`.

Evidence goes in `docs/reports/evidence/linda-logistics-open-pr-docker-2026-10-24/`.

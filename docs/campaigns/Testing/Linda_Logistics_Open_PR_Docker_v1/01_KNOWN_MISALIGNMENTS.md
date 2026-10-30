# Known misalignments before the Docker run

These are visible from the GitHub heads and `git merge-tree` against `origin/Staging`. They do not depend on the test run.

## Merge

GitHub reports all three PRs `CONFLICTING` / `DIRTY`. The only content conflict is `plasticos_logistics/__manifest__.py`, and the only hunk is the version line:

| Side | Version |
|---|---|
| `Staging` | `19.0.1.10.4` |
| #302 | `19.0.1.11.0` |
| #304 | `19.0.1.13.0` |
| #305 | `19.0.1.14.0` |

`plasticos_automation` versions (`19.0.2.1.3` on #302, `19.0.2.1.4` on #304 and #305, against `Staging` `19.0.2.1.2`) auto-merge. No other file conflicts.

Action before merge: rebase each head onto current `Staging` and keep a logistics version that is unused on `Staging` and higher than `19.0.1.10.4`. Do not take `19.0.1.10.4` and drop the PR's data files. This pack does not perform that rebase.

## Test registration

On `Staging`, `plasticos_logistics/tests/__init__.py` imports `test_linda_freight_models` and `test_load_cardinality`.

On all three PR heads, `test_linda_freight_models.py` has moved to `tests/integration/test_linda_freight_models.py` and the addon no longer imports it. Nineteen freight tests that run in the `Staging` module suite will not run on these heads.

On #302, the new PO tests are only at `tests/test_linda_po_issuance.py`. The addon imports `test_load_cardinality` alone. A green #302 module run does not execute PO issuance.

On #304 and #305, PO and SO tests are imported by the addon. #305 also imports `test_linda_inbound`.

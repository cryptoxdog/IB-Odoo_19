# Actions before merge

Do these in order. No product edit was made by this run.

## 1. Resolve the version conflict on each PR

GitHub state is `CONFLICTING`. `git merge-tree` against `Staging` `83f6ff9516e99fd8d2f864dab16078103e231e42` conflicts only in `plasticos_logistics/__manifest__.py`:

- `Staging` is `19.0.1.10.4`
- #302 is `19.0.1.11.0`
- #304 is `19.0.1.13.0`
- #305 is `19.0.1.14.0`

Rebase onto current `Staging` and keep a logistics version above `19.0.1.10.4` that still loads the PR data files. Do not keep `19.0.1.10.4`. `plasticos_automation` auto-merges.

## 2. Do not treat the #302 receipt as PO coverage

`plasticos_logistics/tests/__init__.py` on #302 imports only `test_load_cardinality`. The new file `tests/test_linda_po_issuance.py` is outside the addon, so `--test-tags /plasticos_logistics` never loaded it. The receipt is 4 tests, all `TestLoadCardinality`.

Action: move that module onto `plasticos_logistics/tests/` and import it, which #304 already does. Until that is on the #302 head, #302 has no Enterprise proof of PO issuance.

## 3. Put the freight suite back on the addon import path

`Staging` imports `test_linda_freight_models`. All three heads moved that file to `tests/integration/test_linda_freight_models.py` and dropped the import. Those 19 tests did not run. A green logistics receipt does not replace them.

Action: import the freight tests from `plasticos_logistics/tests/__init__.py` again, or record an explicit decision that Odoo.sh should stop running them.

## 4. #305 does not run Linda AI

The inbound class includes `test_free_form_reply_stays_unresolved_without_native_ai`, and that test passed with the other 13 inbound tests. The PR title already says AI was not run. Do not describe #305 as a completed reply-classification feature.

## 5. Log noise that did not fail a test

- `FileNotFoundError` while mail reads filestore object `1fd21bb695b92439ea61c76efc32672373066a1f` on the #304 and #305 clones. The clone database references a file the clone filestore does not have. `test_attachment_is_the_native_po_report` still passed because it asserts `attachment.raw` at queue time. This is not a failed assertion. It is a clone-filestore gap, not proof that every attachment read succeeds.
- `ERROR: duplicate key value violates unique constraint "plasticos_transaction_unique_load_id"` is the expected rejection inside `test_a_second_transaction_cannot_take_the_same_load`. The test passed.
- Registry warning: `plasticos.freight.estimate.status` and `plasticos.freight.quote.selected` use `tracking`, which Odoo 19 does not accept. This prints on logistics load. It is not an issuance failure.

## 6. Leave the clones

`odoo_test_w40b4c4db7a`, `odoo_test_wdb953dba3a`, and `odoo_test_w4382288706` are this run's clones. The template was not re-stamped. Other owners' clones were not dropped.

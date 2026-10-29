# GMP-129 — close dashboard carrier dates and scale-ticket retry

**Task:** A multi-load sales-dashboard row has carrier names and dates. A failed scale-ticket check is retried on the next run. A losing ownership session under repeatable read rolls back completely. The seven baseline failures stay on their own branch.
**Base:** `origin/Staging`
**Branch:** `feat/domestic-multi-load-cardinality`
**Commit:** `65f365793713969c39727df860562461ff08e37c`

## What changed

`plasticos.sales.dashboard` still emits one row per transaction. When a deal has several loads, `load_id` and `load_state` stay empty, and revenue and margin stay the transaction amounts. `carrier_name` is the distinct carrier names, sorted and joined. Pickup is the earliest, delivery and delivered-at are the latest. A single load still shows that load.

`cron_check_scale_tickets` stores a failed load id in `plasticos_documents.scale_ticket_retry_ids`, capped at 300. The next run processes that list before the scan page. The scan cursor still advances.

Competing ownership is unchanged. The test states that `SerializationFailure` under repeatable read commits nothing. Isolation is still repeatable read, and the request does not retry.

`_lock_rows` uses one literal statement for `sale_order`, `plasticos_transaction`, or `plasticos_load`. The sale order is still locked before the insert.

Versions: `plasticos_commission` `19.0.1.4.5`, `plasticos_documents` `19.0.2.1.9`, `plasticos_logistics` `19.0.1.14.9`. Documents stays off `19.0.2.2.0`.

## Evidence

Enterprise tests on clone `odoo_test_wf7eb54ae39`, template `odoo_test_tpl_ee_c9e8a81f52f23680`, after `-u plasticos_commission,plasticos_documents,plasticos_logistics`:

`TestSalesDashboardLoadCardinality`, `TestScaleTicketCardinality`, `TestLoadCardinality` — 31 tests, 0 failed, 0 errors.

Ruff `0.16.0` check and format passed on the nine edited files. `pre-commit run --config .pre-commit-config.yaml --files` those files passed.

## Left unchanged

The seven Enterprise failures proven on `origin/Staging` `677d734fd88615d673501d91de88734b7150ff50` are not edited here: offer acceptance, claim recovery, and the three ACL tests. No isolation change, no retry inside the request, and no second dashboard row.

# Cron Hardening Report

## Summary
Repository-wide cron hardening applied for determinism, batching, idempotency, concurrency locks, and explicit cron user assignment.

## Changes by cron
- `cron_trucker_followup` (`plasticos_automation/models/stock_picking_automation.py`, `plasticos_automation/data/cron_trucker_followup.xml`): advisory lock, ordered/limited selection, 24h cooldown via `x_trucker_notified_on`, explicit `user_id`.
- `cron_supplier_followup` (`plasticos_automation/models/purchase_order_automation.py`, `plasticos_automation/data/cron_supplier_followup.xml`): advisory lock, ordered/limited selection, 24h cooldown via `x_last_followup_on`, explicit `user_id`.
- `cron_invoice_reminder` (`plasticos_automation/models/invoice_reminder.py`, XML): advisory lock, ordered/limited selection, same-day idempotency via `x_last_reminder_date`, explicit `user_id`.
- `cron_contract_renewal_alert` (`plasticos_automation/models/contract_renewal.py`, XML): advisory lock, ordered/limited selection, daily de-dupe via automation log existence check, explicit `user_id`.
- `cron_stock_reorder_alert` (`plasticos_automation/models/stock_reorder_alert.py`, XML): advisory lock, ordered/limited scan, daily de-dupe via automation log existence check, explicit `user_id`.
- `cron_sale_approval_flag` (`plasticos_automation/models/sale_approval.py`, XML): advisory lock, ordered/limited selection, explicit `user_id`.
- `cron_load_sla_check` (`plasticos_automation/models/load_automation.py`, XML): advisory lock, ordered/limited selection, explicit `user_id`.
- `cron_check_missing_docs` (`plasticos_documents/models/transaction_docs.py`, documents+transaction XML): advisory lock, ordered/limited selection, reminder/activity de-dupe guards, explicit `user_id`.
- `_cron_check_sla` (`plasticos_claims/models/claim.py`, XML): advisory lock, ordered/limited selection, activity de-dupe.
- `cron_geo_backfill` (`plasticos_geolocalize/models/res_partner_geo.py`, XML): advisory lock, ordered limited batch, explicit `user_id`.
- `action_cron_enrich_pending` + `action_cron_inference_only` (`plasticos_enrichment/models/enrichment_run.py`, XML): advisory locks, deterministic ordering, bounded batches, explicit `user_id`.
- `cron_expire_offers` (`plasticos_offer/models/offer.py`, XML): advisory lock, ordered/limited batch, explicit `user_id`.
- `run_monthly_audit` (`plasticos_transaction/models/audit_cron.py`, XML): advisory lock, ordered/limited query, explicit `user_id`.
- `_cron_cleanup_missing_filestore_orphans` (`plasticos_base/models/ir_attachment.py`, XML): advisory lock, ordered/limited candidates, explicit `user_id`.
- `_cron_expire_temporary_exclusions` (`plasticos_buyer_match_engine/models/match_exclusion.py`, XML): advisory lock, ordered/limited query, explicit `user_id`.
- `cron_followup` (`plasticos_logistics/data/cron.xml`): removed no-op code path by switching to callable method execution path and explicit `user_id`.
- All `ir.cron` XML records in repository scope: explicit `user_id` set.

## Remaining risks / business decisions
- Dedicated service user `system_cron` (external id `plasticos_base.user_system_cron`) is now used by all cron records.
- Some daily de-duplication relies on `plasticos.automation.log`; if disabled or removed, duplicate suppression for selected crons will degrade.
- Advisory locks are per-database session and assume Postgres backend (standard for Odoo).

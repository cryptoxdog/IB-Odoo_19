---
auto_generated: false
authority: derived-index
component_id: plasticos_automation
component_name: PlasticOS Automation Layer
module_version: 19.0.2.1.11
layer: 3
installable: true
auto_install: true
application: true
depends:
  - plasticos_base
  - base
  - base_automation
  - mail
  - product
  - sale_management
  - sale_stock
  - account
  - stock
  - purchase
  - plasticos_logistics
  - plasticos_transaction
  - plasticos_claims
models_owned:
  - plasticos.automation.config
  - plasticos.automation.log
  - plasticos.penalty.rule
  - plasticos.invoice.adjustment
models_extended:
  - account.move
  - res.partner
  - plasticos.load
  - purchase.order
  - sale.order
  - stock.picking
  - product.product
crons:
  - cron_sale_approval_flag
  - cron_invoice_reminder
  - cron_contract_renewal_alert
  - cron_stock_reorder_alert
  - cron_supplier_followup
  - cron_trucker_followup
  - cron_load_sla_check
---

# PlasticOS Automation Layer

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Deterministic workflow automation across sales, purchasing, stock, invoicing, and loads: approval flags, overdue and renewal reminders, supplier and trucker follow-ups, load SLA checks, and invoice penalties. It decides nothing by inference; every rule is a fixed condition in XML or Python.

## How it works

- **Configuration.** `plasticos.automation.config` holds thresholds such as `sale_approval_threshold`, `invoice_overdue_days`, and `contract_alert_days_before`. Defaults load from `data/automation_config_data.xml` and `data/config_parameters.xml`.
- **Record-change rules.** `data/workflow_automations.xml` defines `base.automation` rules (all `on_write`) and the server actions they run:
  - `rule_trigger_po_confirmation` and `rule_trigger_do_creation` on `purchase.order`;
  - `rule_trigger_so_notification` and `rule_request_dock_appointment` on `sale.order`;
  - `rule_tx_delivered_on_do_done` on `stock.picking`;
  - `rule_qc_claim_notification` on `plasticos.claim`;
  - `rule_trigger_penalty_calculation` on `account.move`;
  - `rule_trigger_carrier_dispatch` on `stock.picking` is present with `active` false, and its server action is named "Retired".
- **Scheduled checks.** Seven crons, one per data file, call methods on the extended models (sale approval, invoice reminder, contract renewal, stock reorder, supplier follow-up, trucker follow-up, load SLA).
- **Penalties.** `plasticos.penalty.rule` defines penalty terms. `account.move.calculate_penalties()` in `models/account_move_penalty.py` evaluates them from weight variance and days late and writes `penalty_amount`, `penalty_reason`, and `penalty_rule_id` on the invoice. `plasticos.invoice.adjustment` holds separate adjustment lines on the invoice (`adjustment_line_ids`), applied with `action_apply_adjustment`.
- **Audit.** `plasticos.automation.log` records what an automation did.
- **Install hook.** `post_init_hook` in `hooks.py` adds this module's automation groups to `base.group_system` and grants every group defined by this module to the user of each cron it owns.

Email templates in `data/email_templates.xml` load before `workflow_automations.xml` because the server actions reference them.

## Models

| Model                          | Kind     | File                                             |
| ------------------------------ | -------- | ------------------------------------------------ |
| `plasticos.automation.config`  | owned    | `models/automation_config.py`                    |
| `plasticos.automation.log`     | owned    | `models/automation_log.py`                       |
| `plasticos.penalty.rule`       | owned    | `models/penalty_rule.py`                         |
| `plasticos.invoice.adjustment` | owned    | `models/account_move_penalty.py`                 |
| `account.move`                 | extended | `account_move_penalty.py`, `invoice_reminder.py` |
| `res.partner`                  | extended | `models/contract_renewal.py`                     |
| `plasticos.load`               | extended | `models/load_automation.py`                      |
| `purchase.order`               | extended | `models/purchase_order_automation.py`            |
| `sale.order`                   | extended | `sale_approval.py`, `sale_order_automation.py`   |
| `stock.picking`                | extended | `models/stock_picking_automation.py`             |
| `product.product`              | extended | `models/stock_reorder_alert.py`                  |

## Runtime

- All seven crons ship with `active` false. An operator enables each one.
- Seven `base.automation` rules ship active; the carrier-dispatch rule ships inactive.
- `auto_install` and `application` are true.

## Boundaries

- No Gate call and no matching or enrichment logic.
- It does not own claims, loads, or transactions. It reacts to their state.
- Carrier dispatch on delivery-order readiness is retired here.

## Read next

- [`data/workflow_automations.xml`](data/workflow_automations.xml)
- [`hooks.py`](hooks.py)
- [`../AGENTS.md`](../AGENTS.md)

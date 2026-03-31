# plasticos_commission

**Version:** 19.0.1.2.0
**Category:** PlasticOS / Finance
**Depends:** `plasticos_base`, `plasticos_transaction`, `plasticos_security_base`

---

## Purpose

Calculates, tracks, and pays broker commissions on closed transactions. The module provides a rule engine (`commission_service.py`), a payout workflow model (`plasticos.commission.payout`), and a read-only SQL VIEW dashboard (`plasticos.sales.dashboard`) for broker pipeline visibility.

---

## Models

### `plasticos.commission`

One commission record per closed transaction.

| Field | Type | Notes |
|---|---|---|
| `transaction_id` | `Many2one(plasticos.transaction)` | Parent |
| `broker_id` | `Many2one(res.users)` | Assigned broker |
| `commission_locked_amount` | `Float` | Final amount — locked when payout is confirmed |
| `override_pct` | `Float` | Manual override rate (takes priority over rule engine) |
| `commission_rule_id` | `Many2one(plasticos.commission.rule)` | Applied rule |
| `state` | `Selection` | `draft / confirmed / paid` |
| `payout_id` | `Many2one(plasticos.commission.payout)` | Batch payout this commission belongs to |

---

### `plasticos.commission.rule`

Rate rules evaluated in priority order against transaction attributes (polymer, volume, customer tier, etc.).

| Field | Type | Notes |
|---|---|---|
| `name` | `Char` | |
| `priority` | `Integer` | Lower = evaluated first |
| `polymer_ids` | `Many2many(plasticos.polymer)` | If set, rule applies only to these polymers |
| `min_volume_lbs` | `Float` | Volume floor for rule eligibility |
| `rate_pct` | `Float` | Commission rate |
| `is_default` | `Boolean` | Fallback if no other rule matches |

---

### `plasticos.commission.payout`

**One payout record per broker per period.** Aggregates `commission_locked_amount` from confirmed commissions.

| Field | Type | Notes |
|---|---|---|
| `name` | `Char` | Sequence: `PAY-YYYY-NNNN` |
| `broker_id` | `Many2one(res.users)` | |
| `period_start` / `period_end` | `Date` | |
| `total_amount` | `Float` | Computed sum of linked commission amounts |
| `state` | `Selection` | `draft / confirmed / paid` |
| `payment_date` | `Date` | Required to move to `paid` |
| `payment_reference` | `Char` | Required to move to `paid` |
| `commission_ids` | `One2many(plasticos.commission)` | Linked commissions |

**Workflow:** `Draft → Confirmed` (accounting locks the list, no more commissions can join) → `Paid` (requires `payment_date` + `payment_reference`). Full chatter trail.

---

### `plasticos.sales.dashboard`

A `_auto=False` **SQL VIEW** model — read-only, computed at the DB level. Reps see one row per active deal.

Columns: financials, weight source badge, load state, four doc traffic lights (BOL / Scale Ticket / Invoice / CO), commission pay status.

Five drill-through buttons:
- Track Load
- View Scale Ticket
- View BOL
- View Payout Details
- All Documents

**Security:** `group_sales_rep` users see only their own deals (`user_id = uid` record rule). Managers and accounting see all.

---

## Commission Service: `commission_service.py`

Priority-chain calculation engine. Replaces the original stub that always returned `0.0`.

**Resolution chain:**

1. `commission_locked_amount` — if already locked (confirmed payout), return as-is
2. `override_pct` — if manually overridden, apply to `transaction.gross_margin`
3. Rule engine — iterate rules by `priority` ASC, first match wins
4. ICP default rate — `ir.config_parameter` key `plasticos.commission.default_rate_pct`
5. `0.0` — fallback, logged at `WARNING` level

Every resolution path logged at `DEBUG`. `WARNING` fired if fallback to 0.0.

---

## Security

- `ir.model.access.csv` — ACL entries for `plasticos.commission`, `plasticos.commission.rule`, `plasticos.commission.payout`, `plasticos.sales.dashboard`
- `security/record_rules_dashboard.xml` — `group_sales_rep` → `user_id = uid` on dashboard and payout models

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_commission --stop-after-init
```

**Requires `--update`** for:
- New stored fields on `plasticos.commission`
- SQL VIEW creation (first install)
- ACL changes

**Before running `--update`:** verify these fields exist on `plasticos.transaction` — the SQL VIEW query will fail at `init()` if any are missing:
- `broker_id`, `gross_margin`, `weight_lbs`, `load_id`, `freight_cost`, `sale_price`, `buy_price`

---

## Integration Points

| Module | Direction | Notes |
|---|---|---|
| `plasticos_transaction` | Inbound | Commission triggered when `transaction.state = closed` |
| `plasticos_security_base` | Groups | `group_sales_rep`, `group_accounting`, `group_manager` |

---

## Pending

| Item | Priority |
|---|---|
| Commission auto-trigger on `transaction.state = closed` | **High** — `commission_service.calculate()` not yet called from transaction write |
| `action_generate_for_rep()` cron or wizard | Medium — payout batch generation |

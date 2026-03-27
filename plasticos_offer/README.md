# plasticos_offer

**Version:** 19.0.3.1.0
**Category:** PlasticOS / Core Pipeline
**Depends:** `plasticos_base`, `plasticos_intake`, `plasticos_material_profile`, `plasticos_security_base`

---

## Purpose

`plasticos_offer` manages the offer records sent to buyers after intake matching. An offer represents a specific broker proposal: "we have X lbs of Y polymer from Z supplier, at P price per lb — are you interested?"

Offers are created automatically by `plasticos_intake.action_send_offers()` and drive the intake status machine from `matched` → `offer_sent`.

---

## Model: `plasticos.offer`

~16KB model with a full state machine.

### States

| Value | Label | Transition |
|---|---|---|
| `draft` | Draft | Default on create |
| `sent` | Sent | Auto-set when offer is created via `action_send_offers()` |
| `accepted` | Accepted | Buyer confirms interest |
| `declined` | Declined | Buyer passes |
| `expired` | Expired | Cron — system-set terminal state |
| `cancelled` | Cancelled | Manual |

### Key Fields

| Field | Type | Notes |
|---|---|---|
| `intake_id` | `Many2one(plasticos.intake)` | Parent intake |
| `buyer_partner_id` | `Many2one(res.partner)` | Buyer the offer was sent to |
| `match_line_id` | `Many2one(plasticos.intake.match)` | Source match line (carries `match_score`, `facility_profile_id`) |
| `offered_price` | `Float` | Seeded from `match_line.typical_price`; broker can override |
| `quantity` | `Float` | In lbs — from `intake.quantity_per_load_lbs` |
| `expiry_date` | `Date` | Set on creation from `ir.config_parameter` `plasticos.offer.expiry_days` |
| `transaction_id` | `Many2one(plasticos.transaction)` | Populated when offer is accepted and transaction created |
| `broker_id` | `Many2one(res.users)` | Assigned broker |

### Key Methods

| Method | Description |
|---|---|
| `action_accept()` | Advances to `accepted`; posts chatter notification to broker; sets `intake` to `won` if all offers resolved |
| `action_decline()` | Advances to `declined`; posts chatter |
| `action_create_transaction()` | Creates `plasticos.transaction` from accepted offer; links back via `transaction_id` |

---

## Crons

| Cron | Action | Schedule |
|---|---|---|
| PlasticOS Offer Expiry | Sets `state = expired` on offers past `expiry_date` | Daily |

Config param: `plasticos.offer.expiry_days` (default: 14)

---

## Views

| File | Description |
|---|---|
| `offer_views.xml` | Form, list, search, kanban grouped by `state` |

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_offer --stop-after-init
```

---

## Integration Points

| Module | Direction | Notes |
|---|---|---|
| `plasticos_intake` | Inbound | `action_send_offers()` calls `plasticos.offer.create()` |
| `plasticos_transaction` | Outbound | `action_create_transaction()` creates a transaction on acceptance |
| `plasticos_commission` | Downstream | Commission calculated when linked transaction is won |

---

## Pending

| Item | Priority |
|---|---|
| Offer accept → chatter notification to broker (activity + message) | High |
| Offer expiry cron XML | Medium |
| "View Offers" smart button on intake form (`offer_count`) | Medium |


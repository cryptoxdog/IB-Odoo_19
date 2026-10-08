# plasticos_transaction

PlasticOS transaction spine for Odoo 19.

## Purpose

`plasticos.transaction` is the operational deal record connecting supplier, buyer, Odoo sales/purchase documents, logistics, accounting, commissions, claims, and historical ERP line evidence.

The model already relates transactions to native Odoo commercial documents:

- `sale_order_id` → `sale.order`
- `purchase_order_ids` → `purchase.order`

Those relations are the preferred ownership path for native Odoo business semantics. Do not duplicate a native document concept onto the transaction merely because a legacy source exposes a similarly named field.

## Historical ERP import

The historical ERP import does not create `plasticos.transaction` or `plasticos.transaction.line` records. Commercial documents are `sale.order`, `purchase.order`, and `account.move`. A full `make import-erp` run is refused before any write.

The old `transaction_import_service.py`, `run_transaction_import.py`, and transaction CSV wizard remain legacy code. They are not the production historical import path and must not be extended.

## Historical trade date

`GPLedger.TradeDt` has now been semantically resolved:

> It is the date the purchase order was issued and, under current PlasticOS rules, the date the transaction was approved.

Odoo 19 already owns that concept on `purchase.order.date_approve` (`Confirmation Date`). Therefore:

- do **not** add `plasticos.transaction.transaction_date`;
- do **not** overload pickup/delivery dates;
- do **not** use `purchase.order.date_order` as the chosen target, because Odoo uses it as the RFQ/order-deadline date;
- persist `TradeDt` to `purchase.order.date_approve` when the historical PO realization slice creates or resolves the corresponding PO.

Until historical PO realization is implemented, the reconstructed `TradeDt` remains source evidence and is not persisted on `plasticos.transaction`.

## Native document integration

`plasticos.transaction` already links to Odoo purchase orders through `purchase_order_ids`. `purchase_inherit.py` links confirmed/approved POs into the transaction spine and locates the transaction from either the SO origin or the existing M2M relation.

This existing relation is why historical PO semantics should be realized on native `purchase.order` fields rather than copied onto a new transaction field.

## Current production-readiness proof

Static and pure-Python tests cover source mapping, deterministic partner identities, and replay contracts. The real-runtime ERP gate proves the partner import, replay, changed-record handling, and that a full import writes no transaction or line marker.

Direct-SQL readiness additionally requires the restored SQL Server source to feed the same pipeline on a disposable Odoo database, followed by an identical replay with zero creates, zero update churn, and no duplicate identities.

## Module reference

Retained from the previous README; unrelated to the ERP source correction above. The former "Import Wizard" section is removed: the CSV transaction wizard is legacy and is not the historical import path (see above).

### Model: `plasticos.transaction`

#### States

| Value | Label | Notes |
|---|---|---|
| `draft` | Draft | Default |
| `active` | Active | Deal in progress |
| `in_transit` | In Transit | Load picked up |
| `delivered` | Delivered | Load confirmed delivered |
| `invoiced` | Invoiced | Invoice raised |
| `closed` | Closed | Fully settled |
| `cancelled` | Cancelled | |
| `dispute` | Dispute | Claims triggered |

**Statusbar visible:** `draft, active, closed` (current — see Pending section for full-state expansion).

#### Key Fields

| Field | Type | Notes |
|---|---|---|
| `offer_id` | `Many2one(plasticos.offer)` | Source offer |
| `intake_id` | `Many2one(plasticos.intake)` | Source intake (via offer) |
| `supplier_id` | `Many2one(res.partner)` | |
| `buyer_id` | `Many2one(res.partner)` | |
| `supplier_profile_id` | `Many2one(plasticos.facility.profile)` | **Source of truth** for dual-supplier resolution |
| `material_profile_id` | `Many2one(plasticos.material.profile)` | |
| `load_id` | `Many2one(plasticos.load)` | Linked logistics load |
| `freight_bill_id` | `Many2one(account.move)` | Freight invoice — currently **manual link** |
| `sale_price` | `Float` | What the buyer pays |
| `buy_price` | `Float` | What the supplier is paid |
| `freight_cost` | `Float` | |
| `gross_margin` | `Float` | **Computed:** `sale_price - buy_price - freight_cost` |
| `amount_total` | `Float` | **Computed** — `@api.depends` must include `state` for accrual-basis accuracy |
| `weight_lbs` | `Float` | Actual shipped weight |
| `commission_id` | `Many2one(plasticos.commission)` | Populated when commission is calculated |
| `broker_id` | `Many2one(res.users)` | |
| `line_ids` | `One2many(plasticos.transaction.line)` | |
| `claim_ids` | `One2many(plasticos.claim)` | Via bridge in `plasticos_claims` |
| `document_ids` | `One2many(plasticos.document)` | Compliance doc attachments |

#### `amount_total` — Important

`amount_total` uses accrual-basis logic. **`@api.depends` must include `state`** — without it, the gross margin KPI banners in `transaction_ux.xml` can display stale values when a deal is cancelled or reverted to draft.

### Smart Buttons

| Button | Method | Source |
|---|---|---|
| Claims | `action_view_claims()` | **Defined in `plasticos_claims` bridge** — do NOT redefine here |
| Lines | `action_view_lines()` | Defined in `transaction.py` — added in GMP-001 |
| Load | `action_view_load()` | Defined in `transaction.py` |
| Commission | `action_view_commission()` | Defined in `transaction.py` |

> **Critical:** `action_view_claims()` is injected by `plasticos_claims` via `_inherit = 'plasticos.transaction'`. Adding a duplicate in `transaction.py` would shadow the bridge method. Never redefine it here.

### Views

| File | Description |
|---|---|
| `transaction_views.xml` | Primary form (tabs: General, Financials, Logistics, Documents, Commission), list, search |
| `transaction_ux.xml` | KPI banner overlays, gross margin highlights |

### Crons

| Cron | Action | Schedule |
|---|---|---|
| PlasticOS Sale Approval Flag | Flags transactions needing approval | Daily |
| PlasticOS Midnight Time-Based Field Recompute | Recomputes time-sensitive computed fields | Nightly 00:05 |

### Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_transaction --stop-after-init
```

**No `--update` needed** for method additions (no new stored fields). Required for new fields, ACL changes.

### Integration Points

| Module | Direction | Notes |
|---|---|---|
| `plasticos_offer` | Inbound | Created from `offer.action_create_transaction()` |
| `plasticos_logistics` | Bidirectional | `load_id` links to shipment; load state drives transaction state |
| `plasticos_accounting` | Outbound | `freight_bill_id` links to `account.move` — currently manual |
| `plasticos_commission` | Outbound | Commission calculated on `state = closed` |
| `plasticos_claims` | Bridge | Claims bridge injects `action_view_claims()` and `claim_ids` |

### Known Gaps / Pending

| Item | Priority | Notes |
|---|---|---|
| `amount_total @api.depends` missing `state` | High | KPI banners show stale values on cancel/revert |
| `supplier_profile_id` as source of truth | High | Currently informational; downstream views still use `supplier_id` directly |
| Freight Bill Auto-Link | Low | Complex heuristic (weight ±5%, date ±7 days, same carrier) — manual for launch |
| Full statusbar (all 8 states) | Medium | Currently only shows `draft, active, closed` |
| Commission auto-trigger on `state = closed` | High | `commission_service.calculate()` not yet called from transaction write |

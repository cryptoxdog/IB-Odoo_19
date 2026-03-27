# plasticos_transaction

**Version:** 19.0.6.1.0
**Category:** PlasticOS / Core Pipeline
**Depends:** `plasticos_base`, `plasticos_offer`, `plasticos_material_profile`, `plasticos_facility_profile`, `plasticos_logistics`, `plasticos_accounting`, `plasticos_commission`, `plasticos_security_base`

---

## Purpose

The transaction model is the **financial and operational record** of a closed deal. It bridges supplier intake, buyer offer, logistics, accounting, and commission into a single lifecycle record. This is the most complete model in the codebase (~54KB).

Every won deal has a transaction. Transactions drive gross margin reporting, commission calculation, freight bill linking, and document compliance tracking.

---

## Model: `plasticos.transaction`

### States

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

---

### Key Fields

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

### `amount_total` — Important

`amount_total` uses accrual-basis logic. **`@api.depends` must include `state`** — without it, the gross margin KPI banners in `transaction_ux.xml` can display stale values when a deal is cancelled or reverted to draft.

---

## Smart Buttons

| Button | Method | Source |
|---|---|---|
| Claims | `action_view_claims()` | **Defined in `plasticos_claims` bridge** — do NOT redefine here |
| Lines | `action_view_lines()` | Defined in `transaction.py` — added in GMP-001 |
| Load | `action_view_load()` | Defined in `transaction.py` |
| Commission | `action_view_commission()` | Defined in `transaction.py` |

> **Critical:** `action_view_claims()` is injected by `plasticos_claims` via `_inherit = 'plasticos.transaction'`. Adding a duplicate in `transaction.py` would shadow the bridge method. Never redefine it here.

---

## Views

| File | Description |
|---|---|
| `transaction_views.xml` | Primary form (tabs: General, Financials, Logistics, Documents, Commission), list, search |
| `transaction_ux.xml` | KPI banner overlays, gross margin highlights |

---

## Import Wizard

`wizards/transaction_import_wizard.py` — imports historical transaction data from a CIETrade CSV export.

**Default file:** `cieTrade.WksDetail.Test.csv` at the **repo root** (51-line test file). The production file (`cieTrade.WksDetail.csv`, 16,417+ rows) is excluded from the default path.

Path resolution: `os.path.join(module_path, os.pardir, DEFAULT_CSV)` — looks one level up from the module directory (repo root).

---

## Crons

| Cron | Action | Schedule |
|---|---|---|
| PlasticOS Sale Approval Flag | Flags transactions needing approval | Daily |
| PlasticOS Midnight Time-Based Field Recompute | Recomputes time-sensitive computed fields | Nightly 00:05 |

---

## Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_transaction --stop-after-init
```

**No `--update` needed** for method additions (no new stored fields). Required for new fields, ACL changes.

---

## Integration Points

| Module | Direction | Notes |
|---|---|---|
| `plasticos_offer` | Inbound | Created from `offer.action_create_transaction()` |
| `plasticos_logistics` | Bidirectional | `load_id` links to shipment; load state drives transaction state |
| `plasticos_accounting` | Outbound | `freight_bill_id` links to `account.move` — currently manual |
| `plasticos_commission` | Outbound | Commission calculated on `state = closed` |
| `plasticos_claims` | Bridge | Claims bridge injects `action_view_claims()` and `claim_ids` |

---

## Known Gaps / Pending

| Item | Priority | Notes |
|---|---|---|
| `amount_total @api.depends` missing `state` | High | KPI banners show stale values on cancel/revert |
| `supplier_profile_id` as source of truth | High | Currently informational; downstream views still use `supplier_id` directly |
| Freight Bill Auto-Link | Low | Complex heuristic (weight ±5%, date ±7 days, same carrier) — manual for launch |
| Full statusbar (all 8 states) | Medium | Currently only shows `draft, active, closed` |
| Commission auto-trigger on `state = closed` | High | `commission_service.calculate()` not yet called from transaction write |


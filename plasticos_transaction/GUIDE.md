# Plasticos Transaction Module — User Guide

Reference guide for the **plasticos_transaction** module (Odoo 19). Use this when configuring, importing, or bulk-updating transactions.

---

## 1. Overview

- **Model:** `plasticos.transaction` — core deal/trade record (supplier, buyer, product, weights, state).
- **Lines:** `plasticos.transaction.line` — line items (ERP WksDetail); one transaction has many lines.
- **Wizards:** Bulk Update (state), Bulk Assign (supplier/buyer), **CSV Import** (historical WksDetail upload).

---

## 2. Transaction States

| State | Code | Meaning |
|-------|------|---------|
| Draft | `draft` | New, not yet active |
| Active | `active` | In progress |
| Pending Supplier | `pending_supplier` | Waiting on supplier |
| Supplier Ready | `supplier_ready` | Supplier side ready |
| In Progress | `in_progress` | Being processed |
| In Transit | `in_transit` | Shipping |
| Delivered | `delivered` | Delivered |
| Invoiced | `invoiced` | Invoiced |
| Closed | `closed` | Completed (used for historical imports) |
| Cancelled | `cancelled` | Cancelled |

---

## 3. Wizards — Quick Reference

| Wizard | Purpose | Where to open |
|--------|---------|----------------|
| **Bulk Update Status** | Change state of selected transactions | Transaction list → Action → "Bulk Update Status" |
| **Bulk Assign Partners** | Set supplier and/or buyer on selected transactions | Transaction list → Action → "Bulk Assign Partners" |
| **Import Transactions (CSV)** | Upload historical transactions from ERP WksDetail CSV | PlasticOS menu → "Import Transactions (CSV)" |

---

## 4. CSV Import (ERP WksDetail)

### 4.1 Default file

- **Path:** `plasticos_transaction/ERP.WksDetail.csv`
- **Format:** CSV with header row; rows are **line items** grouped by transaction reference.

### 4.2 How it works

1. Rows are **grouped by `BuySellNo`** → one `plasticos.transaction` per unique `BuySellNo`.
2. Each row becomes a **`plasticos.transaction.line`** linked to that transaction.
3. Totals (sale amount, purchase amount, weight) are summed to the parent transaction.
4. Imported transactions are created in state **Closed** (historical data).

### 4.3 Main CSV columns → Odoo fields

| CSV Column | Odoo Field | Notes |
|------------|------------|--------|
| `BuySellNo` | `transaction.name` | Transaction reference (groups lines) |
| `DetailID` | `line.detail_id` | Original detail ID |
| `GradeID` | `line.grade_id` | Material grade code |
| `InvoiceDesc` | `line.description` | Material description |
| `SWeight` | `line.sale_weight` | Sale weight |
| `SPrice` | `line.sale_price` | Sale unit price |
| `SAmount` | `line.sale_amount` | Sale total |
| `PWeight` | `line.purchase_weight` | Purchase weight |
| `PPrice` | `line.purchase_price` | Purchase unit price |
| `PAmount` | `line.purchase_amount` | Purchase total |
| `Color` | `line.color` | Color |
| `ContainerNo` | `line.container_no` | Container number |
| `SealNo` | `line.seal_no` | Seal number |
| `SPo` | `line.sale_po` | Customer PO |
| `PPo` | `line.purchase_po` | Supplier PO |
| `Specifications` | `line.specifications` | Specs/notes |
| `Condition` | `line.condition` | Condition |
| `UnitType` | `line.unit_type` | B/G/X/P/L/A/F/H/C/E/O |
| `Units` | `line.units` | Number of units |

### 4.4 Using the Import Wizard

1. Go to **PlasticOS** menu → **Import Transactions (CSV)**.
2. **Options:**
   - **Use Default CSV File** — use `plasticos_transaction/ERP.WksDetail.csv`.
   - **Custom file** — uncheck and upload your own CSV.
   - **Dry Run** — preview only (no create).
   - **Skip Existing Transactions** — do not create duplicates (match on `name` = `BuySellNo`).
3. Click **Preview** to see counts (transactions to create, lines, skipped).
4. To import: uncheck **Dry Run** (or go to preview and click **Confirm Import**).

---

## 5. Bulk Update Status Wizard

- **Use when:** You need to change the state of many transactions at once.
- **Steps:** Select transactions in list view → **Action** → **Bulk Update Status** → choose new state and reason → **Execute**.

---

## 6. Bulk Assign Partners Wizard

- **Use when:** You need to set supplier and/or buyer on many transactions.
- **Steps:** Select transactions → **Action** → **Bulk Assign Partners** → choose action (Assign Supplier / Assign Buyer / Assign Both) → pick partner(s) and reason → **Assign Partners**.

---

## 7. Key Transaction Fields (for reference)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Unique transaction reference (e.g. from `BuySellNo`) |
| `state` | Selection | See §2 |
| `supplier_id` | Many2one res.partner | Supplier (company) |
| `buyer_id` | Many2one res.partner | Buyer (company) |
| `user_id` | Many2one res.users | Salesperson |
| `product_id` | Many2one product.product | Product (optional) |
| `expected_weight` / `actual_weight` | Float | Weights (lbs) |
| `historical_sale_total` / `historical_purchase_total` | Float (computed) | From line items |
| `line_ids` | One2many | Transaction lines (WksDetail) |

---

## 8. File Locations in Module

| Path | Purpose |
|------|---------|
| `models/transaction.py` | Main transaction model |
| `models/transaction_line.py` | Line items (WksDetail) |
| `wizards/transaction_import_wizard.py` | CSV import wizard |
| `wizards/transaction_bulk_update_wizard.py` | Bulk state update |
| `wizards/transaction_bulk_assign_wizard.py` | Bulk supplier/buyer assign |
| `ERP.WksDetail.csv` | Default CSV for import |
| `views/transaction_import_wizard_views.xml` | Import wizard UI + menu |

---

## 9. Dependencies

Module depends on: `base`, `mail`, `product`, `account`, `sale_management`, `purchase`, `plasticos_logistics`, `plasticos_material_profile`, `plasticos_facility_profile`, `plasticos_intake`.

---

*Last updated: 2026-02-20. For bug fixes and change log see `reports/BUG_FIXES_SUMMARY.md`.*

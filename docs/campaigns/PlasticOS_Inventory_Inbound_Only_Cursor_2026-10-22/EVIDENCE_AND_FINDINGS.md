# Evidence and root-cause boundary

## Pinned evidence

1. Source UI screenshot provided by operator: worksheet 60403, Sold To `(Inventory)`; second Sold To selector `GREENVIEW WASHINGTON WAREHOUSE`; Purchased From `JEI INC`; vendor PO `33498`; order dated 2026-04-13; item PP Purge, 38,580 lb; source worksheet status INVOICED.
2. Frozen, tracked `plasticos_partner_import/erp_extracted_data/bulk/Address.csv`, Staging e78af874: `404812,(INV),GREENVIEW WASHINGTON WAREHOUSE,...`. The frozen source also contains `404811,2331,INVOICE,GREENVIEW WASHINGTON WAREHOUSE,...` for a separate real party. These rows are NOT proof that those two AddressIDs are relationally interchangeable.
3. Frozen source contains 41 Address rows with `CpID=(INV)`, representing warehouse or inventory location labels. The `CounterParty` partner projection explicitly excludes pseudo-ID forms such as `(INV)`, and `source_index._link_children` drops addresses whose parent is outside the projected active counterparties. Those rows remain in indexed `Address` source data but are unavailable to the normal partner import path.
4. `24_buysell.sql` projects CustID/VendorID, dates, status and references, but no verified warehouse selector. `16_wksdetail.sql` omits `WarehouseLocation` even though it exists in source metadata. Do NOT assume `WKSDetail.WarehouseLocation` means the second Sold To warehouse; source schema/row values must prove the relationship first.
5. `native_document_import.py::_realize_one` emits a sale-link anomaly for each worksheet line missing `SPO_ID` / resolvable SO header, then reports `transactions.rejected` whenever no sale group exists, even with purchase documents. `_upsert_order` treats `sale.order.partner_id` as a mandatory external partner. `plasticos.transaction` is compiled from confirming a sale order, so a PO-only inventory acquisition cannot reach that path naturally.
6. 2025-2026 diagnostic CSV user attachment contains 168 missing transactions. Exactly 138 are `customer_id=(INV)`: 134 source closed, 1 source active, 3 cancelled. Of the 135 noncancelled inbound rows, 119 have a purchase link and 16 have no purchase link. Worksheet 60403 is one of the 119 linked cases; vendor 2106 JEI INC, purchase order 33498, and its source customer `'(INV)'` has no Odoo partner.
7. Another 15 rows in that diagnostic have `vendor_id=(INV)` (inventory outbound). This delegation does not change that separate direction. Positive outbound behavior reported by the operator must be regression-tested, not reimplemented here.

## Confirmed defect vs unknown

CONFIRMED: the importer mistakes inventory inbound (`CustID=(INV)`) for a missing commercial sale, and the normal company/location path does not preserve warehouse locations belonging to the pseudo-party.

UNKNOWN: the exact source field/key connecting worksheet 60403 to AddressID 404812; whether the warehouse is already represented by an appropriate native `stock.location`/`stock.warehouse` in this database; whether every source received flag proves completed stock movement; present-day stock reconciliation; the inventory-outbound positive control's source id.

The warehouse-name coincidence with a real partner must never be used as a fuzzy identity join.

## Source-code locators

- https://github.com/cryptoxdog/IB-Odoo_19/blob/e78af874604890f8adb6b049694f93c48311eab4/plasticos_transaction/models/native_document_import.py
- https://github.com/cryptoxdog/IB-Odoo_19/blob/e78af874604890f8adb6b049694f93c48311eab4/plasticos_partner_import/erp/source_index.py
- https://github.com/cryptoxdog/IB-Odoo_19/blob/e78af874604890f8adb6b049694f93c48311eab4/plasticos_partner_import/erp_extracted_data/11_address.sql
- https://github.com/cryptoxdog/IB-Odoo_19/blob/e78af874604890f8adb6b049694f93c48311eab4/plasticos_partner_import/erp_extracted_data/24_buysell.sql
- https://github.com/cryptoxdog/IB-Odoo_19/blob/e78af874604890f8adb6b049694f93c48311eab4/plasticos_partner_import/erp_extracted_data/16_wksdetail.sql

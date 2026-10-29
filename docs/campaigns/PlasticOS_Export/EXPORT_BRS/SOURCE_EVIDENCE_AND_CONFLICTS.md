# Exact source evidence, conflicts and unknowns

Observed at `cryptoxdog/IB-Odoo_19` Staging SHA `04bd0594a7c9dcad53d9c45fc65276d76817c112`, October 28 2026. Code is **not** integrated runtime evidence.

| Source | Verified observation | Consequence (not claimed fixed) |
|---|---|---|
| `plasticos_transaction/models/transaction.py` | `sale_order_id` Many2one, `purchase_order_ids` Many2many, `buyer_id` optional at model field, transaction `state` independent | Real SO/PO link possible; 30 SO loads/4 supplier PO loads need child allocations; no direct AI state writes |
| `plasticos_logistics/models/transaction_inherit.py` | `load_id` Many2one, unique one-load-to-one-transaction and constraint requiring supplier and buyer before assignment | Cardinality + buyer-optional movement need target-owner revision, not an Export-only workaround |
| `plasticos_logistics/models/load.py` | `sale_order_id` Many2one, `company_id` related from SO, auto-links first matching transaction only when buyer and supplier present; delivery_partner_id is independent | Need explicit company authority with buyerless loads, separate port/rail destination, and exact multiple associations |
| `plasticos_logistics/services/freight_context.py` | equipment_class None, repeat_stream bound to transaction intake | Equipment-sensitive drayage and PO/owned-stock movement origin not proven |
| `plasticos_documents_native/models/document_native.py` | `_auto_link_partner` guesses most recent open partner transaction, not exact booking or shipment | Must reject heuristic for export booking AI; exact match or review |
| `plasticos_documents/models/document.py` and Documents native bridge | Each has verification concepts | Existing authority duplication risk resolved by shared Documents owner, not Export |
| `plasticos_logistics/models/linda_request.py` | `po_issue` exact native PO approval/revision mechanism, unknown send outcomes distinguished | Reuse Linda for PO+booking issuance; four booking notices do not equal four new POs |

**Odoo 19 documented capabilities (availability/configuration unverified):** AI Document sort extracts/acts on uploaded files, AI Fields suggest values, AI server actions require a bounded worker to enforce actual business-rule writes. Native Stock supports partial packages/shipments and backorders. None proves our proposed exact matching, state automation, or multi-load bridging is implemented.

Documentation:
- https://www.odoo.com/documentation/19.0/applications/productivity/ai/document_sort.html
- https://www.odoo.com/documentation/19.0/applications/productivity/ai/fields.html
- https://www.odoo.com/documentation/19.0/applications/productivity/ai/server-actions.html
- https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/shipping_receiving/setup_configuration/multipack.html

**Unknown and open:** exact native partial sales/purchase bridge in installed Enterprise; current Staging may have changed since inspected SHA; whether an authorized Logistics business transition exists for a buyerless PO-backed move; whether Odoo 19 AI can extract every booking layout, source-locator quality; precise 30-load quantity UoM; company policies for PO attachment on later weekly releases; source-controlled container/loading relation; marine legal/title and filing responsibilities per trade.

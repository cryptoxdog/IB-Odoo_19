# Native-first capability map

Read as: **existing software foundations** vs. **RecycleOS-specific work not verified**. Source modules and manifests establish declared code, not production readiness.

| Need | Existing owner / likely reuse | Evidence/realization state | Proposed additive extension |
| --- | --- | --- | --- |
| Purchase, sales, accounting | Odoo purchase/sale/account + existing PlasticOS transaction model | Source-declared, running configuration not proven here | Use existing records and approvals |
| Stock receipts, locations, moves, deliveries, lots/packages | Native Odoo Stock/Inventory | Odoo capability; installed model and workflow unproven | Mobile dock orchestrates validated stock operations |
| Form conversion (scrap to regrind) | Odoo Manufacturing (`mrp`), BoM and Manufacturing Order | Native Odoo capability; custom PlasticOS manifests reviewed do not declare `mrp` | Configure/activate MRP; link input/output genealogy and profiles |
| Material type/form/grade | PlasticOS material profiles/registries | Existing registry declarations observed | Map operational stock products and lots to material semantics without duplicate registries |
| Load dispatch/BOL/logistics | PlasticOS `plasticos_logistics`, native stock/sales | Existing declared code, not a complete dock solution | Link scan/physical movement evidence to attributed load and documents |
| Scale tickets & document controls | `plasticos_documents`/logistics rules | Source rule/document boundary observed | Capture source/verified ticket with scoped evidence, no second original authority |
| Barcode fundamentals | `barcodes` in `plasticos_odoo_standard_apps` | Declared dependency | Support labels/identity and select fitting client surface |
| Odoo full warehouse Barcode app | Odoo Enterprise `stock_barcode` | **Not declared** in reviewed standard-app manifest; optional licensed module | Verify target deployment/license or choose compatible alternative |
| Mobile operator UI | Odoo web / PWA / available client options | Documentation-level possibility, not implemented for RecycleOS | Dedicated simple dock workflows with camera/handheld input |
| Platform-scale device weight | Indicator-specific protocol and/or Odoo IoT where compatible | **No integration observed** in the searched repo paths | Adapter or controlled manual entry; source attribution |
| Truck-scale / weighbridge | Certified scale indicator/software interfaces, ticket/evidence system | **No native or custom compatibility proven** | Hardware-neutral weighbridge adapter by model/site; legal suitability review |
| Label print | Odoo reports / appropriate printer mechanism | To verify by installed hardware | Durable QR package label and controlled reprint |
| Production costing | Odoo MRP work centers, accounting, inventory valuation | Native foundations, configuration not assessed | Keep optional; don't require cost/lb for dock rollout |
| Offline behavior | PWA/mobile local sync concept | **NOT PROVEN** | Do not promise until tested; preserve duplicate-safe replay and clear pending state |

## Recommended product boundary

### RecycleOS Dock owns UX, not ERP truth
The dock interface owns task-oriented presentation and controlled input capture. Canonical inventory remains in Odoo stock, manufacturing in native MRP, commercial transaction in the existing transaction/sale/purchase models, financial posting in native Accounting, documents/evidence in the current authorized records. Scale adapter owns acquisition/transport of observed reading, **not** right to settle, invoice or mutate inventory autonomously.

### Leverage hierarchy
1. Verify the existing Odoo license, modules, barcode UI and warehouse configuration.
2. Configure available native stock, packages, lot tracking, and MRP functions.
3. Identify minimal adaptation needed for a phone-based, one-confirmation dock workflow.
4. Bind a real platform scale with an isolated device interface or provide audited manual entry.
5. Add truck-scale adapter(s) only for sites using them, retaining shared weight semantics.
6. Demonstrate complete genealogy and the relevant native stock movements.
7. Optional: enrich production unit economics after data and operational behavior are trustworthy.

## Product packaging hypothesis
Make **mobile receiving, QR traceability and scale integration** core to product capability, not demand that every customer buy a scale, an Enterprise license, a dedicated handheld, or a separate iOS app. A site with only a floor scale should still work. Selection among Odoo Enterprise Barcode, a Community-compatible scanner layer, or a dedicated PWA is a pending licensing/operational decision, not a prematurely settled implementation.

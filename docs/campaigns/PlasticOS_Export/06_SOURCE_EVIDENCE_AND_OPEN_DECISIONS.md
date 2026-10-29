# Source evidence, confidence and unknowns

## Source-bound observation

**Repository:** `cryptoxdog/IB-Odoo_19`
**Branch at inspection:** `Staging`
**Pinned commit:** `04bd0594a7c9dcad53d9c45fc65276d76817c112`
**Observed in the source inspection accompanying this product conversation:** GitHub connector fetched exact pinned manifests and business-rule files. No local runtime, device, installed Odoo instance, warehouse picking or full test suite was executed for this exploration.

| Source path at pinned commit | Observed evidence | Do NOT infer |
| --- | --- | --- |
| `plasticos_odoo_standard_apps/__manifest__.py` | Core `stock`, `barcodes`, accounting, purchase and sales dependencies declared; no `stock_barcode` | Full Enterprise Barcode scanner installed |
| `plasticos_odoo_standard_apps/README.rst` | Explicit distinction between foundational `barcodes` and optional Enterprise `stock_barcode` | Community automatically includes warehouse barcode app |
| `plasticos_transaction/__manifest__.py` | Existing transaction bridge, native purchase, stock, sale and material dependencies | Full grinder manufacturing path exists |
| `plasticos_logistics/__manifest__.py` | Existing load, BOL, dispatch and stock links | Dock scan UI or integrated weighbridge exists |
| `plasticos_documents/__manifest__.py` and `data/scale_ticket_rule.xml` | Existing document classification/scale ticket compliance rule | Automatically verified industrial-scale readings exist |
| `plasticos_material_profile/__manifest__.py`, `models/material_profile.py` | Canonical polymer, form, color and profile concepts | Physical package and manufacturing product identity already reconciled |
| `plasticos_transaction/models/transaction.py` | Supplier/buyer/scale/manual weight fields and computed final weight | That computed final weight is lawfully payable or source of truth |
| `plasticos_logistics/business_rules/NATIVE_DOCUMENTS_INTEROP.md` | Explicit source-weight / settlement separation and native ownership boundaries; marked runtime NOT_RUN | The policy is fully implemented and enforced by installed server |

**Source link prefix:** https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/

### External capability assertions

Odoo 19's native warehouse, barcode, inventory, manufacturing, cost accounting, mobile web and IoT/scale facilities were discussed as potential reuse. Capabilities and licensing vary by edition, module and hardware. These are **upstream product features to confirm in an exact target Odoo installation**, not independently proven runtime results in PlasticOS. General official documentation: https://www.odoo.com/documentation/19.0/.

## Open decisions, not operator commitments

1. Which Odoo edition and module stack is commercially permissible for the first customer: Community-compatible dock scanning versus Enterprise `stock_barcode`?
2. Branded mobile PWA versus tailored native mobile app for later stages; PWA is a provisional low-friction preference, not a lock.
3. QR label identity: native Odoo package ID if sufficient or a mapped durable identifier; label design/printing and physical durability.
4. Which platform-scale make/model, connection protocol, stable reading signal, and tare procedure actually exist at the first grinder?
5. Which truck-scale hardware and legal-for-trade, calibration and ticketing rules apply to a target site? No blanket compatibility promise.
6. How to handle site-owned inventory, third-party material and toll-grinding custody without treating them identically?
7. What is the accepted commercial quantity authority for each movement/party when source business rules and some computed code field descriptions disagree?
8. Does target workflow require 24/7 offline operation? If so, select/test an explicit synchronization model.
9. Which native Odoo MRP setup accurately models process inputs, variable output, residuals and by-products for a grinder?
10. What exact operational actions can be safely performed by scanning and what requires role-based review?

## Conservative outcomes

**Accepted:** product direction, simplicity requirement, core/optional capability priority, native-first strategy, correct conceptual container flow.

**Observed:** source-declared existing PlasticOS modules and specific weight-law/code discrepancy.

**Proposed:** RecycleOS Dock surface, hardware adapters, candidate invariants and acceptance probes.

**Unknown / NOT_RUN:** commercial market response, production readiness, phone scanner at site, instrument integrations, installed Odoo modules, end-to-end traceability, certified weighbridge workflow, legally effective billing behavior.

## No-carryover assurance

All artifacts in the ZIP are new. This pack copies **zero** repository files or prior strategic packs. The links and file paths above are evidence coordinates only. It does not repackage or modify any upstream authority, plan, product code or historic campaign.

# Product exploration acceptance probes (NOT RUN)

These are **candidate design-validation scenarios**, not test receipts and not instructions to write code or purchase devices. The cheapest discriminating proof is an observed platform-scale receiving-to-outbound cycle in an Odoo test installation.

| ID | Scenario / falsifiable expectation | Scope |
| --- | --- | --- |
| AP-01 | On iPhone, scan container ID, capture/enter platform net weight, confirm once; exactly one native Odoo incoming receipt exists. | Core |
| AP-02 | Duplicate scan, retry or page refresh does not create a second receipt, container, or movement. | Core |
| AP-03 | Two Gaylords belonging to one lot have different container IDs and preserved individual weights. | Core |
| AP-04 | Scan a specific container into outgoing load; its identity and weight remain linked to the correct native delivery, no premature completion. | Core |
| AP-05 | Attempt to ship wrong-grade, absent, already-shipped or unauthorized-company package; no silent validation. | Core |
| AP-06 | Record 10 input containers consumed by an actual manufacturing order and 9 new output containers in a different product/form; genealogy remains navigable and input isn't simultaneously on-hand. | Grinder flow |
| AP-07 | Capture platform weight automatically for one verified indicator type; if unplugged, manual path is clearly attributed and does not falsely show device-captured proof. | Core scale applicability |
| AP-08 | Record truck gross/tare/ticket with device provenance and show net; no automatic modification of buyer AR/supplier AP solely from capture. | Truck-scale applicable |
| AP-09 | Reweigh and correct a container with approved action; old reading remains in audit history, and current net is not silently invented. | Core |
| AP-10 | Partially unload/repack a box; original and remaining quantities conserve mass (subject to explicitly recorded loss) and preserve genealogy. | Core edge |
| AP-11 | Label is damaged; controlled reissue or lookup preserves physical container identity rather than duplicating stock. | Core |
| AP-12 | Spotty network/duplicate event: show pending/unknown, retry once idempotently and never claim posted before Odoo confirms. | Deployment quality |
| AP-13 | Use ordinary inventory costing without providing cost-per-pound by batch; receipt, processing, and delivery are not blocked. | Optional-cost guard |
| AP-14 | Demonstrate real scanner client and exact license/installed Odoo modules; no claim about native Enterprise Barcode made on Community-only install. | Deployment gate |
| AP-15 | For customer-owned toll grinding, test whether custody vs ownership requires a distinct setup; no automatic vendor-owned raw-material valuation. | Exploratory, not locked |

## Suggested smallest real-world acceptance witness

1. A platform scale used by the target grinder (record model/indicator, serial/network output, tare behavior).
2. An iPhone camera scanning a printed or preprinted unique QR.
3. A fresh native incoming picking successfully posted for a single weighed Gaylord.
4. A second scan placing the same physical Gaylord on a native outgoing picking without duplication.
5. A manufacturing variant demonstrating source scrap inputs consumed and new regrind outputs received into stock.
6. Readback from the native database showing correct IDs, weights, genealogy, stock state, and original weight source.

**Evidence required for eventual PASS:** exact Odoo edition/version/build, installed modules, barcode client, device make/model and interface, traceable before/after stock moves, manufacturing order if relevant, retry/error behavior and operator feedback. None is available in this idea pack; all scenarios remain **NOT_RUN**.

## Priority of proof

A working iPhone + platform-scale + one-box receiving/shipping witness is the highest-value early discriminator because it probes actual operator simplicity, device integration and native inventory truth together. Full truck-scale support, offline sync, manufacturing costing optimization and a polished standalone app can follow on separate evidence.

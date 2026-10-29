# QR, scale, identity and record-authority boundaries

## Minimal physical identifiers

| Entity | Why distinct | Example |
| --- | --- | --- |
| Material definition / stock product | What material/form is purchased, made or sold | PP molded scrap vs PP regrind |
| Material lot / batch | Traceable production/receipt cohort | LOT-R-0042 |
| Container / package | Physically scannable individual Gaylord, pallet or bag | BOX-000184 |
| Weight observation | A specific scale/manual measurement, possibly repeated | WGT-00918 |
| Warehouse location | Where stock physically resides | FINISHED-A |
| Stock move / picking | Odoo's authoritative physical movement | Incoming transfer / outgoing transfer |
| Manufacturing order | Source of material transformation/genealogy | GRIND-ORDER-021 |
| Load / shipment | Physical carrier movement | LOAD-0019 |
| Commercial contract/order | Governs ownership, price, payable/billable quantity | Supplier PO, buyer SO |

A single lot can have many containers; a container can have multiple weight observations over time; a shipment can consist of partial containers or many containers. Each fact has one authoritative owner.

## QR encoding

**Prefer:** encode an immutable opaque container ID plus an application namespace/version as needed for reliable resolution. Printed human-readable short ID also appears on label. Authoritative grade, weight, location, lot genealogy and state are retrieved and permission-checked from Odoo, not embedded as mutable facts in QR payload.

**Alternative:** existing Odoo package/barcode identifier if it meets uniqueness, lifecycle and reader constraints. Do not create parallel identifiers unless needed and bridged to canonical package identity.

**Label:** short readable ID, barcode/QR, optional product and lot text for human convenience; printed text can be stale and never overrides current record.

## Scale interface contract (candidate, not an implementation schema)

- Device profile: model, interface type (RS-232/USB/TCP-IP/vendor API/file), site, precision, units, calibration/approved-for-trade attributes when relevant, connection and health.
- Measurement observation: raw reading, units, observed_at, device identity (or `manual`), operator/session, reading stability if supplied, gross/tare/net distinction, scale ticket identity, correction/supersession.
- Attribution: container or truck/trailer/load, related stock operation and evidence artifacts; never infer by "latest open" order.
- Validation: reject ambiguous unit, negative/impossible net, stale replay, crossed-device attribution, wrong company/site, duplicate operation, unapproved override.
- Output: accepted physical evidence to the specific authorized Odoo owner, not a second canonical quantity ledger.

### Platform versus weighbridge

**Platform scale:** weigh a box or pallet; tare includes container or pallet as applicable; capture per-container net, then sum actual attributed containers. A truck-scale gateway is unnecessary.

**Weighbridge:** weigh vehicle and trailer; distinguish gross/tare events, trailer/fuel/occupant/packaging effects where material, associate approved ticket, preserve legally required trace/certification. Truck net does not automatically equal sum of package nets or the billing quantity.

### Commercial quantity boundary

The existing PlasticOS source has a mismatch worth preserving as an unresolved integration seam:
- A code path in `plasticos_transaction/models/transaction.py` exposes a computed `final_weight` with documentation claiming it is used for billing and deductions, preferring a scale source.
- The later `plasticos_logistics/business_rules/NATIVE_DOCUMENTS_INTEROP.md` declares human-authenticated supplier weight for supplier AP, buyer weight for buyer AR, and certified scale weight as reference evidence only, with no universal final weight.

**Do not resolve that contradiction by interpretation or by making the scale feed `final_weight` directly.** Before a scale adapter can affect real inventory/settlement, an authorized domain owner must verify currently effective law, actual code writer/readers and native posting behavior, then define the correct distinction of physical receipt, carrier evidence and commercial terms. The packet makes no repository change.

## Physical events versus state transitions

`scan_observed` is not `receipt_posted`.
`scale_reading_captured` is not `certified_ticket_approved`.
`package_scanned_for_load` is not `shipment_completed`.
`input_scanned_for_grinding` is not `manufacturing_consumption_posted`.
`warehouse_stock_received` is not `invoice_approved`.

Only the native authorized transition or human approval can create the consequential state.

## Security and interoperability

- Respect Odoo permissions and company/site boundaries; QR ID alone is not authorization.
- Preserve originals and correction history, including operator, device and timestamps.
- Avoid putting customer details, prices or credentials in public label data.
- Validate actual supported scan formats, hardware model, Odoo edition/license and network/printing environment per target installation.
- Offline capture, if later supported, cannot silently manufacture stock movement; reconcile once through idempotent native operations.

# One-concern acceptance matrix

| Case | Required observation | Failure if |
| --- | --- | --- |
| Source key - WS 60403 | Exact source selector value resolves deterministically to the inventory destination record `AddressID=404812`, `CpID=(INV)`, `Type=GREENVIEW WASHINGTON WAREHOUSE` | The selector is guessed, or real-party `AddressID=404811` is substituted without a proven link |
| Inbound posted/closed source - WS 60403 | JEI INC vendor and PO 33498 retain identities; 38,580 lb PP Purge retained; destination warehouse identified; no ordinary customer or customer SO manufactured; import classification is inventory inbound, not commercial missing-buyer rejection | Source `(INV)` is created as a customer or receipt appears at a generic/default warehouse |
| Inbound other site - WS 58868 | Another `(INV)` inbound source with valid PO links to its actual selected warehouse, not a hardcoded Greenview location | One warehouse is assumed for every inventory inbound worksheet |
| Inbound missing PO - WS 58975 | Identity and destination evidence preserved, missing purchase link remains an explicit exception; nothing invented | Fake PO/header or customer generated to clear the rejection |
| Historical cancelled - status X | No inventory receipt/stock balance inserted for cancelled inbound source worksheets (3 cancelled in the sample); any legitimate shared order remains preserved | Cancelled source adds inventory or unrelated records are deleted |
| Inventory outbound control | One source-proven working `VendorID=(INV)` outward path retains its previous results and source identities | Inbound fix changes the reverse path |
| Ordinary sale control | One source-proven external customer transaction retains sale, purchase, and existing document results | Normal external sale is reclassified as inventory |
| No current-stock overstatement | Historical movements are not applied to today's on-hand/valuation unless source completion, historical outflow, custody/ownership and cutover reconciliation make this safe | Historic purchases add unearned present-day quantities or valuation |
| Replay | Second invocation on exact targeted fixtures creates zero duplicates across PO lines, destination links, stock artifacts, or source markers | A new stock/location/doc event is made for the same source key |
| Counting | `BuySell` and `WKSDetail` source row accounting still closes; inventory inbound has its own explicit outcomes; no modification of the shared summary schema without authority | Successful inbound acquisition remains mislabeled as a failed external sale |

## Minimum evidence

Pin source and local checkout SHAs; show exact inferred warehouse selector with 60403 value; show Odoo destination identity and source marker; before/after classified counts on the same targeted fixtures; native model and state snapshots; no extra source writes; targeted Odoo Enterprise test result and replay proof. No full overnight reimport.

Do not claim that all 138 recent inbound worksheets are now accepted. The evidence has 119 noncancelled rows with a valid purchase link and 16 requiring independent linkage investigation.

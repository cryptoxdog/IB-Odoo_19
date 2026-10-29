# 06 — Import dry run

**Current reading (2026-10-28):** The dry-run block below records the state when no document rows were available. It stays here as history. Every `W` and `#` image is eligible. The importer has not been run. The locked import scope is `11_IMPORT_SCOPE.md`.

**Contract:** `SM-erp-DOCUMENT-RECOVERY-001`  
**Gate D:** NOT RUN  
**Gate E:** NOT RUN

No Odoo destination was proven, because no document image and no `RefType` join exists. The importer was not implemented. A dry run against an empty or invented corpus would report a false green.

| Planned action | Count |
|---|---:|
| Originals to create | 0 |
| Typed evidence links | 0 |
| Unassigned / quarantine | 0 source images |
| Target missing | not evaluable |
| Duplicate originals | 0 |
| Side effects (mail, post, stock, verify) | none; no import code executed |

Worksheet and PO registry counts in `01_SOURCE_DISCOVERY.md` are not import candidates.

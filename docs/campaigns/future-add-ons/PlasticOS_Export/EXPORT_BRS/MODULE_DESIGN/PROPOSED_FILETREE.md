# Proposed `plasticos_export` module file tree

**Status:** Design blueprint only, not an installed addon or instruction to create files automatically. 
**Frozen envelope:** RecycleOS Phase 1 operator-approved architecture, 2026-10-28. 
**Source inspected:** `cryptoxdog/IB-Odoo_19`, Staging `04bd0594a7c9dcad53d9c45fc65276d76817c112`.

```text
plasticos_export/                       # Proposed future Odoo 19 addon
|-- __init__.py                           # Standard Odoo registration
|-- __manifest__.py                       # Exact existing dependencies, no new engine
|-- README.md                             # Hand-authored module README (in this pack)
|-- models/
|   |-- __init__.py
|   |-- booking.py                         # Booking identity, current sourced carrier terms
|   |-- booking_allocation.py             # Capacity-to-execution allocation, no stock ledger
|   |-- booking_revision.py               # ONLY if Documents + native tracking cannot prove revisions
|   `-- load_extension.py                  # _inherit plasticos.load for exact booking association
|-- security/
|   |-- ir.model.access.csv                # Business-role scoped access
|   `-- export_record_rules.xml           # Company/tenant isolation
|-- views/
|   |-- booking_views.xml                 # List, search, form, current revisions
|   |-- allocation_views.xml              # Available/committed/assigned space
|   |-- shipment_views.xml                # Links to existing load/transaction/container
|   |-- export_analysis_views.xml          # Search/pivot/graph and filtered report actions
|   `-- export_menus.xml                   # Overview, Bookings, Allocations, Shipments, Deadlines, Reporting
|-- report/
|   |-- export_report_actions.xml          # Native QWeb actions
|   |-- report_booking_summary.xml         # Source-labeled booking summary PDF
|   `-- report_container_manifest.xml     # Verified loading/packing report, when applicable
`-- tests/
    |-- __init__.py
    |-- test_booking_and_revision.py       # Original, roll, cancellation, precedence, retry
    |-- test_booking_allocation.py         # Multi-PO, multi-SO, equipment counts, concurrency
    |-- test_export_owner_handoff.py       # Correct Documents/Linda/Stock authority
    |-- test_views_and_reports.py          # Six reports, filters, drilldown, grouping
    `-- test_multicompany_permissions.py   # ACLs, no audience data leakage
```

## Why these files, and not more?

| Proposed source | Justified concern | Forbidden alternative |
| --- | --- | --- |
| `booking.py` | A carrier reservation exists without any load and can cover multiple parties, POs, and equipment slots | Implicitly treating a Sales Order or truckload as the carrier booking |
| `booking_allocation.py` | Confirmed carrier capacity can be assigned before a physical container/load exists and must count distinct slots once | Duplicate stock moves, a second order-quantity ledger, or inflating capacity when one slot contains multiple material lines |
| `booking_revision.py` **conditional** | Source-linked, immutable accepted carrier amendments only if `documents.document`, Odoo chatter and existing domain provenance cannot faithfully represent them | Copying original PDFs or creating a parallel document version engine |
| `load_extension.py` | A typed link to an existing Logistics load and booking, with no independent load state | Recreating dispatch, chassis, drayage pricing or gate-in state in Export |
| `export_analysis_views.xml` | Search and report drill-down over native models and accepted Export projections | A custom reporting SQL data warehouse or stand-alone dashboard API |
| QWeb templates | Only export-specific layouts not already provided correctly by native/Logistics reports | Reimplementing PO/SO PDFs, trucking BOL, invoice or carrier-issued ocean B/L |

The files above are **candidate implementation placement**, not frozen data model shapes. Verify actual installed Enterprise APIs, exact model/field existence, and module dependency closure before authoring Python or XML. Reject any proposed new file when an existing owner can faithfully meet the requirement.

## Odoo addon dependency direction

Minimal design dependency direction: `plasticos_export` consumes `plasticos_logistics` and the verified `plasticos_documents_native` / `plasticos_documents` interfaces. `plasticos_logistics` already depends on `plasticos_transaction`, Sale, Purchase and Stock. The native Documents bridge depends on Logistics; therefore Export may depend on it, but **the bridge and Logistics must not depend on Export**. Use source-owned commands/events to connect the other direction. If a declared cycle appears, fix placement/contract at the real owner rather than masking it with an import or hidden dynamic lookup. 

The exact Enterprise Dashboards technical module name and initialization mechanism **must be verified on the installed Odoo 19 runtime** before including a dashboard file or manifest dependency. Phase 1 may use configured native dashboards; a custom JavaScript/OWL dashboard is not a default or justified prerequisite. Do not create placeholder files for future integrations.

## What is intentionally absent

- No `controllers/`, public API, custom `static/` client or website portal in Phase 1.
- No Export freight/tender, appointment, dispatch or mail sender.
- No Export original file storage, OCR pipeline, compliance verification state, or custom ticket scheduler.
- No Export stock move/quant/package or customer/vendor invoice implementation.
- No Phase 1 AES submission, FindTEU webhook, forwarder integration, or ocean voyage execution.
- No broad demo fixtures or private evidence committed with an eventual addon.

## Conditional Phase 2 extension (not Phase 1 tree)

Once independently justified, separate provider-specific adapters may be implemented **at the actual integration owner**, with their own tests. FindTEU = optional observed ocean milestones in Export. AESDirect = operator-reviewed EEI filing support and official outcome evidence; direct certified filing remains out of scope without authorization and certification. The initial addon must work with neither provider installed.

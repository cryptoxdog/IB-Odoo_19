---
auto_generated: false
authority: derived-index
component_id: plasticos_export
component_name: PlasticOS Export
module_version: 19.0.1.1.0
installable: true
auto_install: false
application: true
depends:
  - base_automation
  - purchase
  - sale
  - stock
  - plasticos_security_base
  - plasticos_logistics
  - plasticos_documents
  - plasticos_documents_native
models_owned:
  - plasticos.export.booking
  - plasticos.export.booking.revision
  - plasticos.export.booking.slot
  - plasticos.export.booking.cargo.link
models_extended:
  - plasticos.document
  - plasticos.load
  - plasticos.logistics.request
crons: []
---

# PlasticOS Export

The front matter above is a derived index. `__manifest__.py` wins on any conflict.

## What it is

The Odoo addon for export bookings and shipments: recycler FOB pickup and FAS port or rail delivery in Phase 1, and the international sale later. It is part of the PlasticOS Export campaign (plan of record: `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`).

Export owns only the export-specific context: the booking, its revisions, equipment and slots, applicability declarations, views and QWeb layouts (`BRS-EXP-01-R001`). Every other fact stays with its owner: original files with native Documents, evidence verification with `plasticos_documents`, orders and invoices with native Sales, Purchase and Accounting, stock moves with native Stock, freight, dispatch and outbound operational mail with `plasticos_logistics` and Linda (`BRS-EXP-01-R002`).

## State at this version

`19.0.1.1.0` (slice S5B, contract `PLASTICOS-EXPORT-C05-S5B-EXPORT-MODELS-UI-REPORTS`) adds the four Export models of the technical contract (`EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json`) and their six public commands. J1/J2 stay with Logistics.

| Model | What it is | Commands |
| --- | --- | --- |
| `plasticos.export.booking` (E1) | One carrier reservation of one company, identified by issuer and source booking cycle, never by the number alone | `record_booking_revision_candidate`, `action_accept_booking_revision`, `action_request_booking_notice` |
| `plasticos.export.booking.revision` (E2) | One source snapshot. A candidate until accepted; immutable once accepted | — |
| `plasticos.export.booking.slot` (E3) | One distinct confirmed equipment unit; binds at most one container journey (J1) | `action_commit_cargo`, `action_release_cargo`, `action_bind_journey` |
| `plasticos.export.booking.cargo.link` (E4) | One exact native cargo source of a slot; planned quantity only | — |

Commands return `{"status": applied|already_applied|stale|blocked|ambiguous|not_available, "record_id"?, "reason"?}`. They run only as a Logistics user of the record's company, never through sudo. Acceptance is a compare-and-set on `current_revision_id` and reconciles slots in the same transaction; a lower confirmed count retires free slots first and holds committed or bound ones. Lock order is the booking row, then slots in id order.

Downstream extensions, by ordinary `_inherit` only:

- Linda (`plasticos.logistics.request`): the `booking` typed source resolver and the booking model for reply attribution. The resolver checks the caller's role, record access and company before anything else, so an unauthorized `request_booking_correspondence` is `not_available` (C05 E3). Linda stays the only sender and requires the company's own `email_normalize`-valid address (C05 E6). Export adds no mail template.
- Logistics (`plasticos.load`): a load committed to a held, retired or cancelled slot gets no new physical instruction.
- Documents (`plasticos.document`): Export declares four operation obligations (`booking_confirmation`, `verified_gross_mass`, `loading_photos`, `terminal_ingate_receipt`) and narrows `_release_obligations`: a stale booking confirmation withholds schedule, dispatch, dispatch packet and carrier documents; stale VGM withholds carrier documents only; loading photos and the terminal in-gate receipt never withhold a new instruction (C05 E1/E2). Obligations other owners declare keep the Documents default. An Export booking may carry operation evidence.

Data and UI: least-privilege ACL (Logistics and Operations Manager read/write/create, Sales Rep read, nobody unlinks), global company record rules on all four models, booking/allocation/shipment views, a deadline calendar, six native reports (Booking Space Availability, Booking Allocation / Container Manifest, Open Supplier PO / Customer SO Fulfillment, Container Shipment Register, Cutoff & Booking Exceptions, Missing Export Documents), the Export menu, two QWeb reports (booking summary, container manifest) and a booking-only Linda inbound reply trigger (`data/linda_booking_inbound.xml`). No controller, cron or external effect.

Quantities use native `uom.uom` records. Pounds are `uom.product_uom_lb` (shipped inactive by Odoo 19 `uom`; Export references it and creates no unit). Odoo 19 has no US short ton record; `uom.product_uom_ton` is the metric tonne.

## Installation

- `installable` and `application` are true; `auto_install` is false. Nothing installs it until someone does so on purpose.
- It depends on `plasticos_documents_native`, so the host needs Odoo Enterprise `documents` and `documents_account`. It also names the owners it extends or reads directly: Logistics, Documents, Security Base, native Purchase, Sale and Stock, and `base_automation`.
- Dependency direction is Export to Logistics, Documents and Security Base. No module may depend on `plasticos_export`; `tests/test_repo_dependency_integrity.py` checks it.
- Docker testing: the module is in `default_install_order` of `config/odoo_module_order.yaml`, so the pinned Enterprise test fixture installs it and the PR gate upgrades and tests it. That roster is Docker-only; Odoo.sh does not read it.
- No external effect is enabled: Linda is `off` by default, and there is no carrier call, FindTEU or AESDirect.

## Business rules

The 120 Export rules (`BRS-EXP-01` to `BRS-EXP-14`) live in [`business_rules/`](business_rules/README.md), copies of the campaign pack with their SHA-256 and their pack source's SHA-256 recorded. Read that README before any Export change. Each change names the rule IDs it realizes and gives an observable test, or marks the case `NOT_RUN`. `tests/contracts/test_export_brs_registry.py` guards the copies.

The campaign pack stays the provenance. Its private operator originals (`EXPORT_BRS/SOURCES/PRIVATE_OPERATOR_CASE_PO64014/`) are evidence for the rule authors, not module payload; nothing in this addon reads or ships them.

## Tests

- Pure Python: `tests/contracts/test_export_brs_registry.py` and the Export checks in `tests/test_repo_dependency_integrity.py`.
- Odoo runtime, in `plasticos_export/tests/`: `test_install.py` (install witness), `test_booking_and_revision.py` (E1/E2), `test_booking_allocation.py` (E3/E4, PHASE1 gate case, release hold, live PO constraints), `test_document_obligations.py` (E1/E2 obligations per operation kind), `test_export_owner_handoff.py` (Linda, E3, E6, reply trigger, no shadow writer), `test_views_and_reports.py` (six reports, QWeb) and `test_multicompany_permissions.py` (company access). Each test names the BRS rules it witnesses.

## Read next

- [`business_rules/README.md`](business_rules/README.md)
- `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`
- [`../plasticos_documents_native/README.md`](../plasticos_documents_native/README.md)
- [`../plasticos_logistics/business_rules/README.md`](../plasticos_logistics/business_rules/README.md)

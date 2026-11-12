---
auto_generated: false
authority: derived-index
component_id: plasticos_export
component_name: PlasticOS Export
module_version: 19.0.1.3.0
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
  - plasticos.export.booking.revision.accept
  - plasticos.export.booking.manual.candidate
  - plasticos.export.booking.manual.candidate.line
  - plasticos.export.source.line.claim
  - plasticos.export.slot.command.mixin
  - plasticos.export.slot.commit.cargo
  - plasticos.export.slot.release.cargo
  - plasticos.export.slot.bind.journey
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

Commands return `{"status": applied|already_applied|stale|blocked|ambiguous|not_available, "record_id"?, "reason"?}`. They run only as a Logistics user of the record's company, never through sudo. Acceptance is a compare-and-set on `current_revision_id` and reconciles slots in the same transaction. A slot already held counts as withdrawn capacity: a lower confirmed count retires free slots first and holds committed or bound ones, and a later count that restores capacity lifts those holds first (their cargo is committed again) before adding slots. `slot_confirmed_count` is what the current accepted revision confirms; held slots are counted apart. A local ERD or cutoff that a daylight-saving change makes ambiguous or nonexistent is refused, never guessed. Computed, related and `company_id` fields are never written by an ordinary write, so a row cannot be relabelled across companies or have its derived state forged. Accept Revision on the revision form opens a confirmation (`plasticos.export.booking.revision.accept`) that captures the booking's current revision when it opens; confirming runs the compare-and-set against that value, so a stale confirmation is refused. The deadline calendar keys on `current_cargo_cutoff_date`: the local date the source stated. Planned quantities are never summed across units. A role without purchase read sees that a cargo link has a PO, not the PO's terms. Lock order is the booking row, then slots in id order.

Downstream extensions, by ordinary `_inherit` only:

- Linda (`plasticos.logistics.request`): the `booking` typed source resolver and the booking model for reply attribution. The resolver checks the caller's role, record access and company before anything else, so an unauthorized `request_booking_correspondence` is `not_available` (C05 E3). Linda stays the only sender and requires the company's own `email_normalize`-valid address (C05 E6). Export adds no mail template.
- Logistics (`plasticos.load`): a load committed to a held, retired or cancelled slot gets no new physical instruction.
- Documents (`plasticos.document`): Export declares four operation obligations (`booking_confirmation`, `verified_gross_mass`, `loading_photos`, `terminal_ingate_receipt`) and narrows `_release_obligations`: a stale booking confirmation withholds schedule, dispatch, dispatch packet and carrier documents; stale VGM withholds carrier documents only; loading photos and the terminal in-gate receipt never withhold a new instruction (C05 E1/E2). Obligations other owners declare keep the Documents default. An Export booking may carry operation evidence.

Data and UI: least-privilege ACL (Logistics and Operations Manager read/write/create, Sales Rep read, nobody unlinks), global company record rules on all four models, a read-only cargo-link rule that lets a same-company Sales Rep read every allocation of every booking (operator decision 2026-11-12, `business_rules/SUPERSESSION.md`) while the loads, sale orders and purchase orders behind those rows stay owner-scoped (non-Logistics readers see their names as text or non-opening references; the manifest, exports and the PO/SO/supplier search fields use the link's own name fields, so another rep's allocation is listed, printed and found by order name), booking/allocation/shipment views, a deadline calendar, six native reports (Booking Space Availability, Booking Allocation / Container Manifest, Open Supplier PO / Customer SO Fulfillment, Container Shipment Register, Cutoff & Booking Exceptions, Missing Export Documents), the Export menu, two QWeb reports (booking summary, container manifest) and a booking-only Linda inbound reply trigger (`data/linda_booking_inbound.xml`). No controller, cron or external effect.

`19.0.1.1.3` (slice S8, contract `PLASTICOS-EXPORT-C08-S8-COVERAGE-AND-ALLOCATION-GUARD`) adds the allocation guard of `BRS-EXP-08-R006` to `action_commit_cargo`, with no new public command. A Logistics load or a stock move line sits on at most one live (not released) cargo link; the known planned quantities on one PO or SO line, converted to that line's unit, never exceed the line's own quantity, and a unit that does not convert is refused. The command row-locks the cargo sources before it checks, a model constraint repeats the check for any guarded write, and two partial unique indexes refuse a concurrent second link on the same load or move line. A correction or split passes `replaces_link_id` and `correction_reason` in `source_refs`: the replaced link is released (never edited), each new part records what it replaces, and the booking chatter names the user and the reason. When the replaced link sits on another booking, that booking is locked as well, and `replaced_booking_revision_id` must name its current revision.

Concurrent commits planning on one PO or SO line serialize on one Export-owned row per line. `plasticos.export.source.line.claim` is the module's seventh registry model and is internal: it has no view, menu, action or command, and it stores no quantity. Its conflict key is (line model, line id); `company_id` is stored, and a company record rule keeps each row in its company. Each commit upserts and bumps it before the guard checks. While a first commit is in flight, a second one naming the same line is refused earlier with `cargo_source_busy`. Once the first has committed, a second transaction whose REPEATABLE READ snapshot predates it fails to serialize on the row and is retried, and the retry counts the first. `claim_count` is an attempt counter and is never used for a decision. Logistics and Operations Manager can read it in their own companies; Sales Reps cannot. No native PO or SO row is written, and the public shapes of the technical contract (E1–E4, J1–J2, the twelve commands) are unchanged (C08 SCOPE-2, OP8-E03).

`19.0.1.2.0` (slice S10, contract `PLASTICOS-EXPORT-C11-S10-EXPORT-FEATURES`) adds displays and one input. Export still stores no owner fact:

- Owner facts (`BRS-EXP-01-R002`, `BRS-EXP-07-R006`). The cargo link, slot and booking forms show the facts below. Each one is computed live as the acting user and is never stored:
  - the Documents verdict of each Export obligation, through `get_scoped_evidence_verdict`;
  - the Logistics load status;
  - the native stock move line and its package's shipping weight and package type nominal weight (Stock `base_weight`; not a tare measurement);
  - posted customer invoices and vendor bills;
  - the slot's package totals, labelled "not a certified VGM", and the Documents VGM verdict.

  A fact the user may not read shows a restricted marker, never a blank or a zero (`BRS-EXP-14-R022`). The slot also shows the container tare and VGM weight that Logistics records on the bound journey (`plasticos.iso.journey.fact`), and a shipment history: the recorded gate-in, departure and filing parties, then every cargo allocation, oldest first. A buyer assigned after sailing is a new allocation that replaces the buyerless one (`BRS-EXP-08-R007`); no journey fact or booking revision changes with it. Container weights and identities stay with Logistics. A user who cannot read the Logistics journey facts (only Logistics, which Operations Manager implies, and System can after the S9 review) sees "Restricted" for the container tare, the VGM weight and the shipment-history container facts, and gets no journey link. Export adds no sudo to show them. The operator's see-all rule covers allocations, so a Sales Rep still sees every cargo allocation on every booking through the `*_ref` names and can plan without overbooking (coordinator ruling 2026-11-12).
- Commercial trade label (`BRS-EXP-02-R006`). A cargo link stores the quoted FOB, FAS or CNF usage and its quoted wording. The Set Trade Label dialog on the cargo link edits it; any write by a Logistics user is accepted the same way, and every change posts an audit note on the booking. The order Incoterms are shown beside it and never written.
- Record Booking Candidate (`BRS-EXP-09-R001` manual fallback). This booking button opens `plasticos.export.booking.manual.candidate`. The screen hands the typed terms to `record_booking_revision_candidate` as the acting user, so every command guard applies. It stores no file and makes nothing current. Native Documents AI is not activated.
- Slot command screens (C11-SCOPE-2). Commit Cargo (including a replacement of an earlier link), Release Cargo and Bind Container call the existing slot commands as the acting Logistics user and store nothing.
- Sales Rep see-all (C11-SCOPE-3). Booking search by container and seal goes through the slot's own fields. Only readers of the container journey (Logistics, Operations Manager, System) get an openable journey and the Open Container Journey button. The Export dialog offers a user outside Logistics no cargo-link source link and, outside the journey readers, no slot journey; the `*_ref` names stay exportable.
- Legacy booking report (`BRS-EXP-14-R011`). `_legacy_booking_report_groups()` lays live cargo links out under the 43 legacy headings, grouped by booking. Every cell is a value or an explicit Missing, Unknown, Not recorded, Not mapped, Phase 2 or Restricted marker. It only reads. `tests/data/` holds a synthetic 43-heading workbook, its generator and the heading inventory.

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
- Odoo runtime, in `plasticos_export/tests/`: `test_install.py` (install witness), `test_booking_and_revision.py` (E1/E2), `test_booking_allocation.py` (E3/E4, PHASE1 gate case, release hold, live PO constraints), `test_document_obligations.py` (E1/E2 obligations per operation kind), `test_export_owner_handoff.py` (Linda, E3, E6, reply trigger, no shadow writer), `test_views_and_reports.py` (six reports, QWeb), `test_multicompany_permissions.py` (company access; the Sales Rep allocation audience of 2026-11-12). `native_fixture.py` builds a native Enterprise fixture (30-load SO, 4-load supplier POs, weekly receipts with backorders, a partial delivery, a posted invoice, a verified document); on it `test_native_coverage.py` witnesses the deferred rules of S8 and `test_allocation_guard.py` witnesses `BRS-EXP-08-R006`. S10 adds `test_owner_facts.py` (owner facts, trade label), `test_manual_booking_candidate.py` (manual booking entry), `test_slot_command_screens.py` (Commit Cargo, Release Cargo and Bind Container screens) and `test_legacy_booking_report.py` (43-heading conformance). Each test names the BRS rules it witnesses.

## Read next

- [`business_rules/README.md`](business_rules/README.md)
- `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`
- [`../plasticos_documents_native/README.md`](../plasticos_documents_native/README.md)
- [`../plasticos_logistics/business_rules/README.md`](../plasticos_logistics/business_rules/README.md)

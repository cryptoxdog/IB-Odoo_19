---
auto_generated: false
authority: derived-index
component_id: plasticos_export
component_name: PlasticOS Export
module_version: 19.0.1.0.0
installable: true
auto_install: false
application: true
depends:
  - plasticos_documents_native
models_owned: []
models_extended: []
crons: []
---

# PlasticOS Export

The front matter above is a derived index. `__manifest__.py` wins on any conflict.

## What it is

The Odoo addon for export bookings and shipments: recycler FOB pickup and FAS port or rail delivery in Phase 1, and the international sale later. It is part of the PlasticOS Export campaign (plan of record: `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`).

Export owns only the export-specific context: the booking, its revisions, equipment and slots, applicability declarations, views and QWeb layouts (`BRS-EXP-01-R001`). Every other fact stays with its owner: original files with native Documents, evidence verification with `plasticos_documents`, orders and invoices with native Sales, Purchase and Accounting, stock moves with native Stock, freight, dispatch and outbound operational mail with `plasticos_logistics` and Linda (`BRS-EXP-01-R002`).

## State at this version

`19.0.1.0.0` is the installable scaffold (slice S5A). It has no model, view, report, ACL, mail rule, cron or data record, so installing it writes nothing and changes no workflow. It carries the module-owned business rules and proves the dependency graph and the test roster. The six models and twelve commands of the technical contract (`EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json`) come in later slices, after the Logistics, Documents and Linda changes they depend on.

## Installation

- `installable` and `application` are true; `auto_install` is false. Nothing installs it until someone does so on purpose.
- It depends on `plasticos_documents_native`, so the host needs Odoo Enterprise `documents` and `documents_account`.
- Dependency direction is Export to Logistics, Documents and Security Base. No module may depend on `plasticos_export`; `tests/test_repo_dependency_integrity.py` checks it.
- Docker testing: the module is in `default_install_order` of `config/odoo_module_order.yaml`, so the pinned Enterprise test fixture installs it and the PR gate upgrades and tests it. That roster is Docker-only; Odoo.sh does not read it.
- No external effect is enabled: no mail send, carrier call, FindTEU or AESDirect.

## Business rules

The 120 Export rules (`BRS-EXP-01` to `BRS-EXP-14`) live in [`business_rules/`](business_rules/README.md), copies of the campaign pack with their SHA-256 and their pack source's SHA-256 recorded. Read that README before any Export change. Each change names the rule IDs it realizes and gives an observable test, or marks the case `NOT_RUN`. `tests/contracts/test_export_brs_registry.py` guards the copies.

The campaign pack stays the provenance. Its private operator originals (`EXPORT_BRS/SOURCES/PRIVATE_OPERATOR_CASE_PO64014/`) are evidence for the rule authors, not module payload; nothing in this addon reads or ships them.

## Tests

- Pure Python: `tests/contracts/test_export_brs_registry.py` and the Export checks in `tests/test_repo_dependency_integrity.py`.
- Odoo runtime: `plasticos_export/tests/test_install.py` is the install witness: the module is installed at the manifest version, depends only on `plasticos_documents_native`, and owns no model, menu, view or record. The acceptance suites of later slices join it in `plasticos_export/tests/`.

## Read next

- [`business_rules/README.md`](business_rules/README.md)
- `docs/campaigns/future-add-ons/PlasticOS_Export/STRATEGIC_EXECUTION_PLAN_v2.8.md`
- [`../plasticos_documents_native/README.md`](../plasticos_documents_native/README.md)
- [`../plasticos_logistics/business_rules/README.md`](../plasticos_logistics/business_rules/README.md)

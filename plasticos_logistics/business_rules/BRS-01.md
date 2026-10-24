# BRS-01: Transaction, movement identity and company boundary

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_logistics`.

## Responsibility boundary

Load association, transaction spine and release eligibility.

## Evidence-traced candidate rules

### BRS-01-R001: Machine release starts Linda with Odoo PO/SO issuance

- Requirement: `LR-001`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Exactly one eligible commercial transaction/movement, with its correct company and currently permitted counterparties, must reach a machine-observable Approved-like issue/release transition before Linda issues applicable PO and SO. Linda then resolves/creates those native Odoo orders, renders current Odoo PDF reports, sends the locked supplier and buyer templates from logistics2@scrapmanagement.com through Google Workspace Gmail, records truthful per-order sent results, and hands off to Pending Logistics. A preapproved counterparty is an eligibility condition, never an independent order-send trigger. No extra human review, salesperson Ready utterance, record creation, import, retry or unrelated load can initiate issuance. Supplier cargo READY remains a separate downstream verified fact.
- **Historical original preserved:** One exact released transaction/movement starts one load-specific readiness obligation. Never trigger external coordination solely from import/create.
- Source evidence: `E43, E25, E20, T04, T14`.
- Existing target path/owner: `plasticos_logistics/models/sale_order_inherit.py + models/load.py`.
- Proposed tests: AC-V01, AC-V02, AC-V18, AC-UI01, AC-UI02, AC-UI03, AC-UI04, AC-BR01, AC-BR02; **NOT RUN**.
- Source-policy reconciliation: `PR-01` in `policy_resolution.json`.

### BRS-01-R002: Exact transaction/load/PO/SO association

- Requirement: `LR-002`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Every consequential request identifies company, load, transaction and actual facilities; shared order reference alone is ambiguous.
- **Historical original preserved:** Every consequential request identifies company, load, transaction and actual facilities; shared order reference alone is ambiguous.
- Source evidence: `E06, E43, E46, T01, T13, T38`.
- Existing target path/owner: `plasticos_logistics/models/load.py + models/transaction_inherit.py`.
- Proposed tests: AC-V03, AC-V04, AC-V88; **NOT RUN**.

### BRS-01-R003: Company ownership cannot be unknown for automation

- Requirement: `LR-003`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** No automatic coordination on company-less or conflicting source records, even when user has access to both companies.
- **Historical original preserved:** No automatic coordination on company-less or conflicting source records, even when user has access to both companies.
- Source evidence: `E46, E06, T01, T23`.
- Existing target path/owner: `plasticos_logistics/models/load.py; plasticos_security_base/security/record_rules.xml`.
- Proposed tests: AC-V04, AC-V80; **NOT RUN**.

### BRS-01-R065: Mechanical transaction eligibility before automatic order issuance

- Requirement: `LR-065`. Effective disposition: `MERGE_WITH_EXISTING_AND_HARDEN`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Linda issues orders only after an exact commercial transaction reaches its Approved-like machine issuance event and all source-authoritative eligibility gates are satisfied: current active supplier and buyer/approved contacts, correct company, required vendor onboarding form when applicable, and complete movement association. Preapproved-party status can satisfy its own eligibility check but never releases an order alone. No second Linda human approval is added. The implementation maps the existing or necessary Odoo field/event in technical design; no field literally named approved is asserted by this pack.
- **Historical original preserved:** Logistics consumes approved eligible contacts; vendor onboarding/first-PO policy remains upstream.
- Source evidence: `E04, E05, E25, T04, T24`.
- Existing target path/owner: `plasticos_transaction existing eligibility and plasticos_logistics entry handoff`.
- Proposed tests: AC-V02, AC-V84, AC-V90, AC-UI01, AC-UI02, AC-BR01, AC-BR02; **NOT RUN**.
- Source-policy reconciliation: `PR-01` in `policy_resolution.json`.
- Donor-era disposition retained for provenance: `DEFER_OUT_OF_SCOPE`. This is not an outstanding approval gate.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

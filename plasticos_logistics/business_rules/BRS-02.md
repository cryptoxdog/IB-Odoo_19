# BRS-02: Supplier readiness and verified responses

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_logistics`.

## Responsibility boundary

One attributable supplier answer for the right load/request.

## Evidence-traced candidate rules

### BRS-02-R004: Direct shipper READY for every load

- Requirement: `LR-004`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Only attributed current shipper evidence authorizes readiness; record confirmer identity, event/received time and actual cargo availability.
- **Historical original preserved:** Only attributed current shipper evidence authorizes readiness; record confirmer identity, event/received time and actual cargo availability.
- Source evidence: `E43, E01, E21, E22, T01, T17, T04`.
- Existing target path/owner: `plasticos_logistics/models/load.py; plasticos_automation supplier bridge`.
- Proposed tests: AC-V11, AC-V18, AC-V21, AC-UI05, AC-UI09; **NOT RUN**.

### BRS-02-R005: Ready date versus proposed date

- Requirement: `LR-005`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Ready interval, proposal, confirmation time and planned pickup remain different facts.
- **Historical original preserved:** Ready interval, proposal, confirmation time and planned pickup remain different facts.
- Source evidence: `E21, E22, E06, T01, T04`.
- Existing target path/owner: `plasticos_logistics/models/load.py`.
- Proposed tests: AC-V17, AC-V55; **NOT RUN**.

### BRS-02-R006: Explicit negative and corrected responses

- Requirement: `LR-006`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Not-ready/correction blocks affected commitments, retains previous proof and resumes only through a current accepted revision.
- **Historical original preserved:** Not-ready/correction blocks affected commitments, retains previous proof and resumes only through a current accepted revision.
- Source evidence: `E09, E22, E43, T01, T04`.
- Existing target path/owner: `plasticos_logistics/models/load.py and native party conversation`.
- Proposed tests: AC-V19, AC-V16, AC-V82; **NOT RUN**.

### BRS-02-R007: Source-defined Monday shipper status cadence

- Requirement: `LR-007`. Effective disposition: `SOURCE_POLICY_RESOLVED_RUNTIME_CONFIG_DEFERRED`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** For each current PO/load that is not yet physically READY, Linda sends one supplier status request every Monday morning in the supplier-local morning window, identifying the PO number and shipper company. Do not convert a projected ready date into verified READY, run a second weekly touch for the same open status obligation, or extend the request after verified READY, cancellation, or supersession. A specific hour within that source-defined morning window is runtime scheduler configuration, not a new business-policy approval.
- **Historical original preserved:** Before final READY, one approved Monday-morning status touch uses PO number and shipper company, not just DO; stop on readiness/cancel.
- Source evidence: `E43, E44, E14, T17, T16`.
- Existing target path/owner: `existing plasticos_logistics cron + plasticos_automation mail templates`.
- Proposed tests: AC-V20, AC-V50; **NOT RUN**.
- Source-policy reconciliation: `PR-03` in `policy_resolution.json`.
- Donor-era disposition retained for provenance: `CONFIGURE_AFTER_APPROVAL`. This is not an outstanding approval gate.

### BRS-02-R008: Required cargo/equipment facts

- Requirement: `LR-008`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Require material identity, authoritative quantity/weight when relevant, trailer/loading constraints and pickup contact; missing facts block.
- **Historical original preserved:** Require material identity, authoritative quantity/weight when relevant, trailer/loading constraints and pickup contact; missing facts block.
- Source evidence: `E06, E43, E21, T01, T12`.
- Existing target path/owner: `plasticos_logistics/models/load.py`.
- Proposed tests: AC-V36, AC-V28, AC-V68; **NOT RUN**.

### BRS-02-R009: Google Workspace Gmail through native Odoo Mail

- Requirement: `LR-009`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Linda sends and receives as logistics2@scrapmanagement.com through the existing Google Workspace Gmail provider connected to native Odoo Mail. Preserve original messages, recipient audiences, Gmail/native Message-ID and thread/request identifiers, attachments and Odoo audit trail. Mailbox OAuth, routing and delivery must be verified during later technical design; no second logistics email processor or orchestration platform.
- **Historical original preserved:** Use native mail routing and retained message IDs/attachments; custom-domain routing must be tested in an isolated environment.
- Source evidence: `E30, E47, E02, T01, T37, O01`.
- Existing target path/owner: `plasticos_logistics Mail integration; configured Odoo alias domain`.
- Proposed tests: AC-V09, AC-V10, AC-V78, AC-UI06, AC-UI14; **NOT RUN**.

### BRS-02-R010: Typed request evidence with minimal new persistence

- Requirement: `LR-010`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** A fixed-purpose party-scoped request binds load/company/party/revision/payload and native messages. Response lifecycle is not another load state machine.
- **Historical original preserved:** A fixed-purpose party-scoped request binds load/company/party/revision/payload and native messages. Response lifecycle is not another load state machine.
- Source evidence: `E06, E21, E37, E38, T01, T09, T10`.
- Existing target path/owner: `plasticos_logistics, one proposed load-confirmation record type`.
- Proposed tests: AC-V11, AC-V15, AC-V16, AC-V43, AC-UI06; **NOT RUN**.

### BRS-02-R011: Attributed confirmation through validated reply or secure action

- Requirement: `LR-011`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** A current explicit confirmation from an authorized supplier/buyer/carrier may arrive as a scoped Gmail reply or a verified structured confirmation action. Linda binds sender and company/party authorization, exact current request, load, purpose, document/version and clear intent before a deterministic command accepts the fact. Email From, subject, forwarded copy, bearer link, or LLM interpretation alone never proves that commitment. The exact provider authentication mechanism remains a technical design question.
- **Historical original preserved:** Current authenticated party plus single-use scoped request and explicit POST are required for consequential acceptance; From or bearer link alone is not enough.
- Source evidence: `E43, E06, E47, T01, T09`.
- Existing target path/owner: `plasticos_logistics confirmation command; native authenticated portal/mail capabilities`.
- Proposed tests: AC-V11, AC-V12, AC-V13, AC-V14, AC-V84, AC-UI06, AC-UI08, AC-UI09, AC-UI12; **NOT RUN**.

### BRS-02-R012: Rules-first interpretation then deterministic fact acceptance

- Requirement: `LR-012`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Separate provider transport and inbound message from extracted candidate facts, validated accepted facts and canonical state transitions. Parse standardized replies deterministically; use a narrowly scoped LLM only for free-form/complex mail extraction into typed candidate evidence. Odoo-owned validators verify provenance, identity, currentness and allowed transitions before any action. Missing/contradictory facts trigger an automatic clarification or recorded exception, not guessed acceptance.
- **Historical original preserved:** Queued/sent/received/accepted/fulfilled are separate; only typed validated evidence may affect the canonical milestone.
- Source evidence: `E28, E36, E46, T01, T03`.
- Existing target path/owner: `plasticos_logistics confirmation command`.
- Proposed tests: AC-V10, AC-V17, AC-V35, AC-V85, AC-UI07, AC-UI08, AC-UI09, AC-UI10, AC-UI11; **NOT RUN**.

### BRS-02-R013: Stable business identity independent of payload hash

- Requirement: `LR-013`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Unique company/load/purpose/party/revision/touch key controls operation; payload fingerprint detects drift but cannot mint a duplicate by itself.
- **Historical original preserved:** Unique company/load/purpose/party/revision/touch key controls operation; payload fingerprint detects drift but cannot mint a duplicate by itself.
- Source evidence: `E37, E38, E40, T01, T09`.
- Existing target path/owner: `plasticos_logistics confirmation/send command + native Mail`.
- Proposed tests: AC-V15, AC-V48, AC-V49; **NOT RUN**.

### BRS-02-R014: Stale, forwarded and contradictory replies

- Requirement: `LR-014`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Validate exact request, current revision and party; duplicates are no-ops, conflicts retained, cancelled requests never revived.
- **Historical original preserved:** Validate exact request, current revision and party; duplicates are no-ops, conflicts retained, cancelled requests never revived.
- Source evidence: `E37, E38, E46, E06, T01, T09`.
- Existing target path/owner: `plasticos_logistics confirmation command`.
- Proposed tests: AC-V13, AC-V15, AC-V16, AC-V19, AC-UI10, AC-UI12; **NOT RUN**.

### BRS-02-R015: Linda autonomous routine coordination within distinct commercial boundaries

- Requirement: `LR-015`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Linda autonomously performs eligible Odoo PO/SO generation and templated sends, supplier/buyer/carrier coordination, rule-based response handling, permitted logistical updates, reminders and clarifications without per-action human approval. Existing separately owned commercial rate/carrier award, confidentiality, security and financial controls remain distinct; notification of an exception is not a default approval gate.
- **Historical original preserved:** Routine actor may record validated facts and advance allowed noncommercial transitions; may not select or approve carrier/rate.
- Source evidence: `E31, E46, E01, T01, T10, T24`.
- Existing target path/owner: `plasticos_logistics guarded actions; plasticos_security_base role owner`.
- Proposed tests: AC-V08, AC-V21, AC-V80, AC-UI05, AC-UI13; **NOT RUN**.

### BRS-02-R062: Bounded LLM may interpret; deterministic rules alone govern action

- Requirement: `LR-062`. Effective disposition: `MERGE_WITH_EXISTING_AND_HARDEN`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** A scoped LLM may extract structured candidate meaning from free-form inbound email only when deterministic parsing is insufficient. Its candidate facts and confidence are never business authority and cannot directly send, change load state, select carrier/rate, satisfy document proof or invoke tools. Deterministic verification of identity, request version, explicit response and all business prerequisites alone governs the next permitted Odoo action. OCR confidence likewise never proves a physical event.
- **Historical original preserved:** No LLM/probabilistic intent or OCR confidence advances routine workflow. Ambiguous input stays exception evidence.
- Source evidence: `E36, E41, E49, E46, T37, T01`.
- Existing target path/owner: `plasticos_logistics Mail interpretation and deterministic fact-acceptance actions`.
- Proposed tests: AC-V10, AC-V67, AC-V78, AC-UI07, AC-UI08, AC-UI10, AC-UI11; **NOT RUN**.
- Donor-era disposition retained for provenance: `REJECT`. This is not an outstanding approval gate.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

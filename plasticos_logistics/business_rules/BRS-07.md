# BRS-07: Delivery, documents and operational closeout

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_documents_native + plasticos_documents + plasticos_logistics`.

## Responsibility boundary

Validated receiver/document truth and separate transaction close.

## Evidence-traced candidate rules

### BRS-07-R045: Receiver evidence and destination validation

- Requirement: `LR-045`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Carrier-reported delivered is an attributed claim; verified delivery requires correct receiver/destination evidence and unresolved dispute handling.
- **Historical original preserved:** Carrier-reported delivered is an attributed claim; verified delivery requires correct receiver/destination evidence and unresolved dispute handling.
- Source evidence: `E28, E41, E49, T01, T04, T03`.
- Existing target path/owner: `load delivery action and existing receiver/document owners`.
- Proposed tests: AC-V60, AC-V61, AC-V68; **NOT RUN**.

### BRS-07-R046: Store once, preserve original and role views

- Requirement: `LR-046`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Native Documents owns file UX, existing attachment and mirror stay linked; supplier/carrier/buyer views use tags, not duplicate physical files.
- **Historical original preserved:** Native Documents owns file UX, existing attachment and mirror stay linked; supplier/carrier/buyer views use tags, not duplicate physical files.
- Source evidence: `E08, E49, E41, T05, T07`.
- Existing target path/owner: `plasticos_documents_native plus existing legacy compliance mirror`.
- Proposed tests: AC-V64, AC-V66, AC-V71; **NOT RUN**.

### BRS-07-R047: Deterministic association before classification

- Requirement: `LR-047`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Bind submitted attachment through authenticated request and exact company/load; ambiguous PO-only/domain matches go to review.
- **Historical original preserved:** Bind submitted attachment through authenticated request and exact company/load; ambiguous PO-only/domain matches go to review.
- Source evidence: `E08, E49, E06, T05, T07`.
- Existing target path/owner: `existing document/mail intake seam`.
- Proposed tests: AC-V88, AC-V83, AC-V63; **NOT RUN**.

### BRS-07-R048: Current verified BOL/POD, not checkboxes

- Requirement: `LR-048`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Operational delivery/closeout needs attributable evidence for this exact current load, destination, delivery event and document revision. A current signed or otherwise verified BOL/POD is sufficient when required; a distinctly authenticated receiver delivery acknowledgment may also establish the delivery fact where its format is permitted. A handwritten or unsigned document is not rejected solely for lacking a signature, but its contents must still be attributable, coherent and verified. A hash, OCR score, checkbox, file count, forwarded text or carrier assertion alone cannot impersonate receiver acceptance. All separately required load/facility compliance documents must be current and verified before unattended operational close; incomplete/uncertain evidence is archived with an exception. Financial transaction close remains governed by its own accounting/compliance actions.
- **Historical original preserved:** Required current signed/verified evidence for this load must exist before close; eligibility separate from file count/content hash.
- Source evidence: `E38, E41, E28, T01, T05, T06, T08`.
- Existing target path/owner: `plasticos_documents/models/load_docs_bridge.py close guard; load action`.
- Proposed tests: AC-V62, AC-V63, AC-V65, AC-V67, AC-BR07; **NOT RUN**.
- Source-policy reconciliation: `PR-05` in `policy_resolution.json`.

### BRS-07-R049: Native-to-legacy proof synchronization

- Requirement: `LR-049`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** The compliance mirror must track exact current attachment, tag, source link and verification/supersession; not only a stale verification flag.
- **Historical original preserved:** The compliance mirror must track exact current attachment, tag, source link and verification/supersession; not only a stale verification flag.
- Source evidence: `E49, E38, E08, T07, T05, T08`.
- Existing target path/owner: `plasticos_documents_native/models/document_sync.py`.
- Proposed tests: AC-V64, AC-V63, AC-V66; **NOT RUN**.

### BRS-07-R050: Hash and supersession as integrity, not authority

- Requirement: `LR-050`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Hash binds exact bytes/version; corrected evidence is a successor; acceptance of old bytes cannot seal a new file.
- **Historical original preserved:** Hash binds exact bytes/version; corrected evidence is a successor; acceptance of old bytes cannot seal a new file.
- Source evidence: `E38, E41, E37, T05, T07`.
- Existing target path/owner: `existing document versioning and verification owner`.
- Proposed tests: AC-V65, AC-V66, AC-V67; **NOT RUN**.

### BRS-07-R051: Party-specific missing-document SLA and escalation

- Requirement: `LR-051`. Effective disposition: `SOURCE_POLICY_RESOLVED_RUNTIME_CONFIG_DEFERRED`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** For each actually required outstanding document, Linda tracks the accountable party and milestone in business days (Monday-Friday): supplier document checks begin one business day after pickup and escalate after five business days after pickup; carrier checks begin two business days after pickup and escalate after six; buyer checks begin one business day after delivery and escalate after five after delivery. Once a party-specific check is due, send at most one missing-doc reminder per day through the configured approved Gmail channel, including exact transaction/reference and missing types. An escalation creates one native internal activity for the correct responsible role; it is not a request for new routine approval and not a blanket broadcast. Suppress cleared, inapplicable, canceled and superseded obligations. Preserve source-required proof gates without using receipt/file hashing alone to mark operational close. Historical alternate SMS and docs@ inbox are not additional configured transport obligations under the later chosen Google Workspace logistics2 mailbox.
- **Historical original preserved:** Request only actually required missing docs from responsible party; keep internal escalations on existing activity surface.
- Source evidence: `E08, E49, E41, T05, T16, T04`.
- Existing target path/owner: `existing document rules/cron and native activities`.
- Proposed tests: AC-V71, AC-V62, AC-BR08, AC-BR09, AC-BR10; **NOT RUN**.
- Source-policy reconciliation: `PR-06` in `policy_resolution.json`.
- Donor-era disposition retained for provenance: `CONFIGURE_AFTER_APPROVAL`. This is not an outstanding approval gate.

### BRS-07-R052: Quantities, discrepancies and original unit evidence

- Requirement: `LR-052`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Separate expected/actual/source weights, normalize through existing units and block disputes; logistics does not settle financial variance.
- **Historical original preserved:** Separate expected/actual/source weights, normalize through existing units and block disputes; logistics does not settle financial variance.
- Source evidence: `E06, E41, E28, T04, T05`.
- Existing target path/owner: `existing transaction weight authority and document evidence`.
- Proposed tests: AC-V68, AC-V61; **NOT RUN**.

### BRS-07-R053: Verified downstream synchronization

- Requirement: `LR-053`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Idempotently publish verified dispatch/pickup/delivery facts to exact linked records; stock completion uses native business actions and valid route quantities.
- **Historical original preserved:** Idempotently publish verified dispatch/pickup/delivery facts to exact linked records; stock completion uses native business actions and valid route quantities.
- Source evidence: `E12, E28, E22, T04, T03, T13, T38`.
- Existing target path/owner: `existing transaction/picking bridges and load owner`.
- Proposed tests: AC-V69, AC-V03, AC-V56; **NOT RUN**.

### BRS-07-R054: Financial close is a separate gate

- Requirement: `LR-054`. Effective disposition: `PRESERVE_EXISTING`. Admission: `EXISTING_BEHAVIOR_CLAIM_NOT_RUNTIME_PROVEN`.
- **Effective candidate rule:** Logistics close publishes evidence; posted financial docs, manager authority and current compliance/margin checks remain mandatory.
- **Historical original preserved:** Logistics close publishes evidence; posted financial docs, manager authority and current compliance/margin checks remain mandatory.
- Source evidence: `E28, E38, E41, E46, T04, T08`.
- Existing target path/owner: `plasticos_transaction existing action_close and accounting owners`.
- Proposed tests: AC-V70, AC-V61; **NOT RUN**.

### BRS-07-R055: Truthful operational metrics

- Requirement: `LR-055`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Measure event time vs accepted baseline, acknowledgment latency, overdue milestones and human exceptions; no fabricated KPI percentages.
- **Historical original preserved:** Measure event time vs accepted baseline, acknowledgment latency, overdue milestones and human exceptions; no fabricated KPI percentages.
- Source evidence: `E41, E49, E25, T01, T04, T29`.
- Existing target path/owner: `existing logistics dashboard/evidence projection`.
- Proposed tests: AC-V72, AC-V57; **NOT RUN**.

### BRS-07-R056: Legacy assertions are not confirmed events

- Requirement: `LR-056`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Classify existing fields as verified evidence, legacy assertion, contradictory or unassociated; automation activates only reviewed eligible cohort.
- **Historical original preserved:** Classify existing fields as verified evidence, legacy assertion, contradictory or unassociated; automation activates only reviewed eligible cohort.
- Source evidence: `E21, E06, E48, T01, T04, T05`.
- Existing target path/owner: `affected existing models migration/adoption owner`.
- Proposed tests: AC-V73, AC-V62, AC-V05; **NOT RUN**.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

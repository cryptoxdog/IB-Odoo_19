# BRS-05: Dispatch, messages and confidentiality

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_logistics + plasticos_automation`.

## Responsibility boundary

One guarded sender and party-scoped documents.

## Evidence-traced candidate rules

### BRS-05-R029: One guarded dispatch authority

- Requirement: `LR-029`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** All send/release paths call the canonical load checks; stock assigned is not a carrier instruction and no independent dispatch state can grant permission.
- **Historical original preserved:** All send/release paths call the canonical load checks; stock assigned is not a carrier instruction and no independent dispatch state can grant permission.
- Source evidence: `E02, E18, E47, E32, T01, T03, T15`.
- Existing target path/owner: `plasticos_logistics/models/load.py; plasticos_automation/data/workflow_automations.xml`.
- Proposed tests: AC-V06, AC-V07, AC-V86; **NOT RUN**.

### BRS-05-R030: Three documents, current version, then acknowledgment

- Requirement: `LR-030`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** The carrier packet contains exactly the three separately rendered current Odoo PDF documents: Pickup Bill of Lading (pickup BOL), Delivery Bill of Lading (delivery BOL) and Delivery Order (DO). Only the permitted carrier receives the complete current-revision packet, after valid READY, appointments when required and authorized booking. Sending or Gmail provider acceptance records transport status only. Attributable carrier acknowledgment of all three same-version attachments is a separate mandatory condition before the load may transition to Dispatched; stale, missing, partial or mismatched attachments fail closed.
- **Historical original preserved:** A fully scheduled/booked load can send its packet in Scheduled; exact packet receipt gates Dispatched. Sending and releasing are separate facts.
- Source evidence: `E44, E40, E28, E33, T01, T25, T26, T27, T28`.
- Existing target path/owner: `existing load packet/report/Mail owners`.
- Proposed tests: AC-V41, AC-V42, AC-V53, AC-BR05, AC-BR06; **NOT RUN**.
- Source-policy reconciliation: `PR-04` in `policy_resolution.json`.

### BRS-05-R031: Party-specific document and message audiences

- Requirement: `LR-031`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Supplier sees pickup-side allowed content, buyer delivery-side content, carrier execution itinerary. DO and combined packet only to carrier.
- **Historical original preserved:** Supplier sees pickup-side allowed content, buyer delivery-side content, carrier execution itinerary. DO and combined packet only to carrier.
- Source evidence: `E02, E03, E29, E44, E35, T25, T26, T27, T28`.
- Existing target path/owner: `existing templates/report generation and Mail guard`.
- Proposed tests: AC-V43, AC-V45, AC-UI03; **NOT RUN**.

### BRS-05-R032: No Sales CC on buyer SO; no archival CC

- Requirement: `LR-032`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Apply literal no-Sales-CC on buyer/SO and no buyer/supplier CC on trucker mail; archive in Odoo.
- **Historical original preserved:** Apply literal no-Sales-CC on buyer/SO and no buyer/supplier CC on trucker mail; archive in Odoo.
- Source evidence: `E03, E02, T25, T01`.
- Existing target path/owner: `plasticos_automation email templates; load Mail/composer guard`.
- Proposed tests: AC-V44, AC-V43, AC-UI03; **NOT RUN**.

### BRS-05-R033: No secret leakage through shared notes or chatter

- Requirement: `LR-033`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Exclude shared internal notes and other-side identity from party documents; native followers must not relay cross-party replies.
- **Historical original preserved:** Exclude shared internal notes and other-side identity from party documents; native followers must not relay cross-party replies.
- Source evidence: `E29, E35, E49, T26, T27, T25, T01`.
- Existing target path/owner: `report/template owners and party-scoped Mail records`.
- Proposed tests: AC-V45, AC-V43, AC-V13, AC-UI11; **NOT RUN**.

### BRS-05-R034: Durable queue and truthful send status

- Requirement: `LR-034`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Persist one outbound obligation and enqueue atomically; queue/sent/ack are separate; failed mail does not produce sent/release success.
- **Historical original preserved:** Persist one outbound obligation and enqueue atomically; queue/sent/ack are separate; failed mail does not produce sent/release success.
- Source evidence: `E30, E35, E37, E22, T01, T03, T25`.
- Existing target path/owner: `load send command plus native mail.mail`.
- Proposed tests: AC-V46, AC-V47, AC-V48, AC-UI04, AC-UI14; **NOT RUN**.

### BRS-05-R035: Uncertain SMTP outcome is not safely retryable by default

- Requirement: `LR-035`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** After post-accept timeout/crash, reconcile provider/native message identity or raise an exception; no exactly-once external-delivery promise.
- **Historical original preserved:** After post-accept timeout/crash, reconcile provider/native message identity or raise an exception; no exactly-once external-delivery promise.
- Source evidence: `E37, E35, E30, T01, T16`.
- Existing target path/owner: `native Mail reconciliation and load activity owner`.
- Proposed tests: AC-V47, AC-V49, AC-V77, AC-UI14; **NOT RUN**.

### BRS-05-R036: Currency, time zone and actual fields rendered correctly

- Requirement: `LR-036`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Show approved currency and explicit local window, and label planned versus actual checkpoint honestly.
- **Historical original preserved:** Show approved currency and explicit local window, and label planned versus actual checkpoint honestly.
- Source evidence: `E06, E46, E40, T25, T28, T29`.
- Existing target path/owner: `existing report/templates/load UX`.
- Proposed tests: AC-V40, AC-V27, AC-V57; **NOT RUN**.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

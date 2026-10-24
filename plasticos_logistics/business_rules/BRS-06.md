# BRS-06: Physical checkpoints and follow-ups

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_logistics + plasticos_automation`.

## Responsibility boundary

Physical evidence and event-specific escalation.

## Evidence-traced candidate rules

### BRS-06-R037: One state-dependent milestone clock

- Requirement: `LR-037`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** One evaluation owner schedules due readiness/slot/ack/checkpoint/doc obligations; other models project it rather than independently chase.
- **Historical original preserved:** One evaluation owner schedules due readiness/slot/ack/checkpoint/doc obligations; other models project it rather than independently chase.
- Source evidence: `E39, E40, E14, E45, T16, T17, T18, T19, T20`.
- Existing target path/owner: `existing logistics escalation/scheduler owner`.
- Proposed tests: AC-V20, AC-V53, AC-V59, AC-V75; **NOT RUN**.

### BRS-06-R038: Race-safe due evaluation and catch-up

- Requirement: `LR-038`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Under transaction lock re-read current request/status; due<=now, bounded fair batches and durable touch keys.
- **Historical original preserved:** Under transaction lock re-read current request/status; due<=now, bounded fair batches and durable touch keys.
- Source evidence: `E37, E39, E40, E45, T16, T20`.
- Existing target path/owner: `existing logistics cron + guarded command`.
- Proposed tests: AC-V49, AC-V50, AC-V51, AC-V87; **NOT RUN**.

### BRS-06-R039: Reconcile existing distinct cadence obligations, no invented schedule

- Requirement: `LR-039`. Effective disposition: `SOURCE_POLICY_RESOLVED_RUNTIME_CONFIG_DEFERRED`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** One Odoo-owned reminder schedule maintains distinct obligations and stops on current acknowledgment, cancellation or supersession: (1) not-yet-READY shipper status every Monday morning with PO and shipper; (2) separately due supplier confirmation follow-up after 24 hours, at most one per day, with escalation after three unanswered follow-ups, and buyer slot follow-up on the documented 24-hour/48-hour buyer thresholds; (3) carrier packet acknowledgment reminder at T+2 hours and carrier/ops escalation at T+4 hours; (4) for still-unacknowledged carrier dispatch, broker-facing pre-pickup touch D-1 09:00 and pickup-day touch D 08:00 origin-local, plus DISTINCT ops-only D-1 13:00 digest and D 07:00 alert origin-local. These different audiences/touch types must not be collapsed into an apparent time contradiction or duplicated by multiple crons. Broker-facing routine messages honor 22:00-06:00 broker-local quiet hours from the selected dispatch templates; internal urgent exceptions can remain actionable. Source-defined timing is binding intent; precise Monday clock hour and job wiring are technical configuration.
- **Historical original preserved:** Preserve approved current limits until a single selected cadence is admitted; Monday status, pre-pickup and acknowledgment touch types are distinct.
- Source evidence: `E39, E40, E43, E49, T16, T17, T18, T19`.
- Existing target path/owner: `business policy owner + existing cron configuration`.
- Proposed tests: AC-V20, AC-V50, AC-V52, AC-BR04, AC-BR05; **NOT RUN**.
- Source-policy reconciliation: `PR-03` in `policy_resolution.json`.
- Donor-era disposition retained for provenance: `CONFIGURE_AFTER_APPROVAL`. This is not an outstanding approval gate.

### BRS-06-R040: Actionable, deduplicated human exceptions

- Requirement: `LR-040`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** One unresolved activity per load/milestone/reason/revision names blocked step, owner, source, deadline and allowed resolution.
- **Historical original preserved:** One unresolved activity per load/milestone/reason/revision names blocked step, owner, source, deadline and allowed resolution.
- Source evidence: `E39, E49, E31, T17, T18, T01`.
- Existing target path/owner: `native mail.activity and responsible business owner`.
- Proposed tests: AC-V59, AC-V71, AC-V46; **NOT RUN**.

### BRS-06-R041: Checkpoint vocabulary without new load states

- Requirement: `LR-041`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Driver assignment, en-route, arrival, pickup, departure, delay and destination arrival are attributed checkpoints; picked_up represents in-transit at load level.
- **Historical original preserved:** Driver assignment, en-route, arrival, pickup, departure, delay and destination arrival are attributed checkpoints; picked_up represents in-transit at load level.
- Source evidence: `E21, E25, E42, T01, T02, T04`.
- Existing target path/owner: `plasticos_logistics checkpoint handler; transaction bridge`.
- Proposed tests: AC-V54, AC-V55, AC-V57; **NOT RUN**.

### BRS-06-R042: Pickup proof does not finish delivery picking

- Requirement: `LR-042`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Accept pickup only with exact current load/facility/actor evidence; update actual pickup and in-transit projection once.
- **Historical original preserved:** Accept pickup only with exact current load/facility/actor evidence; update actual pickup and in-transit projection once.
- Source evidence: `E21, E12, E43, T01, T04, T03`.
- Existing target path/owner: `load checkpoint action and native stock/transaction bridge`.
- Proposed tests: AC-V54, AC-V69; **NOT RUN**.

### BRS-06-R043: Out-of-order and stale event handling

- Requirement: `LR-043`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Retain late evidence, separate physical and receive times; hold missing predecessor; never overwrite delivered with an older delay.
- **Historical original preserved:** Retain late evidence, separate physical and receive times; hold missing predecessor; never overwrite delivered with an older delay.
- Source evidence: `E21, E37, E46, T01, T02, T04`.
- Existing target path/owner: `load checkpoint command`.
- Proposed tests: AC-V55, AC-V56, AC-V58; **NOT RUN**.

### BRS-06-R044: No response after pickup is a monitored exception

- Requirement: `LR-044`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Every active load has next expected milestone and due evidence; lost contact/overdue arrival creates an owned exception.
- **Historical original preserved:** Every active load has next expected milestone and due evidence; lost contact/overdue arrival creates an owned exception.
- Source evidence: `E25, E39, E49, T20, T19`.
- Existing target path/owner: `existing logistics scheduler`.
- Proposed tests: AC-V53, AC-V59, AC-V51; **NOT RUN**.

### BRS-06-R068: Minimal operator-facing exception and next action

- Requirement: `LR-068`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Show last verified checkpoint, next required fact, owner and blocked reason; routine email threads are not the work queue.
- **Historical original preserved:** Show last verified checkpoint, next required fact, owner and blocked reason; routine email threads are not the work queue.
- Source evidence: `E25, E31, E46, T01, T19, T04`.
- Existing target path/owner: `existing Odoo load/activity/dashboard UI`.
- Proposed tests: AC-V57, AC-V59, AC-V72; **NOT RUN**.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

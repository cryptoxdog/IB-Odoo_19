# BRS-03: Facility terms and appointments

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_facility_profile + plasticos_logistics`.

## Responsibility boundary

Pickup and delivery independently determined and committed.

## Evidence-traced candidate rules

### BRS-03-R016: Per-facility unknown-safe dock rules

- Requirement: `LR-016`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Determine pickup and delivery dock requirements independently; blank/default/unverified differs from confirmed FCFS.
- **Historical original preserved:** Determine pickup and delivery dock requirements independently; blank/default/unverified differs from confirmed FCFS.
- Source evidence: `E43, E21, E17, T22, T21, T01`.
- Existing target path/owner: `plasticos_facility_profile actual facility fields; plasticos_logistics load`.
- Proposed tests: AC-V22, AC-V23, AC-V25; **NOT RUN**.

### BRS-03-R017: Delivery slot constrains pickup scheduling

- Requirement: `LR-017`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** When destination requires appointment, obtain accepted available slot before final pickup commitment and coordinate feasible pickup around it.
- **Historical original preserved:** When destination requires appointment, obtain accepted available slot before final pickup commitment and coordinate feasible pickup around it.
- Source evidence: `E43, E44, E28, T01, T21`.
- Existing target path/owner: `plasticos_logistics scheduling command`.
- Proposed tests: AC-V24, AC-V26, AC-V28; **NOT RUN**.

### BRS-03-R018: Proposal/request/acceptance/cancellation distinction

- Requirement: `LR-018`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Keep both-party proposals and explicit accepted slot/reference/source. appointment_requested remains a request indicator only.
- **Historical original preserved:** Keep both-party proposals and explicit accepted slot/reference/source. appointment_requested remains a request indicator only.
- Source evidence: `E21, E28, E43, T03, T21`.
- Existing target path/owner: `plasticos_logistics confirmation records; existing SO bridge projection`.
- Proposed tests: AC-V26, AC-V29, AC-V81; **NOT RUN**.

### BRS-03-R019: FCFS removes only appointment gate

- Requirement: `LR-019`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Confirmed FCFS allows arrival within approved hours but does not prove material ready, immediate loading, truck acceptance or rate authority.
- **Historical original preserved:** Confirmed FCFS allows arrival within approved hours but does not prove material ready, immediate loading, truck acceptance or rate authority.
- Source evidence: `E17, E26, E43, T01, T22`.
- Existing target path/owner: `plasticos_logistics scheduling prerequisites`.
- Proposed tests: AC-V18, AC-V23, AC-V32; **NOT RUN**.

### BRS-03-R020: Facility time zones, hours and lead time

- Requirement: `LR-020`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Persist UTC instants and explicit facility-local windows; unknown hours/time zone require a question to the facility or exception.
- **Historical original preserved:** Persist UTC instants and explicit facility-local windows; unknown hours/time zone require a question to the facility or exception.
- Source evidence: `E21, E39, E43, T01, T22`.
- Existing target path/owner: `facility requirements owner; plasticos_logistics scheduling`.
- Proposed tests: AC-V27, AC-V28, AC-V52; **NOT RUN**.

### BRS-03-R021: No invented dock-capacity subsystem

- Requirement: `LR-021`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Validate exact exclusive slot/resource only where actually known; two loads at a facility need not be an overlap violation.
- **Historical original preserved:** Validate exact exclusive slot/resource only where actually known; two loads at a facility need not be an overlap violation.
- Source evidence: `E21, E43, T01, T22`.
- Existing target path/owner: `plasticos_logistics scheduling`.
- Proposed tests: AC-V26, AC-V30; **NOT RUN**.

### BRS-03-R022: Amendment invalidates dependencies

- Requirement: `LR-022`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Material accepted slot/readiness changes invalidate only dependent current requests and require renewed commitments; history remains.
- **Historical original preserved:** Material accepted slot/readiness changes invalidate only dependent current requests and require renewed commitments; history remains.
- Source evidence: `E38, E46, E43, T01, T12`.
- Existing target path/owner: `plasticos_logistics recovery/confirmation command`.
- Proposed tests: AC-V16, AC-V29, AC-V38, AC-V82; **NOT RUN**.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

# BRS-04: Freight policy and carrier booking

**Status:** Candidate operating specification, not registered Odoo repository authority.
**Canonical candidate machine rule source:** `business_rules/rules.json`.
**Existing code/domain owner:** `plasticos_logistics`.

## Responsibility boundary

SAL/rate quote commercial policy and distinct booking acceptance.

## Evidence-traced candidate rules

### BRS-04-R023: SAL and canonical executed history

- Requirement: `LR-023`. Effective disposition: `PRESERVE_EXISTING`. Admission: `EXISTING_BEHAVIOR_CLAIM_NOT_RUNTIME_PROVEN`.
- **Effective candidate rule:** Preserve exact elapsed-time and physical-context matching; reuse prior confirmed/booked rate, not actual invoice variance.
- **Historical original preserved:** Preserve exact elapsed-time and physical-context matching; reuse prior confirmed/booked rate, not actual invoice variance.
- Source evidence: `E46, E47, E34, T11, T12, T01, T33`.
- Existing target path/owner: `existing SAL/context/rate owners`.
- Proposed tests: AC-V31, AC-V38, AC-V79, AC-UI13; **NOT RUN**.

### BRS-04-R024: Estimate/recommendation/award/actual remain distinct

- Requirement: `LR-024`. Effective disposition: `PRESERVE_EXISTING`. Admission: `EXISTING_BEHAVIOR_CLAIM_NOT_RUNTIME_PROVEN`.
- **Effective candidate rule:** Nonbinding estimate and ranked recommendation cannot commit rate/carrier; actuals remain executed outcome.
- **Historical original preserved:** Nonbinding estimate and ranked recommendation cannot commit rate/carrier; actuals remain executed outcome.
- Source evidence: `E46, E47, E34, T09, T10, T37`.
- Existing target path/owner: `existing local estimation, quote and actual-cost owners`.
- Proposed tests: AC-V31, AC-V34, AC-V39, AC-V40, AC-V79, AC-UI13; **NOT RUN**.

### BRS-04-R025: Manual-only RFQ after SAL miss

- Requirement: `LR-025`. Effective disposition: `PRESERVE_EXISTING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** After a genuine current SAL miss, Linda may record and surface the missing commercial rate and coordinate informational follow-up, but no freight rate/carrier award or new outbound carrier RFQ is inferred from autonomous routine logistics authority. The pre-existing freight RFQ episode and any solicitation are manual-only until a separately authorized commercial decision supplies exact current terms. Previously approved/booked valid rate/carrier records can be used for routine follow-through without a redundant Linda human send approval.
- **Historical original preserved:** Maintain deliberate manual RFQ and operator decision boundary; surfaced requirements are not permission for automated solicitation.
- Source evidence: `E46, E47, E13, T01, T09, T37`.
- Existing target path/owner: `plasticos_logistics existing freight request action`.
- Proposed tests: AC-V33, AC-V34, AC-BR03; **NOT RUN**.
- Source-policy reconciliation: `PR-02` in `policy_resolution.json`.

### BRS-04-R026: Immutable market response and recipient evidence

- Requirement: `LR-026`. Effective disposition: `PRESERVE_EXISTING`. Admission: `EXISTING_BEHAVIOR_CLAIM_NOT_RUNTIME_PROVEN`.
- **Effective candidate rule:** Retain losing, late, declined and superseding quote facts without fabricated send evidence or zero-price declines.
- **Historical original preserved:** Retain losing, late, declined and superseding quote facts without fabricated send evidence or zero-price declines.
- Source evidence: `E46, E47, E06, T09, T10, T33`.
- Existing target path/owner: `plasticos_logistics/models/freight_quote.py`.
- Proposed tests: AC-V39, AC-V15, AC-V79; **NOT RUN**.

### BRS-04-R027: Carrier commitment beyond approved rate

- Requirement: `LR-027`. Effective disposition: `NATIVE_REIMPLEMENTATION`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** Linda may autonomously coordinate and dispatch against the exact already-authorized carrier, confirmed freight rate/currency, permitted equipment and validated facility windows. Booking acceptance must be attributable to that carrier and current request; a ranked quote, stale SAL context or estimate is not an award. No additional human prompt is required merely for Linda to execute routine booking or document sends once the commercial authorization exists.
- **Historical original preserved:** Book only exact approved carrier/rate/currency/equipment/windows/current context with attributable carrier acceptance.
- Source evidence: `E28, E21, E43, T01, T09`.
- Existing target path/owner: `plasticos_logistics booking confirmation command`.
- Proposed tests: AC-V32, AC-V35, AC-V36, AC-BR03; **NOT RUN**.
- Source-policy reconciliation: `PR-02` in `policy_resolution.json`.

### BRS-04-R028: Unavailable carrier routes commercial exception

- Requirement: `LR-028`. Effective disposition: `MERGE_WITH_HARDENING`. Admission: `CANDIDATE_REQUIRES_TARGET_OWNER_REVIEW`.
- **Effective candidate rule:** A carrier decline, failed capacity commitment or material freight-context change invalidates affected booking/dispatch commitments. Linda preserves the refusal and old rate evidence, seeks permitted factual clarification autonomously, and raises one commercial re-resolution exception for the existing decision owner. Linda does not select the next-best carrier, change the rate or reroute an unapproved substitute by itself; after the resulting commercial decision, routine coordination resumes automatically.
- **Historical original preserved:** Carrier decline/unavailability holds release; operator chooses permitted re-resolution. Preserve old evidence and document amendments.
- Source evidence: `E22, E24, E30, E31, E47, T01, T09`.
- Existing target path/owner: `existing freight recovery and operator owner`.
- Proposed tests: AC-V37, AC-V38, AC-V82, AC-BR03; **NOT RUN**.
- Source-policy reconciliation: `PR-02` in `policy_resolution.json`.

### BRS-04-R067: Retain useful working freight; do not repeat predecessor campaign

- Requirement: `LR-067`. Effective disposition: `PRESERVE_EXISTING`. Admission: `EXISTING_BEHAVIOR_CLAIM_NOT_RUNTIME_PROVEN`.
- **Effective candidate rule:** Current implementation outranks older donor baseline; retain already-satisfied interfaces and regressions.
- **Historical original preserved:** Current implementation outranks older donor baseline; retain already-satisfied interfaces and regressions.
- Source evidence: `E46, E47, E48, T09, T10, T11, T12, T33`.
- Existing target path/owner: `current plasticos_logistics freight spine`.
- Proposed tests: AC-V79, AC-V78, AC-V90; **NOT RUN**.

## Admission and evolution

Business policy is source-resolved for the active candidate rules. The original donor assertions remain unchanged in `campaign.json` and `source_inputs/`.
All seven BRS families are candidate concern indices, not newly admitted repository rule authorities. Technical configuration, implementation, runtime testing, publication and live sends remain separately gated.

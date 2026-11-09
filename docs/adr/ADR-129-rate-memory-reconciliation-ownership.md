# ADR-129: Rate-memory reconciliation ownership

**Status:** Accepted
**Decision date:** 2026-11-08
**Applies to:** `plasticos.rate.memory.reconciliation` in `plasticos_logistics`
**Decision owner:** Operator, approving [issue #182](https://github.com/cryptoxdog/IB-Odoo_19/issues/182)
**Implementation owner:** `plasticos_logistics`

## Context

Legacy rate-memory rows have no company. Reconciliation classifies each row against canonical loads. The reconciliation model required `company_id` and defaulted it to the operator's current company. When no load company could be named, the classifier skipped the row, so the four non-exact dispositions were never stored.

An exact match does have a company: the matched load's company. A non-exact disposition does not. Recording the operator's company on that row would invent an owner the historical evidence does not have.

## Decision

Ownership follows the historical evidence, not the company of the person running reconciliation.

| Disposition | `company_id` | `canonical_load_id` | Who can read the row |
|---|---|---|---|
| `exact_single_match` | The source load's company | The matched canonical load | Users authorized for that company |
| `invalid_lane_key` | Explicit empty | Empty | Anyone who already has model read access |
| `no_candidate_match` | Explicit empty | Empty | Anyone who already has model read access |
| `multiple_candidate_matches` | Explicit empty | Empty | Anyone who already has model read access |
| `candidate_scan_truncated` | Explicit empty | Empty | Anyone who already has model read access |

Companyless rows are visible across companies to existing model readers. That disclosure is the approved tradeoff. It does not grant read access to anyone who lacks it, and it does not make an exact-match row visible outside its load's company.

An exact match with no determinable load company is rejected. A canonical load whose company differs from the row's company is rejected. One reconciliation row exists per legacy row. Reconciliation rows stay immutable. Access rights stay as they are. The legacy cache stays frozen.

## Consequences

`company_id` on the reconciliation model is optional and has no current-company default. The reconciliation record rule is the only rule that changes: unowned rows are readable, and company-owned rows stay inside `company_ids`. No access-control list is widened. No legacy cache row is rewritten.

## Compliance

Issue #182. Module `plasticos_logistics` models `rate_memory.py` and `freight_governance.py`, and `security/record_rules.xml` rule `rule_rate_memory_reconciliation_company`.

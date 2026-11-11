# Recursive Leverage: Changes and Dispositions

The prior v2 Revised ZIP is the exact parent. Changes are bounded to the distributed addon pack, with all source-harvest evidence bytes retained unchanged.

| ID | Verified risk | Repair and owner | Evidence |
|---|---|---|---|
| LEV-01 | Feedback copied source access and company permission logic from the advice owner, creating future policy drift. Bad IDs could raise unhandled conversion errors. | Delegate feedback source checks to `plasticos.broker.advice.service._authorized_target`; validate positive integral IDs. | New portable source-owner check; Odoo source-ID regression authored but not run. |
| LEV-02 | Approved knowledge query stopped at 150 records with no indication that applicable references might be omitted. | Fetch sentinel 151, expose `knowledge_retrieval.complete` and candidate count; incomplete search leaves `uncertainty=unresolved`. | Pure behavior tests for complete/truncated results. |
| LEV-03 | A human-approved rule could appear to be verified for the current material or buyer despite free-text scope. | Include `workflow_scope`, mark `applicability_verified=false`, explicitly require source-specific confirmation. | Pure behavior test. |
| LEV-04 | Rejection advice arbitrarily selected first among multiple approved same-code references. | Retrieve at most two, abstain with structured ambiguity instead of guessing. | Pure behavior test. |

The existing compatibility wrapper, 106 draft knowledge identities, four optional addon topology, native Odoo owners, zero automatic commerce, reviewer admission, and evidence lineages remain in place. Previous-source fixes and their proofs remain in `IMPROVEMENT_REPORT.yaml`.

**Status:** portable-source improvements validated. Real Odoo 19 Enterprise registry/ORM and optional addon installation remain unverified. No PR, merge, deploy or Production changes performed.

## Architecture alignment follow-up: current release

| Finding | Proven source defect | Corrected authoritative owner | Validation |
|---|---|---|---|
| ALN-01 | Approved knowledge was filtered by all companies available to the user, rather than the actual advice source company. Offer/match rejection lookups duplicated the same rule. | `plasticos.broker.advice.service._knowledge_company_domain`, reused by core advice and rejection wizard | Odoo company-scope tests authored, **not executed**; portable checks pass |
| ALN-02 | Saved reviewer attestation survived subsequent changes to the draft's meaning, evidence or applicability. | `plasticos.broker.knowledge.write` invalidates attestation on material draft changes and rejects a simultaneous save/attest shortcut | Odoo regression authored, **not executed** |
| ALN-03 | Colon-delimited feedback replay digest ignored legal-company context and allowed ambiguous encodings; changing format naively would duplicate old receipts. | `services/evidence.py` canonical JSON digest including company/scope; `models/feedback.py` validates exact legacy receipts during replay | 3 new portable behavior tests pass; ORM **not executed** |
| ALN-04 | Optional shadow advice swallowed database errors without a savepoint, potentially leaving the containing qualification transaction aborted. | `plasticos_broker_intelligence_web_leads/models/web_lead_advice.py` | Source/static checks pass; Odoo error-injection **not executed** |
| ALN-05 | Fractional/boolean source IDs were coerced to integer IDs, risking advice on a different record. | Core `_authorized_target` now rejects these input forms | Odoo regression authored, **not executed** |

The source adapter is the pinned `IB-Odoo_19` Staging at `d25da3236887c924c8a0164b00c1198f1804a2ea`; the commits since the previous pin changed only documentation. Open PR #471 contains Export plans only and is not an implementation authority for this addon. No other repo was inspected or modified. No changes to matcher, Offer, transaction, external Gate transport, or ERP data ownership.

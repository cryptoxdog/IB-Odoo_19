# Verification matrix, product tests all NOT_RUN

| ID | Phase | Positive scenario | Adversarial/negative scenario |
| --- | --- | --- | --- |
| P01 | PRECODE | Observe installed Odoo.sh Enterprise module version, automation, ACL, company/partner scope and row counts. | No absent runtime row/cron is inferred from manifest, XML noupdate or static grep. |
| P02 | PRECODE | Exact source/current active eight-field mapper, signed Gate->EIE response shape and origin evidence bound at same source revision. | Unrecognized/rejected packet can never become reviewable writable values. |
| P03 | PRECODE | Inventory all dynamic/explicit callers of action_inject, post_init_hook, local inference service and cron plus data class. | Legacy local consumer or hidden action is not silently disabled or dropped. |
| P04 | PRECODE | Verify current partner company semantics, shared partners, group XML IDs and admin/cron group grants. | No broad all-user mutation or unrelated cron rights silently preserved. |
| P05 | POSTCODE | Gate return recorded once and no partner fields written until individual approvals. | Both legacy auto-writeback switches set ON cannot bypass the new review action. |
| P06 | POSTCODE | Proposed values include original typed snapshot, validated target field, run/packet metadata, status and evidence class. | Missing field-specific citations are visibly not labeled as EIE-provided sources. |
| P07 | POSTCODE | User approves 2 of 3 suggestions, rejects 1, and exactly 2 permitted/empty fields are written with factual provenance. | No rejection, skip or pending line writes; raw Gate JSON button cannot bulk bypass. |
| P08 | POSTCODE | Legacy material extraction is accessible as historical read-only evidence. | engine_used=local or historical validated run cannot invoke material profile create/write via Inject. |
| P09 | POSTCODE | Direct RPC cannot mutate injected/failed/reviewed protected run fields or set terminal states without authorized action. | State plus gate_proposal in same write call is rejected; no sudo/context bypass. |
| P10 | POSTCODE | Portal/internal non-enrichment user denied write, full CRUD on runs/provenance removed, manager actions constrained. | Internal-user `base.group_user` grants cannot resurrect broader write, create or unlink. |
| P11 | POSTCODE | Distinct company and shared-partner review rules restrict visibility and act rights to permitted company/tenant. | Wrong company or mixed allowed_company_ids cannot approve/write, regardless of UI hiding. |
| P12 | POSTCODE | Target value/record company/source revision revalidated under real DB row lock before atomic write. | Concurrent partner change, renamed/remapped recipient or stale approval refuses/refreshes. |
| P13 | POSTCODE | Native existing nonempty, False, zero and missing values are classified by field schema as present/absent. | No truthiness accident treats existing confirmed zero as blank, or writes unsupported type. |
| P14 | POSTCODE | Approval writes only eight current allowlisted fields and creates exactly one source-attributed commit provenance per field. | EIE extra final_fields, comment or material_json cannot write arbitrary ORM fields. |
| P15 | POSTCODE | Missing confidence remains unknown with explicit run-level scope; KB version/packet/correlation are kept as observed. | Provenance never fabricates confidence 1.0 or field citation for packet without evidence. |
| P16 | POSTCODE | Repeated Apply Approved and same packet are idempotent with one receipt and coherent terminal/partial state. | No second write or duplicate provenance when rerun or two reviewers race. |
| P17 | POSTCODE | A no-allowlisted-field completed response is stored and classified as no-action/evidence-only. | It is neither misreported as Gate transport failure nor injected into CRM. |
| P18 | POSTCODE | Retry after Gate failure preserves truthful durable state with correct logical attempt and no local fallback. | Second cursor/rollback deadlock, cache replay under same ID and phantom completed states fail. |
| P19 | POSTCODE | Old enrichment crons are inactive/no-op in new data and actual installed DB; post-install user privileges reviewed. | Module upgrade or XML noupdate cannot resurrect retired cron, service or system_cron broad rights. |
| P20 | POSTCODE | Historical local runs/extractions/provenance and Gate packet IDs preserved with original semantics and counts. | Migration does not create approved lines for past data, delete evidence or relabel legacy run as verified. |
| P21 | POSTCODE | Partnerless CRM prospect cannot accidentally create partner or get a writable enrichment run. | No synthetic res.partner for supplier before PO and no CRM/web-lead/offer changes. |
| P22 | POSTCODE | Contact Enrichment tab and Enrichment Run display line decisions, review evidence, status and chatter with native Odoo controls. | Unapproved user cannot use direct button/RPC to bypass server authorization. |
| P23 | PREMERGE | Fresh complete source file/DAG census and registry XML/action/security reference tests pass. | No missing init, manifest XML ID, field integrity, addon cycle or module version regression. |
| P24 | PREMERGE | Odoo 19 Enterprise Docker clean install and existing-database upgrade, security/role/record rule tests pass at exact SHA. | Pure pytest or Community-only success is not an Enterprise acceptance receipt. |
| P25 | PREMERGE | Current `test_gate_enrichment_fallback`, `test_action_methods` and allowlist fixtures enforce new review-only policy. | No old test claims live auto-writeback success as required behavior and no test weakened or skipped. |
| P26 | PRERELEASE | Database+filestore backup/restore and versioned additive migration rehearsal verifies exact counts and history. | Any loss or ambiguous company assignment quarantined; no destructive start clean. |
| P27 | PRERELEASE | Isolated staging recorded-shape packet displays approve/reject choices and applies two fields with one original message. | No unapproved live EIE calls, paid work or automatic overnight dispatch. |
| P28 | PRERELEASE | Independent revision-bound code review covers all affected source/security/DB consumers and protects retired external authority. | Unaccepted new source/contract/role and unresolved P0 issue blocks merge/release. |
| P29 | POSTCODE | After each review step, audit linkage and line/run statuses match committed side effects; partial approvals truthful. | No phantom injected state when zero fields written and no stale pending decision left silently applied. |
| P30 | PRECODE | Review proposal-line versus provenance owner decision against actual ORM model/write consumers. | No new duplicate enrichment/supply model or semantic corruption of committed provenance. |
| P31 | POSTCODE | Gate contract incompatible or no-source evidence remains in secure review-only evidence, not writable by default. | No conversion of inferred/unknown values to business truth just from aggregate confidence. |
| P32 | PREMERGE | Technical-debt audit baseline/checks and M4 tombstone tests retain accuracy under changed run/refactor. | No resetting known findings or weakening Semgrep/ruff/test gates to pass. |

## Required test owners and how to interpret evidence

- `plasticos_enrichment/tests/test_gate_enrichment_fallback.py`: existing real ORM path. Rewrite old live opt-in test to assert scoped review-only behavior; preserve EIE status failure, retry attempts, and Gate unavailability tests, add no-eligible-fields and legacy Inject refusal.
- `plasticos_enrichment/tests/test_field_proposal_review.py` (new proposed): create three proposed fields for an existing partner, verify per-line decisions, precise original typed values, conflicts, evidence provenance, double-submit, user permissions, cross-company and business state.
- `plasticos_security_base/tests/test_action_methods.py`: existing `test_action_inject` expects bulk write; replace with negative bypass and explicit positive with approved line. Do not change the unrelated hundred-plus action tests.
- `tests/test_enrichment_gate_writeback.py`: source-level binding, update old brittle expectation, ensure method owner and new safe entrypoint. `tests/test_gate_match_contract.py` remains source-verified and no unnecessary Gate config change.
- Native Odoo 19 Enterprise Docker module install and upgrade: XML IDs, ACL/record rules, hooks, data migrations, registry methods, object fields, `sudo` bypass, company switching, and 1+ valid Gate-shaped packet. Pure pytest or Community-only passing is not Enterprise acceptance.
- Source- and negative-control tests for legacy crons, M4 retired local engine, accepted ADR-012's corrected effective defaults, source data retention, and no unapproved external API spend.
- Staging acceptance uses isolated fixtures/test contacts and mocked or recorded-shape Gate response; no live marketing/paid work or nightly enabling.

## Test result distinctions

**Package tests executed:** recorded under `ASSURANCE/VALIDATION_SUMMARY.md`. **Product/Enterprise tests executed:** NONE. **Actual deployed Odoo.sh/multi-node evidence:** NONE. **Independent source-owner acceptance:** NONE. Any future reviewer must present exact commands, source revision, environment, expected vs observed rows, full failure receipts and test identity.

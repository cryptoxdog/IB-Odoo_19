# 08. Required evidence, diagnosis and operator approval packet

Create the report at `docs/reports/evidence/pr301-pr303-premerge-enterprise-<date>/` in the operator checkout, with one subdirectory per tree (`m301`, `m303`, `both`) and the tested commit SHA in `SESSION_SUMMARY.md`. Copy original logs without rewriting them. Redact secrets. This folder is the remediation input. It is not permission to patch the PRs.

## Minimum report structure

`SESSION_SUMMARY.md`: all lanes attempted, exact base/head, read-only fixture preflight result, test scope and permissions, clean worktree evidence, overall validity. Followed by one report per tested PR or `Staging` baseline, plus a ranked `OPERATOR_APPROVAL_QUEUE.md`.

Each behavior row from `BEHAVIOR_CATALOG.csv` must produce one line:

| Field | Required value |
|---|---|
| `behavior_id` | Exact ID from the catalog |
| `subject`, `head_sha`, `base_sha` | PR # and immutable Git SHA actually checked out |
| `source_path`, `assertion` | Exact production seam and expected invariant |
| `pure_method`, `pure_result` | Fully qualified pytest node and actual result, or NOT_RUN |
| `orm_method`, `orm_result` | Class.method observed in Odoo test log; or NOT_COLLECTED/NOT_PROVEN |
| `module_receipt` | Existing canonical JSON receipt path, its sha256, and nonzero test count |
| `environment` | Pinned Enterprise template name, fingerprint, Odoo image ID, Postgres major, Enterprise source identity, no Community fallback |
| `source_value -> actual_value` | Redacted source/target evidence for a real mapping/fidelity comparison; otherwise NOT_PROVEN |
| `first_wrong_boundary` | Source / reader / index / crosswalk / mapping / ORM / report / replay / test-discovery / environment / unknown |
| `technical_verdict` | PASS, FAIL, BLOCKED, NOT_PROVEN, NOT_COLLECTED |
| `business_fidelity_verdict` | PASS, FAIL, NOT_PROVEN, DECISION_REQUIRED |
| `scope_assessment` | IN_SCOPE, DEPENDENCY_ONLY, OUT_OF_SCOPE, NON_IMPORT_CHANGE |
| `severity`, `confidence` | Severity S0/S1/S2/S3 plus observed/reported/inferred/unknown confidence |
| `decision_id` | Link to approval queue, if change would be needed; else NONE |

Never collapse a clean `pytest`, `make test-module`, or CI run into all-behaviors PASS. For pure checks that make no Odoo writes, the ORM column is typically `NOT_PROVEN`; for a method not discoverable by the runtime package the verdict is `NOT_COLLECTED`, never PASS. A test that passes on #303 does not establish #301's behavior. No method-level log evidence means NOT_PROVEN.

### Severity and diagnosis

- **S0, evidence-backed integrity breach:** wrong source identity, unapproved database mutation, business/fixture DB touched, data overwrites, wrong person binding, wrong amounts/dates causing meaningful inconsistency. STOP the lane and escalate.
- **S1, material import correctness:** lost ERP contact/phone/history, wrong vendor bill date/terms, duplicate order, false-success report, fabricated stock or settlement event. Hold the affected behavior and recommend one bounded corrective decision.
- **S2, recoverable coverage/contract:** omitted runtime assertion, stale fixture, unregistered Odoo tests, known source/fixture mismatch. Distinguish environment from code failure.
- **S3, advisory:** cosmetic log wording or documented deferred mapping field, with no demonstrated impact.

**Root-cause discriminator:** capture the smallest source record or synthetic fixture; pinpoint its value at reader/adapter -> index/crosswalk -> canonical mapping -> ORM field -> report -> replay. If the value is lost before ORM, fixing Odoo is unlikely to address the source seam. If persisted record is correct but test asserts a retired contract, classify TEST_DRIFT instead of production fault. If import is code-correct but violates a locked source semantics, classify WORKFLOW_REANALYSIS / DECISION_REQUIRED. Supply **both** the strongest defect interpretation and the strongest alternate cause.

Do not infer an ERP import replay guarantee from `test_upsert_lead_idempotent` or from one green Odoo transaction test. Re-execution tests need an actual identical-source replay witness on the same approved disposable clone, or must be NOT_PROVEN.

## Operator decision queue (no autonomous changes)

For each distinct material finding, provide one short decision record:

```text
DECISION ID: D-301-01
STATUS: PENDING_OPERATOR_APPROVAL
SEVERITY: S1
SOURCE: PR #301 HEAD <40hex>; method/path/log line; Enterprise fixture fingerprint
OBSERVED: <smallest concrete counterexample and measured actual value>
EXPECTED: <accepted operator rule and correct value>
FIRST WRONG BOUNDARY: <source|reader|mapper|ORM|report|replay|test>
ALTERNATE EXPLANATION TESTED: <evidence / or UNKNOWN>
MINIMUM CORRECTION PROPOSED: <one precise change class; NO EDIT performed>
REGRESSION PROOF IF APPROVED: <existing test name, or ask approval to author one>
BLAST RADIUS: <only affected module/PR and downstream behavior>
USER DECISION: [ ] approve [ ] reject [ ] defer [ ] request further evidence
```

One defect can affect several behavior rows; link them to one decision rather than opening duplicate remediation loops. Record operator-approved decision provenance later, not speculative consent. Cursor stops after reporting. If no issues, the approval queue explicitly says "No code changes requested".

## End of every run

Submit one ranked summary by severity and decision impact, then PR-specific behavior ledgers with exact method results, independently preserved source receipts and their digests, factual gaps, and the next **operator-controlled** decision. Do not commit reports, mutate PRs or attempt a fix. No new request for full tests just because a specialized pure test was green. Re-test only after operator explicitly authorizes the code/coverage change in another session.

## Published #303 handoff evidence provenance (v2.3.1)

Every PR #303 report must include `PR_HEAD_SHA=190c497...` (or newly verified exact GitHub head), `IMPLEMENTATION_BASELINE_SHA=702ebaf...`, `DOC_ONLY_DELTA_VERIFIED=yes/no`, and read status for each of five files. Preserve whether a finding is `CE_REPORTED`, `STATIC_OBSERVED`, `ENTERPRISE_VERIFIED`, or `HYPOTHESIS`. Compare #303's observed runtime results to the baseline inventory of **7 CE FAIL + 1 CE ERROR** (of **807 total CE tests**, **605 relocated CE tests**), but do not use those counts as required import-only Enterprise totals. Export all deviations, including unexpectedly passing previously red tests and the unexpected ACL unlink PASS.

Do not overwrite the actual per-test verdict with `EXPECTED_FAIL`. Use `FAIL` for a failing executed test, `PASS` for a genuinely passing executed test, and an **additional separate** `DIAGNOSTIC_EXPECTATION_MATCH=yes/no` field. `DIAGNOSTIC_COMPLETE` may pass even with known FAIL records, but `PR303_MERGE_READY` cannot. Every proposed correction remains PENDING_OPERATOR_APPROVAL.

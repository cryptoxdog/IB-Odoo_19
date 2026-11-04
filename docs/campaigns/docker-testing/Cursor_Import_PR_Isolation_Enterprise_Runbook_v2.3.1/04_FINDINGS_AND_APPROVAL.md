## v2.3.0 mandatory finding receipt

Every row of `BEHAVIOR_CATALOG.csv` requires a corresponding actual ledger entry using `08_EVIDENCE_AND_APPROVAL_PACKET.md`. `PASS` is disallowed if an expected test did not execute or lacks the corresponding business assertion. Report separate `PURE`, `ORM`, `SOURCE_REALITY` and `BUSINESS_FIDELITY` evidence dimensions, instead of turning a pure or Community run into an Enterprise business acceptance. Every proposed repair, added test, fixture adjustment, import-run change or PR movement must be marked `PENDING_OPERATOR_APPROVAL`. Cursor must never execute the proposal. Do not create GitHub issues or comments from the findings without operator approval.

# 04. One finding per behavior, and an operator-controlled decision queue

**Cursor writes evidence, not patches.** Save the report under `docs/reports/evidence/pr301-pr303-premerge-enterprise-<date>/` in the operator's checkout. Copy the runner's `.l9` receipts into that folder. Do not write the report into a test worktree before the run finishes, or the receipt will be dirty. Redact secrets. Do not commit the evidence unless the operator asks. Do not open a GitHub issue or edit a PR from the report.

## Non-negotiable verdict vocabulary

| Technical outcome | Exact meaning |
|---|---|
| `PASS` | The named *behavior's own* assertion executed at the correct SHA and passed on the authorized fixture. `module tests=100` does not independently prove that behavior. |
| `FAIL` | Actual assertion/record violated a previously accepted implementation contract; reproducible evidence and first incorrect boundary are supplied. |
| `NOT_PROVEN` | No actual named method ran, method evidence is not available, or a pure test cannot establish the ORM behavior claimed. |
| `BLOCKED` | Source identity, Enterprise fixture, collection environment, dependency or access cannot be trusted; **not** a code-failure verdict. |
| `NOT_RUN` | Intentionally deferred because the result would not add leverage or needs a separate permission. |
| `OUT_OF_SCOPE` | Logistics, unrelated product/security migration, an unauthorized live import or a code change. |

For **business meaning**, use independently: `FAITHFUL`, `DIVERGENCE`, `DECISION_REQUIRED`, `UNVERIFIED`. Do not collapse implementation correctness into historical-business faithfulness. Keep old policy decisions (draft bills, no payments, unchanged imported documents) as **policy** until the operator changes them; an agent may report business divergence but must not silently 'correct' it.

## Finding types

- **ERROR:** concrete, evidenced test failure or API/ORM exception. Must include traceback/error, affected behavior ID, exact SHA and first failing boundary.
- **WARNING:** plausible material risk, missing test coverage or unverified prerequisite, without a demonstrated defect. Never inflate to ERROR.
- **INCONSISTENCY:** same source identity or value disagrees across projection, `SourceIndex`, mapped record, result summary or replay. Include source/target comparison.
- **MISALIGNMENT:** implementation passes its own assertions, but the operator's intended ERP/CRM business workflow is not represented or a documented policy is internally contradictory. Mark `DECISION_REQUIRED`, **not an automatic patch**.

Classify high-leverage issues before minor cosmetic warnings. Use `P0 = unsafe test/source identity`, `P1 = material data loss/corruption or wrong person/accounting`, `P2 = meaningful behavioral inconsistency`, `P3 = documented low-impact coverage/diagnostics`. Severity is about business effect and proof, not the number of failed tests.

## Report record (duplicate this block for EACH behavior ID)

```text
RUN ID: <unique time/host identifier, redacted>
LANE: S / PR #301 / PR #303
PR STATE AND URL: <open/merged + browser link>
EXPECTED PR HEAD: <40-hex GitHub SHA obtained immediately before fetch>
ACTUAL TESTED HEAD: <40-hex SHA>
SOURCE WORKTREE: <separate detached absolute path>
WORKTREE CLEAN BEFORE / AFTER: <yes/no>
SOURCE MOUNT /mnt/extra-addons: <resolved worktree path; verified yes/no>
EXISTING ENTERPRISE FIXTURE: <name>  ADMITTED: <ready/not ready>
FINGERPRINT / IMAGE ID: <safe digest only; pre and post>
PARITY: ENTERPRISE ONLY
OWNED CLONE NAME / OWNER / RETIRED: <...>
TEST METHOD / COMMAND: <exact, redacted>
ACTUALLY EXECUTED: <yes/no + log marker>
MODULE TEST COUNTS: <total/failed/errors/skipped as actually reported>
EXIT CODE / RECEIPT PATH / LOG SHA256: <...>

BEHAVIOR ID: <catalog ID only: S-05 / 301-C / 303-A. 301-C means unmatched term, not the retired matrix letter>
FALSIFIABLE EXPECTATION: <one source-backed sentence + file/ADR anchor>
OBSERVED RESULT: <redacted field/source-key comparison or exact error>
TECHNICAL: PASS / FAIL / NOT_PROVEN / BLOCKED / NOT_RUN / OUT_OF_SCOPE
BUSINESS: FAITHFUL / DIVERGENCE / DECISION_REQUIRED / UNVERIFIED
FINDING TYPE: ERROR / WARNING / INCONSISTENCY / MISALIGNMENT / NONE
PRIORITY: P0 / P1 / P2 / P3 / NONE
FIRST CORRECT BOUNDARY: <source/reader/index/mapper/ORM/report/replay>
FIRST WRONG BOUNDARY: <or UNKNOWN>
EVIDENCE LOCATION: <test method, source path:line, receipt/log line>
MINIMAL DISCRIMINATING COUNTEREXAMPLE: <test input identity, redacted>
ALTERNATIVE EXPLANATION / NEXT CHEAP PROBE: <...>
CHANGE IMPLEMENTED BY CURSOR: NONE
NEXT ACTION: <proposed investigation or minimal change, UNAPPROVED>
NEEDS OPERATOR DECISION: YES / NO
```

If a behavior's test is not registered or its method never appears in actual execution evidence, **do not award PASS**. The existing guarded runner writes a *module-level* JSON receipt, not a per-method certificate. The test log plus source assertion must support the claim; where logs cannot disambiguate method execution, mark `NOT_PROVEN` rather than inventing a new runner or test instrumentation.

## Earliest wrong boundary triage

| Example | Evidence to request | Owner for proposed decision (not execution) |
|---|---|---|
| Source PayablesBatch `DueDate` never projected | Exact source schema, projection and reader values | ERP reader/projection owner |
| Projected DueDate correct, Odoo bill due date wrong | Header facts/term helper, actual ORM invoice fields | ERP transaction mapping owner |
| Approved VS person becomes a duplicate lead | Crosswalk and external identity key, last correct canonical DTO | ERP/CRM identity contract owner |
| Previously root Odoo test not executed | Addon `tests/__init__.py`, Odoo log/count, #303 patch | Test discovery/test ownership review |
| Runtime fails because Enterprise fixture missing/incompatible | Existing template name/fingerprint/mount, without rebuild | Environment owner/operator approval |
| Source says paid/posted, Odoo draft is expected by code | Source operational meaning vs accepted historical import scope | Operator workflow/architecture decision |
| Odoo invoice 'to invoice' despite source invoice identity | Source row -> order/invoice links, qty_invoiced/read-only ORM | Commercial workflow reanalysis |
| #301 and #303 both pass independently | Version/overlap of transaction module, no tested merged head | Integration decision before merge, not an automatic combine |

Known deferred source fields in [issue #299](https://github.com/cryptoxdog/IB-Odoo_19/issues/299) stay deferred. Vendor reversal pairing, zero-weight priced lines, historical posting/settlement and existing-document replay semantics are **observation-only** until operator decisions. No new tests or code without approval.

## Final report: short prioritized operator queue

Cursor delivers one rollup per independent lane (`S`, `301`, `303`) and a cross-lane observation. For each lane, include a table:

| Behavior ID | Actual assertion ran? | Technical | Business | Finding | Priority | Evidence |
|---|---|---|---|---|---|---|
| Example `301-C` | Pure: yes; ORM: not proved | NOT_PROVEN for ORM | UNVERIFIED | WARNING | P2 | path + log anchor |

Then provide at most the top 5 material proposed actions:

| Rank | PR and behavior | Precise proposed change or decision | Verified evidence | Consequence if ignored | Operator authorization |
|---|---|---|---|---|---|
| 1 | #... / ... | <description, no diff written> | <first incorrect boundary> | <specific consequence> | **PENDING_OPERATOR_APPROVAL** |

Every entry is **proposed**, not dispatched. Cursor must ask the operator which item to authorize; it must **not** start a repair plan, rebase, stage edits or pass this report automatically to a coding agent. A P0 unsafe-source or fixture failure stops test execution immediately. Independent lanes may continue only where they don't share that unsafe dependency.

## Before reporting PASS for any PR

Verify: GitHub and tested SHA same, worktree source unmodified, the correct existing Enterprise fixture ready, Docker mount bound to correct source, module receipts nonzero and clean, expected test methods genuinely observed, owned DB clones retired, no logistics-specific tests, and **zero unauthorized source/config/fixture changes**. If any condition fails, downgrade the corresponding claim to BLOCKED/NOT_PROVEN and show why.

## Final whole-system report (Phase I; future only)

After individual defects have been **separately approved, fixed by an authorized implementer, and re-tested**, add a separate integrated-commit report. Never blend its evidence with earlier per-PR receipts. Its top block must include: `APPROVED_INTEGRATION_REF`, `INTEGRATION_SHA`, all accepted PR/fix heads, proof of included content, the same canonical EE template/fingerprint, exact combined `m=...` module command, test method execution evidence, all owned-clone retirements and `SOURCE_UNCHANGED=yes`.

| Integrated gate | Technical | Business fidelity | Actual evidence or blocker |
|---|---|---|---|
| I-A source composition | PASS / FAIL / BLOCKED | n/a | Operator-approved commit and accepted PR/fix closure |
| I-B pure cross-boundary | PASS / FAIL / NOT_PROVEN | UNVERIFIED until data observed | Named methods actually run on integrated SHA |
| I-C combined Enterprise addons | PASS / FAIL / NOT_PROVEN / BLOCKED | UNVERIFIED if only rollback tests | One module-scoped test on one owned clone |
| I-D synthetic CRM F1-F3 | PASS / FAIL / NOT_PROVEN / BLOCKED | UNVERIFIED for ERP+CRM data | Separate F1-F3 receipt tied to integrated SHA |
| I-E same-clone ERP+CRM identity | PASS / FAIL / NOT_PROVEN / BLOCKED | FAITHFUL / DIVERGENCE / DECISION_REQUIRED / UNVERIFIED | Authorized same-clone source/target comparison |
| I-F same-clone commercial/financial | PASS / FAIL / NOT_PROVEN / BLOCKED | FAITHFUL / DIVERGENCE / DECISION_REQUIRED / UNVERIFIED | Source dates, amounts, statuses, provenance and side-effect comparison |
| I-G same-clone full replay | PASS / FAIL / NOT_PROVEN / BLOCKED | FAITHFUL / DIVERGENCE / DECISION_REQUIRED / UNVERIFIED | Before/after identity, totals, summary, notes/calls, no duplicates |

**Top-line rule:** `COHESION_PASS` is valid only with sufficient I-A to I-G proof; I-A to I-D alone can support `COMBINED_RUNTIME_PASS; END_TO_END_NOT_PROVEN`, never a stronger claim. Every integration failure is classified as `PREEXISTING_INDIVIDUAL`, `COMBINATION_REGRESSION` or `PREVIOUSLY_UNTESTED`, citing an actual first-wrong-boundary counterexample. Report proposed changes **only** as `PENDING_OPERATOR_APPROVAL`; Cursor changes nothing, publishes nothing, and does not rerun automatically after a code revision.

## v2.3.1 PR #303: two distinct sign-offs

**DIAGNOSTIC_COMPLETE:** all authorized import-facing targeted Enterprise checks attempted and accurately classified; published CE observations and unresolved operator decisions carried forward; successful or blocked XMLID test-setup reason recorded; `test_base_user_cannot_unlink` AccessError origin established or clearly NOT_PROVEN; compliance/auto-posting interaction tested if already covered, otherwise marked NOT_PROVEN. Known CE failures are **not counted as accepted PASS**; unresolved stays unresolved.

**PR303_MERGE_READY:** **NO, by default.** The seven known unresolved test contracts/security issues, mixed logistics/document/matching production changes, no-sovereign role matrix, and shared `plasticos_transaction 19.0.2.3.40` collision require their own **explicit approved dispositions and relevant tests**. Diagnostic completion does **not** imply permission to modify or merge. Cursor never sets PR merge approval itself.

In the final approval queue use five buckets: (A) claim recognition business policy, (B) offer-test rewrite only after approval, (C) role-based ACL effective access (plus separately tracked `ir.model.data` and `product.template`), (D) scope split + compliance invoice auto-post/close semantics, (E) Enterprise import fixture and #301/#303 version integration. The accepted A/B/C/D/E decisions in the handoff are **authoritative as policy, not authorization to implement**.

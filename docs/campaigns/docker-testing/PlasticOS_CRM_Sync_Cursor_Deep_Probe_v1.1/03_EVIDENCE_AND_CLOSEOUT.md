# Evidence contract and surgical remediation handoff

## Required output directory

`docs/reports/evidence/plasticos-crm-sync-deep-probe-v1.1/`

That directory is inside the Git worktree. After the files are written, `git add docs/reports/evidence/plasticos-crm-sync-deep-probe-v1.1` so every file there is tracked. `validate_results.py` rejects a directory outside `docs/reports/evidence/` and rejects any non-`.DS_Store` file that `git ls-files` does not list. Do not commit from this diagnostic step unless the operator asks.

`SESSION_SUMMARY.md` (SHA, verified scope, terminal verdicts, counts and limitations)
`COVERAGE_MATRIX.csv` (all 43 immutable behavior IDs plus material reachable additions, statuses and reasons)
`SOURCE_FIELD_LEDGER.csv` (all independently identified fields, or `FIELD_INVENTORY_NOT_PROVEN` with exact missing origin)
`SOURCE_CONTACT_CENSUS.csv` (only tokenized IDs, reference/state/disposition, no PII)
`TEST_EXECUTION_RECEIPTS/` (original native `.test.log`, `.test-receipt.json`, actual exit and test method census; tracked with the evidence directory; no secrets or raw contact PII)
`ROOT_CAUSE_FINDINGS.md` (root-cause anchored, deduped surgical map)
`OPERATOR_DECISIONS.md` (only true policy/provider-access approvals, never unapproved auto-fixes)
`BLOCKERS.md` (material unsupported, uncollected or provenance-blocked obligations)
`PROVENANCE.json` (exact SHA and source digest, fixture/image/PG/Enterprise identity before-after, tests/commands, source window/as-of)
`NEXT_CODING_CONTRACT_CANDIDATES.md` (minimal separate future remediations; **no code edits**)

No file is an official runtime receipt merely because its name resembles one. Include actual command, arguments (redact secrets), test scope, exit, raw log checksum, method ID list, and counterfactual property proved. Native receipt properties and independent environment attestation must not be conflated.

`SESSION_SUMMARY.md` contains each of `DIAGNOSTIC=COMPLETE|PARTIAL|BLOCKED` and `CRM_PROMOTION=PASS|FAIL|NOT_PROVEN` exactly once. Do not paste the alternation list into the summary. `PROVENANCE.json` carries `git_sha` (40 hex), `source_digest`, `image_before`, `image_after`, `template_before`, `template_after`, `postgres_identity`, and `enterprise_revision`. `TEST_EXECUTION_RECEIPTS/` is a directory. A technical `PASS` on a row whose `evidence_lanes` include `enterprise` or `clone` names a file that exists under the evidence directory, and that directory contains a native `.test-receipt.json` or `.test.log`. A `FAIL` `finding_id` matches `[A-Za-z][A-Za-z0-9_.-]{2,}` and appears in `ROOT_CAUSE_FINDINGS.md`. Shareable files contain no `password=`, `api_key=`, `Authorization:`, or dotted email address. Census `record_token` values are non-numeric tokens without `@`.

## COVERAGE_MATRIX.csv shape

Copy all rows of `CRM_BEHAVIOR_CATALOG.csv` as baseline, preserving `behavior_id,group,behavior,owner_surface,initial_probe,required_proof`. Populate existing `technical_verdict` with `PASS|FAIL|BLOCKED|NOT_COLLECTED|NOT_PROVEN|NOT_APPLICABLE`; `business_verdict` with `PASS|FAIL|NOT_PROVEN|DEFERRED_APPROVED|NOT_APPLICABLE`; write actual evidence path in `evidence_ref`, earliest proven fault boundary in `first_wrong_boundary`, exact finding ID for confirmed FAIL, and explanation in `unresolved_reason` for every unresolved row. **Tests not run remain `NOT_PROVEN`, never fake green**. A test-only PASS can coexist with `business_verdict=NOT_PROVEN` pending independent provider census or source-to-ORM readback.

## SOURCE_FIELD_LEDGER.csv shape

Headers shipped in `SOURCE_FIELD_LEDGER_TEMPLATE.csv`. One actual field identity per record, including nested material sections/tables/variant aliases as separate source instances when needed. Fill current authorized disposition (`native|evidence|material|excluded|pending`), source schema exact path, source count/denominator/as-of, target model/field or source-labelled evidence holder, exact/failed/unknown counts, identity link and decision provenance. `source_field`, `raw_provider_path`, and `approved_decision_source` are non-empty. The pair `(source_field, raw_provider_path)` is unique. Numbered placeholders (`field_001`, `TODO`, `TBD`) are invalid. Do not assume absence from a 30-day API sample means the field is absent in historical records. If the 96-field source inventory is unavailable, return exactly the confirmed rows plus a blocker, not 96 manufactured placeholders. The 44 pending fields require priority triage; never implicitly approve a semantic rewrite. `CRM_PROMOTION=PASS` requires every `GATE` row to be technical and business `PASS`, and `BLOCKERS.md` must not contain `FIELD_INVENTORY_NOT_PROVEN` or `EXTERNAL_SOURCE_CENSUS_BLOCKED`. `SRC-01` technical `PASS` requires at least one census data row. Zero census rows require `EXTERNAL_SOURCE_CENSUS_BLOCKED` in `BLOCKERS.md`.

## ROOT_CAUSE_FINDINGS.md schema per finding

`finding_id`, `severity S0-S3`, `affected behavior IDs`, `exact repo SHA`, `proof classification CONFIRMED|INFERENCE|UNKNOWN`, `provider endpoint/window or test method IDs`, `observed vs expected values using safe tokens`, `witness and denominator`, `first wrong boundary and symbol`, `alternative causes discriminated`, `status impact`, `smallest proposed code-owner correction`, `failing discriminating regression after approval`, `external dependency`, `operator decision if any`. Distinguish a real code defect from source limitation, unmapped business policy and uncollected tests. Group all symptoms that share a confirmed root cause; never produce one PR per symptom by reflex.

## Outcomes, truth hierarchy and stop gates

- `DIAGNOSTIC=COMPLETE`: all original 43 obligations explicitly dispositioned, every material root cause bounded or marked unknown with owner and next discriminating probe, environment/source blockers recorded. May coexist with `CRM_PROMOTION=FAIL|NOT_PROVEN`.
- `DIAGNOSTIC=PARTIAL`: material inspection/coverage gaps or no discovery/verification closure; do not hide them in a success summary.
- `DIAGNOSTIC=BLOCKED`: unsafe or inaccessible prerequisite stops the needed evidence collection; independent static tests may still have run.
- `CRM_PROMOTION=PASS`: requires independently complete source-contact history and approved field inventory, successful Enterprise persisted import+readback+identical snapshot replay, all required identity/owner/material/history gates matched, no material error hidden in green status. This Step 1 diagnoses, **does not itself authorize production**.
- `CRM_PROMOTION=FAIL`: an actual materially incorrect accepted behavior has been reproduced.
- `CRM_PROMOTION=NOT_PROVEN`: essential source census, test collection or mapping evidence is missing without confirmed wrong outcome.

No data loss claim from code inspection alone. No unconditional launch/import if the history API is blocked. Do not re-run unchanged green tests or open an endless remediation loop; one discovery pass + one bounded verification pass. The evidence directory, including native logs, is git-tracked. Do not add secrets or raw contact PII. Commit or publish only when the operator asks.

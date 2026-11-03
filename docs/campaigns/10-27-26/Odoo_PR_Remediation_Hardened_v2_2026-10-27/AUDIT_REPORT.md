# Remediation pack audit and hardening report

**Date:** 2026-10-27. **Subject:** input ZIP SHA256 `1e58de60bacb3fdd46577a82d978c72f366de4d28a9cc2bc000dbfcd4efccadc`.
**Verdict:** all 22 incoming finding IDs were reviewed and retained with explicit dispositions; two additional source-level counterexamples were added. The improved contracts are ready for controlled Cursor execution. Repaired PR code and Enterprise runtime are NOT certified by this review.

## What was actually verified

The input ZIP CRC and all nine manifest entries match. All five source contracts, the entrypoint, the 22-row register and all eleven original audit findings were inspected. Fresh GitHub metadata shows the same eight open PR heads and Staging at `e22eb6c0c34d9ea124ae4a04715f7948c3316d86`. Named code paths were inspected at immutable revisions, and the active branch ruleset was read. The earlier partial audit remains evidence, not a new blanket failure or approval.

Six controlled counterexamples executed against copied source-function logic with explicit boundary doubles. Their result is **REPRODUCED DEFECT**, not a successful repair or Odoo test. The fixture and reported unpublished local repairs were not accessible. Detailed evidence coordinates are in `evidence/SOURCE_INDEX.json`; no assertion of whole-repository audit coverage is made.

## Two additional counterexamples

**N-MATERIAL-CONFLICT-FALLBACK:** `_resolve_material` retries without structured evidence whenever shared normalization returns unresolved. The shared normalizer rejects HDPE Drums with a contradictory known LDPE Film hint; the caller then accepts HDPE after dropping that hint. CRM03 requires contradictory known evidence to remain unresolved, without conflating it with an unsupported hint.

**N-PPS-REPLAY:** the PPS gate checks existing freeform text for supersac. The profile reuse path writes the raw source phrase PP Supersacs into that same freeform text. First import blocks PPS notes, but replay can admit them using text written by the previous import. CRM10 requires a genuine eligible identity rather than self-qualification. The reproduction uses the inspected bridge's note-append behavior as a boundary double; native ORM replay is still required.

## Findings that were corrected or narrowed

The inbound-mail allegation is not proven for every template send: official Odoo 19 mail code defaults to `email_outgoing`, while the handler accepts `email`. Installed composer/override behavior still needs proof. Legitimate inbound `unbound` or `identity_unverified` evidence must not be erased simply because it is not an authenticated business commitment.

F-TEST-COLLECT was a historical #302 placement defect. The current #316 loader imports all four suites; runtime collection remains a test requirement, not a demonstrated missing-registration patch.

The Linda lock path contains a model flush and row-directed `FOR UPDATE` query. It does not establish an exclusive table-wide lock or a measured performance regression. A minimal read to determine Linda ownership is allowed.

`Post Consumer` is already a source-type classification, not a condition attribute. The approved information is preserved using that existing field. The earlier statement of seven unmapped crosswalk losses has been removed because the supplied evidence does not establish it.

The installed Compose source selects PostgreSQL 15. The reported 15.19 and broader note saying 16 must not become an unauthorized major-version migration during fixture recovery. The image mismatch is a separate reported runtime observation.

## Documents source preservation

The frozen BRS ZIP digest matches its declared source identity. Git blob hashes match all three original chapters byte-for-byte. Reconstruction from the supplied 170-rule registry gives exactly the 44 local effective-rule records, and all 44 local acceptance records; both reconstructed JSON blobs exactly match #318. The other 126 rule identities remain external references.

This verifies source copying, not repository admission or implemented native Documents behavior. #318 must also retain the logistics overlay inherited from #317. Taking only its last two Documents commits would drop unique alignment work.

## Full finding disposition

`CONFIRMED_REMOTE` means the bounded source/state allegation is supported on the named remote revision, not that a local repair is incorrect or an Enterprise reproduction was run. All other classes deliberately distinguish historical, external or prospective obligations from code defects.

| Finding | Disposition | Contract | Acceptance IDs |
|---|---|---|---|
| `F-THROTTLE` | CONFIRMED_REMOTE | C01 | L01, L02 |
| `F-DROPSHIP` | CONFIRMED_REMOTE | C01 | L03 |
| `F-SECTION-HINT` | CONFIRMED_REMOTE | C02 | CRM02 |
| `F-INBOUND` | NARROWED_REQUIRES_RUNTIME | C01 | L06 |
| `F-TEST-COLLECT` | ALREADY_ADDRESSED | C01 | L08 |
| `F-CI-MISSING` | CONFIRMED_REMOTE | C05 | R02 |
| `F-MAIL-LOCK` | CONFIRMED_REMOTE | C01 | L04 |
| `F-CANCEL-WRITE` | CONFIRMED_REMOTE | C01 | L05 |
| `F-CRM-TAG` | CONFIRMED_REMOTE | C02 | CRM05 |
| `F-CLASSIFY-GUARD` | CONFIRMED_REMOTE | C02 | CRM06 |
| `F-STACK` | CONFIRMED_REMOTE | C05 | R01, R03 |
| `A-MATERIAL-PE` | CONFIRMED_REMOTE | C02 | CRM01 |
| `A-MATERIAL-1-7` | CONFIRMED_REMOTE | C02 | CRM01 |
| `A-CRM-STAGES` | NARROWED_REQUIRES_RUNTIME | C02 | CRM08 |
| `A-CRM-ERROR-SCHEMA` | CONFIRMED_REMOTE | C02 | CRM07 |
| `A-CRM-HISTORICAL` | EXTERNAL_EVIDENCE_REQUIRED | C02 | CRM09 |
| `A-DOCUMENTS-OWNERSHIP` | VERIFIED_SOURCE_PRESERVATION | C03 | D01, D02, D03 |
| `A-DOCUMENTS-NATIVE` | FUTURE_RUNTIME_GAP | C03 | D03 |
| `A-ENV-IMAGE` | EXTERNAL_EVIDENCE_REQUIRED | C00 | E01, E02, E03, E04 |
| `A-ENV-POSTGRES` | VERIFIED_DISTINCTION | C00 | E01 |
| `A-MATERIAL-SOURCE-OWNER` | VERIFIED_DISTINCTION | C02 | CRM01 |
| `A-MATERIAL-SOURCE-CONFLICT` | CONFIRMED_REMOTE | C02 | CRM04 |
| `N-MATERIAL-CONFLICT-FALLBACK` | CONFIRMED_REMOTE | C02 | CRM03 |
| `N-PPS-REPLAY` | CONFIRMED_REMOTE | C02 | CRM10 |

## Contract defects repaired

### PK01. Contracts were prose, not schema-valid execution objects

**Observed:** The five original files do not expose all required execution-contract fields as machine-readable records.

**Changed:** Six canonical YAML contracts and native/schema validation.

Source: `contracts/*.md`.

### PK02. Read-only preflight was actually mutating

**Observed:** The contract labels scripts/test_env.sh status non-mutating, but the pinned script starts db and builds the image.

**Changed:** Read-only Docker/SQL inventory precedes intended build; status classified honestly.

Source: `contracts/00_ENTERPRISE_FIXTURE.md:Procedure 1`.

### PK03. Backup acceptance could skip restoration proof

**Observed:** Original accepts archive integrity/object count as an alternative to a restore test before template retirement.

**Changed:** Restore drill, owned scratch identity, filestore check and rollback evidence are mandatory.

Source: `contracts/00_ENTERPRISE_FIXTURE.md:Procedure 3`.

### PK04. Publication depended on forbidden parent merges without a distinct local completion state

**Observed:** No-merge instruction and Staging-only publisher leave child publication awaiting a human step. Original completion wording blurs local success with campaign completion.

**Changed:** Explicit local/published/merge-ready states and per-PR human checkpoints; independent lanes continue.

Source: `00_CURSOR_START.md; contracts/02_CRM_PR312_PR314.md; contracts/03_DOCUMENTS_PR318.md`.

### PK05. Inbound contract conflated evidence with authenticated commitment

**Observed:** It says messages without bound/authenticated original MIME must not create reply evidence, yet the model intentionally stores unbound and identity_unverified evidence.

**Changed:** Preserve legitimate inbound exceptions; distinguish direction, correlation, sender authentication and accepted business facts.

Source: `contracts/01_LINDA_PR316.md:L5; contracts/04_CLOSURE_AND_RELEASE.md:matrix 3`.

### PK06. Non-Linda mail isolation over-constrained harmless reads

**Observed:** Ban on extra ORM query can forbid the minimal read needed to determine whether a mail belongs to Linda. It also fails to distinguish row lock from table-wide exclusivity.

**Changed:** Allow minimal read-only classification; prohibit model flush, claim mutation/row lock and unrelated commits.

Source: `contracts/01_LINDA_PR316.md:L2`.

### PK07. Unproven seven-loss claim became a frozen requirement

**Observed:** Neither 763 ContactIDs nor 716 ERP people establishes seven unmapped losses. No private crosswalk is supplied for that claim.

**Changed:** Remove asserted seven; require actual mapped/unmapped/duplicate/collision census and retain historical gate.

Source: `contracts/02_CRM_PR312_PR314.md:C1`.

### PK08. Mandatory summary discrepancy could be punted outside completion

**Observed:** Schema alignment is mandatory but edit ownership could be deferred to another proposed handoff, leaving no direct completion path.

**Changed:** C02 explicitly includes bounded producer/schema/validator/consumer closure with strict failure semantics.

Source: `contracts/02_CRM_PR312_PR314.md:C2; contracts/04_CLOSURE_AND_RELEASE.md`.

### PK09. Tag duplicate handling promised success without identity policy

**Observed:** Original says not to fail upgrade when duplicates exist, but no legitimate deterministic identity may exist.

**Changed:** Actual install and parent-version upgrade tests; ambiguity may explicitly block before destructive data choice; no arbitrary merge.

Source: `contracts/02_CRM_PR312_PR314.md:C8`.

### PK10. Dropship guard lacked an unavoidable positive safe-send gate

**Observed:** Fail-closed wording could allow an implementation that still blocks every legitimate dropship; an HTML screen is not proof of sent PDF bytes.

**Changed:** Require positive safe dropship with queued attachment byte/recipient evidence plus cached/stale negative cases.

Source: `contracts/01_LINDA_PR316.md:L3`.

### PK11. Historical collection defect was attributed to current survivors

**Observed:** Original audit names #302; register associates #305/#316. Current #316 loader registers all four suites.

**Changed:** Mark source defect already addressed; retain runtime collection as a proof obligation, not a forced patch.

Source: `evidence/REMEDIATION_REGISTER.csv:F-TEST-COLLECT`.

### PK12. Documents preservation focused on the last two commits

**Observed:** The two Documents commits are not all unique useful work: #317 logistics alignment is also present in #318 and absent from #316.

**Changed:** Preserve whole overlay and all source/owner references; reconcile complete effective tree.

Source: `contracts/03_DOCUMENTS_PR318.md:D1`.

### PK13. Source/test/published identities were too easily collapsed

**Observed:** A docs-only commit need not invalidate identical addon code proof, while actual code/base drift must. Local repair prefixes are not published source.

**Changed:** Full local/source/tested/remote revisions plus code/addon digest equality and proportional revalidation.

Source: `contracts/01_LINDA_PR316.md:Validation gates; 00_CURSOR_START.md`.

### PK14. Broad directly-coupled CI edit scope could expand remediation

**Observed:** Necessary directly-coupled CI scope files is an open-ended edit allowance without an exact defect/owner boundary.

**Changed:** Explicit implementation paths, conditional narrow collateral allowance and separate scope gate for CI/security/governance changes.

Source: `contracts/01_LINDA_PR316.md:Exact scope`.

## Execution architecture of v2

Six individually schema-valid contracts replace mixed prose. C00 owns safe fixture recovery, C01 Linda, C02 CRM, C03 Documents-only alignment, C04 independent parent readiness, and C05 final integration/publication evidence. Each has a single repository write boundary, exact modification scope, source anchors, explicit negative tests and action permissions. Each incoming finding has one accountable contract and test references; cross-lane preservation is explicit.

Parent human merges are exposed as publication checkpoints. A branch can be `LOCAL_VERIFIED_AWAITING_PARENT` without being falsely called ready or being reimplemented from scratch. #309's pure scanner verification can finish independently. If the current publisher still only supports Staging, do not manufacture a new PR for #314 or bypass it. No actual merges are authorized.

## Review limits and residual evidence

The six counterexamples are narrow source-excerpt tests, not independent native Odoo execution. Exact local `53cb6316...` and `ca4f3f26...` changes, real PostgreSQL/Enterprise state, queued PDFs, live multi-worker behavior and private CRM corpus remain unverified. Current check-runs prove a CI gap on the published Linda candidates, not its cause. Any fresh repaired source supersedes only affected old findings after new evidence, not by narrative assertion.

This is a single-session pack hardening review. The producer-validated assessment is partial because the requested underlying code/runtime conclusions still contain material Unknowns. No GitHub comments, branch changes, pushes, PR closures, merges or deployments were performed.

**Alignment follow-up (current release): 49 Python-only offline tests passed.** This supersedes the 46 and 41 counts below, which are retained as historical lineage. The alignment additions were evaluated by the package release builder, not an Odoo runtime.

# Validation Report - Exact Package Source

**Latest portable result (Recursive Leverage revision): 46 offline tests passed.** The 41-test count in the original subsection below belongs to the prior Revised archive, retained for traceability. Odoo Enterprise runtime remains NOT RUN.

## Evidence classification

- **Passed (portable source):** 41 Python-only offline tests (`unittest discover`), compilation of all delivered Python files, parse of delivered Odoo XML, package declarations, ACL model-reference checks, add-on dependency cycle check, all source-catalog declared digests, seed XML structure, prohibited-identifier and private-key scan. Reproducible checks live in `tests_offline/` and `tools/validate_package.py`.
- **Not run:** Odoo 19 Enterprise `odoo-bin` registry installation, ORM tests, PostgreSQL indexes, native ACL/record-rule behavior, binary attachment storage, final web-lead model inference provider call, live Email/Offer/Match state-machine integration and staging or Production activation. No runnable Odoo runtime or connected disposable Odoo database was available in the build container.
- **Unknown/unproven:** equivalence to source from a nonexistent second standalone v1 ZIP, original 38 seeds, migrations of historical v1 data, and any actual installation in Odoo.sh.

## Acceptance scenarios

| # | Scenario | Portable evidence | Odoo 19 runtime gate |
|---|---|---|---|
| 1 | Approval cannot bypass review inputs | `action_approve` enforces source SHA, candidate key, owner, reviewed meaning, evidence requirements, reason, attachment, reviewer attestation; Odoo regression test authored | **NOT RUN** |
| 2 | Draft/retired never ordinary advice | Offline `rank_approved` tests **PASS** | **NOT RUN** |
| 3 | Concurrent approvals one active version | Partial SQL unique index + row lock implemented | **NOT RUN** |
| 4 | Company/party isolation | Native source read + company rule and ACL code inspections | **NOT RUN** |
| 5 | Unauthorized Mack source message denied | Chatter-source model/record/user/thread/body checks implemented; Odoo test authored | **NOT RUN** |
| 6 | Message-bound Mack replay idempotent | Deterministic `request_key` + DB uniqueness + collision guard implemented | **NOT RUN** |
| 7 | Missing MFI not zero | Offline **PASS** | **NOT RUN** |
| 8 | MFI without test conditions insufficient | Offline **PASS** | **NOT RUN** |
| 9 | Rejection aliases never silently resolve | Offline **PASS**, 28 aliases unresolved | **NOT RUN** |
| 10 | Single rejection not permanent exclusion | Offline rejection service **PASS**; approved guidance must also pass prerequisite/citation gates; no exclusion write | **NOT RUN** |
| 11 | Historical pricing not live quote | Advice abstains from price, offline **PASS** | **NOT RUN** |
| 12 | Invalid citations deferred/unavailable | Offline **PASS** after added hash/source guard | **NOT RUN** |
| 13 | Web-lead integration off baseline | Returns exact `super()` signals when off, static + helper tests **PASS** | **NOT RUN** |
| 14 | Shadow-only cannot route | Only injected when native qualification itself `shadow`; helper tests **PASS** | **NOT RUN** |
| 15 | No extra economic model request | Advisory uses no provider; existing one-call seam untouched | **NOT RUN** |
| 16 | Failed advice cannot silently create COLD | Optional advice failure returns original native signals; no COLD code added | **NOT RUN** |
| 17 | Feedback cannot change approved knowledge | Separate append-only observation model, deduplicated source-revision/actor/evidence identity, no knowledge write | **NOT RUN** |
| 18 | Installation/upgrade preserves history | Stable XML IDs, `noupdate="1"`, append-only history; static checks **PASS** | **NOT RUN** |
| 19 | Optional addons only declared dependencies | Manifest checks + acyclic dependency graph **PASS** | **NOT RUN** |
| 20 | No advisory commercial state mutation/mail | Pure reasoning/rejection tests **PASS**, no matching/offers/email in advice code | **NOT RUN** |

**Interpretation:** No scenario's runtime column is a PASS. Source tests demonstrate bounded behavior without Odoo ORM and cannot establish installation-ready status. The package is a testable **candidate release**, not Enterprise-installation-proven.

## Validation commands

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests_offline -v
python tools/validate_package.py
python tools/validate_package.py --verify-manifest
```

See `BUILD_MANIFEST.json` for exact bytes and SHA-256 of every packaged file except the manifest itself. `tools/build_release.py` regenerates a manifest and verifies archive members and CRCs. Real Odoo tests are under each addon `tests/`, but were not executed in this environment.


## Kernel v3.0 recursive improvement from the original v2 ZIP

- **Baseline pass:** Verified original 100-member ZIP CRC and SHA-256 `649389e7b3fe163067e68beff6fa48d6518d0fed27f9482b171468eac79fe183`. Original 36 portable tests and static manifest validation PASSED. Inventoried the complete original archive, including the exact source catalog; validated catalog member digests. The external Odoo runtime was unavailable at both baselines.
- **Owner-bound root-cause pass:** Closed a direct-create path for forged `plasticos.broker.review.event` entries. Audit insertion now has a private, knowledge-owned action that derives real actor and source revision; the public create method rejects attempts, including sudo. Odoo database enforcement is still NOT RUN.
- **Feedback integrity and isolation pass:** An arbitrary quality/correction narrative can no longer inherit `verified_against_source` from an unrelated rejection state; the flag requires the exact rejected source text and a rejection observation type. Feedback reads are actor-and-company scoped, and provenance distinguishes source company from operator context. A past source's later authorization revocation remains a runtime policy question for historical receipts.
- **Rejection evidence pass:** Approved rejection knowledge is filtered by the same structured prerequisite and source-citation checks used by `broker-advice/v2`; incomplete evidence is deferred instead of rendered as applicable guidance.
- **Evidence performance pass:** Reviewer admission checks `ir.attachment` metadata instead of decoding binary content to test existence. An empty file cannot satisfy the attachment requirement.
- **Packaging integrity pass:** The builder now reruns and counts real offline tests at build time, accepts an explicit output path, and records original v2 ZIP and kernel SHA-256 rather than reusing a stale claimed test count.
- **Regression pass:** Five focused new portable test methods added covering source-confirmed rejections, feedback rule, audit direct-create source guard, rejection prerequisites, and invalid-citation abstention. Total offline tests: **41 passed** on the working source before delivery; the release builder reruns them on the exact packaged state.
- **Convergence:** Source improvements complete for the issues above. Full feature/runtime readiness remains **NOT PROVEN** until Odoo 19 Enterprise registry, ACL, concurrency, attachment and web-lead runtime gates execute successfully. No GitHub, Odoo.sh or Production mutation was performed.

A structured findings and pass receipt is in `IMPROVEMENT_REPORT.yaml`. Structural/AST tests are *not* permission-rule or ORM execution. Do not treat a successful portable build as a Staging deployment authorization.

## Release gate disposition

**BLOCKED ON RUNTIME PROOF:** install into an isolated Odoo 19 Enterprise database with the pinned owner revision, run `-i` test installation and `-u` replay, inspect actual ACL/rules with users from two companies, validate native web-lead shadow provider context without extra calls, and prove no business state changes. Only then consider a Staging deployment; Production remains a separate authorization.


## Recursive Leverage follow-up: current package evidence

The original 41-test receipt above describes the **parent revised archive**, not the current follow-up state. The release builder re-runs the complete `tests_offline` suite and records the observed result in `BUILD_MANIFEST.json`. The new tests directly exercise retrieval truncation, conditional applicability, ambiguous approved rejection references, and the single source-access owner; an additional Odoo-only source-ID test was authored but **NOT RUN**. Static checks cannot establish live ORM, multi-company, or concurrency behavior.

New response fields are additive (`workflow_scope`, `applicability_verified`, `knowledge_retrieval`); the existing `broker-advice/v1` wrapper and action routing remain intact.

## Current architecture-alignment verification

- **Portable execution:** 49 pure Python tests passed with zero failures; syntax, XML, model ACL references, archived source SHA digests, draft counts, module topology, and package hashes are verified by `tools/validate_package.py`.
- **New exact-scope protections:** source-company-only knowledge domain is shared by advice and rejection wizard, saved review attestation is invalidated on mutable input, feedback digest is unambiguous and scope-bound with guarded legacy replay, shadow advice uses a database savepoint, and source IDs cannot truncate booleans/floats.
- **Odoo runtime acceptance:** NOT RUN. The actual Odoo 19 Enterprise registry, reviewer ACL, two-company information barriers, original attachment lifecycle, PostgreSQL unique-index migration, and shadow failure recovery are unknown.
- **Authority review:** Current `Staging@d25da3236887c924c8a0164b00c1198f1804a2ea` moved from the original pin through two documentation-only commits. The open PR #471 affects Export documentation only. No commercial owner API changes were observed.

`ARCHITECTURE_ALIGNMENT_REPORT.yaml` records the concrete violation-to-fix disposition and minimum safe next action.

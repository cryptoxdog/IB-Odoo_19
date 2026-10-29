# Recursive hardening and kernel-to-repository alignment

**Scope of inspection:** 30 current Odoo addon manifests, active constitution and 19 core authority files, current enrichment ORM/source/view/ACL/hooks/tests, Gate Odoo mapper/allowlist/config, inherited security-base test, and present ADRs. Runtime/Enterprise database and actual Gate/EIE deployed packets NOT inspected. Source is pinned to `2dc516aa29718b4545faf67e79ca225589ac6d7f`.

## First-pass defects and corrected owner dispositions

| Finding | Severity | Problem observed | Required disposition |
| --- | --- | --- | --- |
| F01 | P0 | Broad base.group_user full CRUD | ['E08', 'E09', 'E06'] |
| F02 | P0 | Bulk Inject circumvents per-field consent | ['E04', 'E05', 'E02'] |
| F03 | P0 | ADR-012 contradicts current feature defaults | ['E18', 'E21', 'E23'] |
| F04 | P0 | Retired cron privilege grant | ['E14', 'E15'] |
| F05 | P0 | No run-level company/record rules | ['E09', 'E02'] |
| F06 | P1 | Legacy local inject remains reachable | ['E05', 'E12'] |
| F07 | P1 | State guard can be bypassed | ['E06'] |
| F08 | P1 | Aggregate confidence hidden or misrepresented | ['E01', 'E07'] |
| F09 | P1 | No field-level citation in mapped contract | ['E03', 'E02'] |
| F10 | P1 | Unknown eligible field discarded or degrades | ['E01', 'E03'] |
| F11 | P1 | Auto-writeback code path still exists | ['E01', 'E04', 'E18'] |
| F12 | P1 | No native proposal line artifact | ['E02', 'E03', 'E10'] |
| F13 | P1 | No transaction-safe CAS/admission | ['E04', 'E07'] |
| F14 | P1 | Retired cron has noupdate XML | ['E13', 'E15'] |
| F15 | P1 | Existing tests assert legacy one-click and live mode | ['E23', 'E25'] |
| F16 | P2 | README stale version + ambiguous wording | ['E17', 'E12'] |
| F17 | P2 | Historical review evidence must survive | ['E07', 'E26', 'E15'] |
| F18 | P2 | Source-only scope is incomplete | ['E28'] |
| F19 | P2 | Existing tests and tech debt include exact consumers | ['E23', 'E25', 'E17', 'E18'] |

## Recursion passes, outcomes

**Pass 1: evidence/source rebind.** Prior v1.0.0 case targeted current Staging but used the old bundled 677d manifest/source lock and lacked eleven source blobs. Fixed: new `EVIDENCE/REPO_SOURCE_LOCK_CURRENT.json`, all 30 freshly inspected addon manifest SHAs/dependencies and every effect's exact source blob/proposed-new status. Original supplied kernel remains untouched. Result: no `SOURCE_DRIFT`, `MISSING_EXACT_BLOB`, DAG or schema errors.

**Pass 2: exact semantic owner.** Removed assumed Gate module rewrites. The current Odoo `plasticos_gate` already owns the eight-field mapper and dual switches. No external API or field schema addition is justified. A new model is justified only as `plasticos.enrichment.proposal.line` within the *existing* addon because pending reviewer decisions have a different semantic meaning from committed `plasticos.enrichment.provenance`. Do not add a second addon, queue or service.

**Pass 3: authority and contradiction.** Accepted ADR-012 says single-switch auto-writeback defaults ON, while active code and data seed TWO flags OFF. Amend ADR-012 in place with historical status preserved and a new proposed successor for granular approval; keep ADR-003/009/010/013/017 and Gate owner semantics unchanged. Source-only manual review is bounded, and CEG nightly ranking stays outside Odoo.

**Pass 4: security/blast radius.** Broad `base.group_user` CRUD spans run/source/extraction/provenance; no addon company `ir.rule` in the inspected manifest. Hook grants manager privilege to old cron user. Source run.write allows terminal payload change when `state` key included. All enter P0 safeguards, migration and direct-RPC negative tests. Tests from security_base and root tests are named consumers. No assumption of deployed grants being unchanged.

**Pass 5: data/evidence and transition integrity.** Current `gate_proposal` stores mapped final fields, proposed partner fields and EIE run-level metadata, NOT necessarily raw signed packet or per-field citations. New lines must project immutable source snapshot, distinguish missing evidence from absence, and never claim per-field EIE confidence. Gate run's displayed `confidence_score` currently depends on legacy extraction records; its field-level interpretation must be fixed. `Inject` remains a compatibility entry requiring prior decisions, no implicit approval. Historic `engine_used=local` records become read-only and retain provenance.

**Pass 6: migration/verification/next consumer.** Existing old cron XML is `noupdate=1`; original migration should not be rewritten. New versioned remediation after actual installed version discovery, while keeping old cron records disabled. Tests cover 2-of-3 approvals, race, role/company, no-eligible-fields, retry, legacy local evidence, actual Enterprise install/upgrade and DB+filestore restore. Manifest sources and regression owner are named; no deleted unrelated files.

## Hardening-specific counterinterpretations

**Could provenance hold proposal-line status?** It has actual write values, committed-write statuses and current UI. Reusing it for *pending* consent would allow a user to misread an un-applied prediction as a written CRM value, and migrate histories ambiguously. The smallest defensible new model stays in the same addon. A source-owner implementing it may propose a different representation only with independent proof that semantic/audit ownership is preserved.

**Could human review be satisfied with old Inject?** No. It accepts all eligible values in one action without a recorded decision per field, no stale-value compare, no reliable actor mapping and weak access guard. New explicit lines and server approval make the requirement testable.

**Could the EIE response provide field citations?** Current Odoo mapper does not guarantee them. Do NOT alter EIE. Display run-level references only when true, and permit reviewer-attested per-field evidence with clear origin and role. Unsupported suggestions remain evidence-only until accepted review policy is met.

**Could security changes be avoided because UI buttons are restricted?** No. Broad model CRUD and public RPC are separate from view visibility; role, company and state must be enforced server-side. No blind ACL revocation without installed graph/caller census.

## Source closure limits (must not be misreported as complete)

We have immutable repository evidence for the affected static paths. We do NOT have installed Odoo.sh database, current Enterprise extensions, dynamic `ir.actions.server`, cron state, group membership, existing historical row populations, exact live Gate packet or independent owner acceptance. `U00` remains a material blocker, not hidden underneath a source-bound green validator. A new actual consumer or source drift reopens only the affected effect and its downstream proofs.

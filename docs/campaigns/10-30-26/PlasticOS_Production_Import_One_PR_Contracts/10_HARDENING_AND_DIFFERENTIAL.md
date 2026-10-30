# Hardening findings and dispositions (v1.0 -> v1.1)

| Finding | Original defect in prior pack | Hardened disposition |
|---|---|---|
| H01 | Implicit wait for #346 merge before starting separate work; stale fixed branch SHA | Start from actual verified Staging; rebind after external merges, compare overlapping owner closure |
| H02 | Required read-only live Production credential/network proof before *any* code work | Separate offline code readiness from actual hosted import authorization; missing live evidence remains NOT_RUN |
| H03 | Original C05 treated full Enterprise ten-test closure as PR-publishing prerequisite despite separate repair work | Differential candidate vs base is code PR gate; ten-test closure remains mandatory merge/promotion gate |
| H04 | Production permit described too loosely, could become reusable environment bypass | Bind actual DB identity, stage, build, release, snapshot, phase, expiry/run ID; wrong/replay/skip-phase negative controls |
| H05 | ERP bounded sessions could misuse newest-N `ERP_LIMIT` as chunk cursor | Explicit stable-key, snapshot-locked, shared-order-safe resume; fail if no bounded Odoo.sh-native path |
| H06 | Partial ERP summary may still return exit 0 | Script exit separated from data acceptance, source exceptions and accounting state exposed |
| H07 | Source-accurate financial status ambiguous | No new posting semantics; accounting DATA_ACCEPTANCE remains blocked until independent approved source semantics |
| H08 | CRM hardcoded local checkpoint path; checkpoint marked any row completed | Durable/reconciled Odoo identity vs checkpoint; retry only with evidence, preserve reason and API backoff |
| H09 | Historical 4,876 snapshot could be mistaken for live full-population import | Separate snapshot cohort, live recent delta, authoritative total if available, otherwise live coverage UNKNOWN |
| H10 | Contract claimed command publication owner partly verified | v1.2 D1: verify the repository-local `Makefile` `pr` -> `scripts/make_push_pipeline.sh` chain before the single `make pr`; unknown blocks only publication |
| H11 | Documents/worksheet images might slip into critical path | Strong negative exclusion in scope, tests, runbook and post-import gates |
| H12 | No clear artifact vs implementation assurance distinctions | Package structural validator/negative controls, no claim of GAR compiler conformance or live runtime PASS |

| H13 | Earlier cutover graph and initial contract publication gates blurred | Bind later operator graph 26/27; require hosted-source preflight before combined same-night promotion although code PR can publish without credentials |

## Comparison/adversarial consistency probes

1. Inject a fake `ALLOW_PROD` env flag with mismatched DB UUID/stage/release/source; ensure no ORM write.
2. Interrupt before and just after ERP commit; assert no duplicate payable, worksheet transactions, shared sale order or mail.
3. Replay with a changed source backup/digest or changed code revision; assert refusal, not mixed-source ingestion.
4. Replay CRM after Odoo commit and before durable checkpoint; ensure no duplicate person, lead, ref, call or custom table rows.
5. Load a pending/NO ContactID matching an ERP email; assert no person binding; preserve DNC and status.
6. Configure CRM cron overlapping manual historical import; assert one fenced owner and no silent second writer.
7. Feed a `partial` ERP result with nonzero rejected entries and process exit 0; assert DATA_COMPLETE remains false.
8. Hide a historical accounting posted-state value; assert no fabricated invoice posting and no ACCEPTED status.
9. Drop Odoo.sh access and private API credentials; code PR can remain assessable but import-ready must fail.
10. Try an unrelated #346 merge during implementation; assert base rebind, overlap review and retest before PR terminal publication.

**Design warning:** Contradictions requiring new public security/auth mechanism or an accounting-status owner decision cannot be settled by implementation-discretion. The affected slice is blocked and returned as exact evidence question, not generalized architecture work.

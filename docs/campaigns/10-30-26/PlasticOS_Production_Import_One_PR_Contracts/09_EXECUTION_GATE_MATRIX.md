# Operator runbook proof ledger: do not confuse PR green with overnight cutover

Every row is a REQUIRED evidence item for the named milestone; never mark PASS from a plan, stale fixture, synthetic script or observed mere command exit. Fill this after implementation and again after an operator-authorized cutover.

| Proof | Code PR | Before merge/promotion | Before first Production import | After imports |
|---|---|---|---|---|
| Exact patch SHA, modified-file owner census and schema/checks | Required | Refresh final merged release SHA | Match deployed release SHA | Include in receipt |
| Default-deny Production refusal + positive scoped simulated permit | Required | Regression pass | Exact real target permit reviewed | Record used permit ID without secret |
| Full Enterprise base-vs-candidate tests | Required differential | Full integrated green incl. the ten-test closure | Not a substitute for source proof | Preserve SHA results |
| Actual Odoo.sh shell, addon install, SQL driver, private SQL reachability | May be NOT_RUN | Deployment prerequisites | Required live read-only proof | Record observed runtime |
| Immutable current ERP source snapshot and census | Fixture proof | Not historical go-live data | Required current source snapshot | Counts/amounts/exception ledger |
| Empty first-import business-data target, no reset or hidden waiver | Simulated | No Production writes | Required target census / separate reset authorization if needed | Verify writes only into named target |
| Phase 1 active partner then Phase 2 full commercial import, no LIMIT | Disposable real-runtime | N/A | Operator authorized run plan | Must reconcile stages and stable IDs |
| No email, Linda, stock/procurement, payments/account posting, CRM cron races | Simulated negative | Recheck after merge | Check actual job/mail configuration | Negative side-effect receipts |
| VanillaSoft old per-ID API, exact private crosswalk digest, 4,876 census | API might be NOT_RUN | No PR secrets | Required API + private-input proof | 4,876 dispositions + reason per hold/fail |
| Post-snapshot CRM delta | Simulated | N/A | Current-source scope must be known | Current delta separate; no claim all-current unless source census proves |
| Crash/replay after DB commit before checkpoint, interrupted session, double run | Required test | Recheck against final SHA | Real-host feasibility/read-only proof | Verify no duplicates and bounded resume |
| Historical accounting real-state contract | Record current Odoo draft/no-post truth | Record required decision | Block accounting acceptance if unadmitted | Never mark accounting data COMPLETE by assumption |
| Odoo.sh native pre-change DB+filestore restore point | N/A | Deployment planning | Required before deployment/cutover | Restore provenance retained |
| Broad business UAT and AWS DR rollout | Deferred | Deferred | Deferred | Separately planned |
| Worksheet images/documents -> transactions | **EXCLUDED** | **EXCLUDED** | **EXCLUDED** | **EXCLUDED** |

## Execution gates after the coding PR

1. **PR_PUBLISHABLE**: code within one seam, source-backed root fix, target tests, no introduced regressions; current publisher verified; single PR to Staging. Missing host credentials may leave operational gates NOT_RUN.
2. **MERGE_PROMOTION_READY**: externally approved merge, final integrated Enterprise green after the known ten issues, correct branch/release code. Operator separately authorizes promotion. Full production migration rehearsal deferred. Verify native pre-change restore point, release-ready modules and code loading.
3. **HOSTED_IMPORT_READY**: deployed Production SHA, trusted live Odoo.sh target and a current ERP source read-only connected; first-import clean business data or separately approved reset, scoped import permit, no side effect, real driver, VanillaSoft API and private crosswalk, host restarts safe. ERP and CRM may be separately blocked where inputs absent.
4. **POST_IMPORT_DATA_ACCEPTED**: actual final ERP partner/commercial and historical CRM count/crosswalk/field/disposition evidence, account-state semantics independently approved, separately current provider delta. No automatic approval from summary `partial`, `exit 0`, 4,876 snapshot or presence of invoice rows.

**Same-night sequencing invariant:** if promotion and first data load will happen during the same overnight window, finish the real hosted connectivity, source freshness, credential, clean-target and bounded restart preflight *before* promoting the code. Runtime preflight may be deferred for an earlier coding PR but not for a committed same-night cutover.

## Stop conditions for overnight operator

- Before ANY live write: wrong target/build/code/source, unreadable ERP SQL source or invalid driver, unknown source freshness, nonempty business partners on first import without separate operator disposition, permit invalid/expired, customer-facing cron/mail not fenced, no native restore point.
- During ERP: changed SQL snapshot, failed partner layer gate, payables reconciliation failure, unaccounted rows, unhandled transaction identity conflict, inability to resume without duplicating business records. Persist exception ledger, do not improvise SQL writes.
- Before CRM: ERP partner identity not reconciled, crosswalk digest mismatch, API auth or old-ID fetch failure, unbounded throttling, missing durable checkpoint, pending/NO IDs incorrectly bound as ERP partners, overlap with incremental cron.
- After ERP/CRM: keep exceptions explicit and block respective *data-complete acceptance* until reviewed. Do not silently repair production by replaying arbitrary commands, change accounting status or post payments.

**No Production execution commands, tokens, URLs with credentials, database passwords, customer PII, or shell modifications are issued by this planning pack.**

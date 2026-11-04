# Acceptance gates, actual receipts and falsification cases

**Scope:** SM-ODOO-INDEPENDENT-DR-001. A test fixture proves code behavior, not the existence of a real Odoo.sh source or ability to restore a real Odoo 19 Enterprise system. Recording the actual source timestamp is mandatory.

## Required gate ledger

| Gate | Minimum observable proof | Disqualifying case |
|---|---|---|
| **P0-A Source identity** | Live Odoo.sh Production build/DB identity, SSH/native backup grant, latest completed source-backup timestamp, full DB+filestore archive discoverable | Dev/Staging instance or backup timestamp assumed from download time |
| **P0-B AWS isolation** | Verified account ID/company owner/region/role, new-resource list, cost estimate, IAM/SCP boundary | Same production credential controls vault, unknown account or arbitrary-resource edit |
| **P0-C Blast radius** | Accounted exact new/modified files, AWS services, source reads, dependency/consistency proof, secrets/license and rollback | Hidden source mutation or unexpected model/schema/cron change |
| **P1-A Native continuity** | Odoo.sh native automatic backup schedule still enabled; actual latest native recovery point | Native backups disabled, replaced or altered |
| **P1-B Vault protection** | Private encrypted S3 bucket with Object Lock, valid version IDs/retention dates, writer denied delete and KMS administration | Protected object can be removed/shortened using writer identity |
| **P1-C First independent copy** | Genuine production database + referenced filestore source archive; hashes, byte totals, source timestamp, S3 versions, independent read | Only zip upload; database or filestore missing; no source time |
| **P2-A Restore and integrity** | Isolated independently restored Odoo 19 Enterprise; source transaction, changed/unchanged attachments, DB relations, ACLs; no Odoo.sh dependency | Restored DB opens but attachments missing, code mismatch, or needs Odoo.sh key |
| **P2-B No side effects** | No outbound SMTP, payments, shipping, webhooks or cron-driven operational writes during restore | One external business effect occurs during test |
| **P3-A Fresh source** | Two or more *different* valid source-time checkpoints from the supported acquisition path | Four downloads of the same nightly native backup |
| **P3-B Dedup and deletion** | Controlled isolated Odoo fixture creates/changes/deletes transaction and attachment state through the actual backup engine; newer restore preserves deletions and old restore retains old bytes. Real Production snapshots independently proven | Production data modified as a test, `write_date` partial state or phantom resurrected record |
| **P3-C Immutable closure** | Every shared content object version is protected at least through all dependent immutable snapshot retention; restore latest and older | Old chunk pruned or Glacier-only while newer checkpoint still references it |
| **P3-D Efficiency** | Measured baseline full transfer vs incremental read and S3 bytes, including DB and filestore; no silent full re-transfer | Only S3 storage is reduced while 40GB source transfer silently repeats without disclosure |
| **P4-A Schedule** | Actual AWS Scheduler triggers at 11/13/15/17 Mon-Fri Eastern with DST, no overlap, native backups unchanged | Night/weekend trigger, skipped error/no alarm or two running jobs |
| **P4-B Timeliness** | Real `source_checkpoint_at`, upload/commit completion and measured source-age timeline. RPO calculated during business hours | RPO reported from scheduler start time or >=2 hours without alert |
| **P4-C Recovery exercise** | Successful independent restore from at least one scheduled (not merely manual baseline) checkpoint | Checkpoint files only uploaded/verified via list command |
| **P5-A Publication** | Scoped PR after actual code/test evidence, compliant reviewed publication path; actual AWS state captured | Raw push, merged/deployed without authorization or PR claimed without URL |
| **P5-B Operations** | Runbook, operator-admin emergency access, cost/alert contact, observed SHA and resource inventory, no source credentials exposed | Only developer memory makes restoration possible |

## Negative test ledger - execute in disposable fixtures / isolated restore

1. **Modified transaction:** change worksheet's ordinary business fields plus dependent lines and verify exact later recovery state.
2. **New attachment:** create real `ir.attachment` test item, ensure binary opens with exact checksum after restore.
3. **Updated attachment:** replace attachment content and ensure old snapshot returns old bytes while later snapshot returns updated bytes.
4. **Deleted record:** delete test row and its linkage; restore older and later points and ensure deletion is not silently undone in later point.
5. **Unchanged 40GB case:** re-run unchanged data; verify stored dedup reuse and measure bytes actually transferred from Odoo.sh, not simply S3 size.
6. **DB-filestore race:** mutate/garbage-collect a referenced attachment between DB capture and file copy in fixture; checkpoint must fail or prove captured exact earlier content, never pass on missing file.
7. **Missing protected chunk:** remove access to a required test chunk and attempt restore; it must fail closed, preserve previous last-good and alert.
8. **Corrupt backup:** change test file bytes while keeping file name; SHA/restore check fails.
9. **Partial upload / crash:** terminate runner before manifest commit; no promoted last-good and safe idempotent restart without destructive overwrite.
10. **Stale native archive:** run same source-time backup at 11,13,15,17; only one unique source recovery point must be counted, gap alarm fires.
11. **Credentials compromised (non-destructive):** simulate writer attempts to DeleteObject/PutObjectRetention/KMS disable, all denied; use canary objects only, not actual production archive.
12. **KMS key survivability:** emergency restore role decrypts protected fixture with preserved key policy; writer cannot schedule deletion or change key policy.
13. **WORM dedup dependency:** protect old common file under new snapshot, simulate old checkpoint aging; old file remains protected through new retention boundary.
14. **Cold tier:** simulated archive/restore of a full >365-day recovery bundle, no latest restore needs Glacier, archived version can be independently retrieved.
15. **Friday/Monday:** next run is Monday 11am; native Odoo backups still run over weekend; report weekday-gap semantics rather than 2h wall-clock RPO.
16. **DST:** single invocation at intended local times across spring/fall; no double job or incorrect UTC static offset.
17. **No external side effect:** restore environment blocks outbound mail, payment, shipping and webhooks; verify logs/controls.
18. **No Odoo.sh in recovery:** revoke/unplug Odoo.sh connectivity during restore; only independent S3/key/source assets used.
19. **Cost runaway:** exceed test budget threshold with synthetic forecast or metric; alarm works and no quiet expansion of cloud resources.
20. **Business document provenance:** original Enterprise Documents ownership and native filestore path still work after restore, including a worksheet containing several distinct evidence files.

## Checkpoint receipt format (private, not a new global/L9 schema)

Per checkpoint, emit fields sufficient for an independent verifier:

```yaml
checkpoint_id: <unique>
run_state: DISCOVERED|CAPTURING|VERIFYING|ADMITTED|FAILED
source_build_id: <observed>
source_db_name: <observed>
source_checkpoint_at: <UTC from DB source, never inferred from job>
source_backup_completed_at: <UTC>
vault_verified_at: <UTC>
source_method: NATIVE_COMPLETED_ARCHIVE|SUPPORTED_READONLY_CONSISTENT_EXPORT
source_archive_sha256: <if relevant>
postgresql_state_sha256: <hash manifest or dump>
filestore_manifest_sha256: <hash of exact referenced content>
filestore_referenced_count: <integer>
filestore_missing_count: <integer>
backup_content_bytes: <integer>
new_upload_bytes: <integer>
reused_bytes: <integer>
protected_object_versions: <private manifest ref>
retention_dependency_closed: true|false
enterprise_software_revision: <exact>
custom_repo_revision: <exact>
operator_status: PASS|FAIL|UNKNOWN|NOT_RUN
restore_witness: <URI of independent evidence or NOT_RUN>
next_action: <minimal bounded action>
```

A receipt is not equivalent to running the restore. Keep sensitive values in private AWS storage, not Git.

## Acceptance states

- `NATIVE_ONLY`: Odoo.sh platform backups exist; independent protection not proven.
- `INDEPENDENT_VAULT_CREATED`: protected AWS resources exist but no actual live full recovery point proven.
- `INDEPENDENT_FULL_RECOVERY_PROVEN`: complete real production backup restored outside Odoo.sh, with correct filestore and code.
- `INCREMENTAL_RECOVERY_PROVEN`: >=2 valid fresh source points, changed/deleted tests, content reuse, complete immutable closure and independent restore observed.
- `TWO_HOUR_OPERATIONAL_PROVEN`: four schedule times producing source-fresh checkpoints, monitored, and empirical <=120 operating-minute RPO in observed windows. Does NOT claim zero future failures; alerts and recovery process remain active.

Status cannot advance by assertion; each transition requires date, source time, exact artifact identities and observed independent evidence. `INDEPENDENT_FULL_RECOVERY_PROVEN` is a valuable outcome even if `TWO_HOUR_OPERATIONAL_PROVEN` is still blocked by Odoo.sh.


## Contract 01 / Infisical additive gates (v1.1)

| Gate | Required real witness | Must fail if |
|---|---|---|
| N0 Native source | Exact live Odoo.sh Production build and native backup listing with observed most recent completed source time | Only staging data or unsupported inferred settings |
| N1 Native configured/verified | Automatic provider-native daily backups actually active; one documented native manual-backup attempt/result; no rate-limit bypass | "Configured" only from a vendor documentation claim or hidden API usage |
| N2 Native restoration | Completed native backup with complete filestore restored to isolated nonproduction target, no outbound effects, actual timings | Any Odoo Production overwrite or missing attachment |
| S1 Secret inventory | Every newly generated persistent secret in scoped Infisical path, identified by reference only; worker can read allowed path and denied other paths | A new secret only in .env, repo, terraform state or broad machine identity |
| S2 Safe nonsecret config | Exact deployed desired settings mirrored in minimal version-controlled IaC/config, sensitive state encrypted outside Git | Hand-configured AWS with no code reproduction or state in commit |
| S3 Infisical-independent emergency access | With Infisical/Odoo.sh disabled, independently controlled recovery principal reads and decrypts a protected test object; full recovery uses independently held assets | Restore depends on fetching a crucial credential from unavailable Infisical |
| S4 AWS KMS key/control separation | KMS material non-exportable, policy and key ARN recovered from private inventory, admin vs writer separation tested | Backup writer has KMS disable/delete/key-admin or secret editor power |
| C1 Provider ownership isolation | Native 01 versus AWS 02-04 versus emergency custody 05 each has separate authority and receipts | AWS executor claims native UI configuration it did not perform |

Test negative scenarios: wrong Infisical env, cross-folder read, expired machine identity, absence of Infisical, leaked nonsecret config accidentally containing credential, auto Odoo backup not present, native manual cap reached, restore target Production misselected (fail before action), and AWS compliance retention + KMS key lost.

## v1.2 contract 00-06 additional mandatory acceptance

| Gate | Real PASS witness | Non-PASS counterexample |
|---|---|---|
| C00 Full ripple closure | Current source/plan enumerates every exact file/resource/permission/owner/test/dependency/exclusion; unrelated code unchanged, new ripples trigger replan before coding | Unknown exact file or service hidden until implementation |
| C02 Infisical owner/consumer | Every new persistent credential's verified Infisical path, scope, rotation and denied unrelated reads; no real secret in public repo/state/log | New token only in local `.env` or AWS user data |
| C05 1Password custody | Authenticated restricted Document *really exists*, item ID, version/digest, independent download hash identical; operator can read and rehearse; no lasting Mac file | Agent printed ZIP to terminal; item inaccessible without Cursor session |
| C05 Self-unlock negative | Actual outside-1Password Emergency Kit/recovery proved to exist without displaying secrets to agent | 1Password Secret Key/account recovery only in locked 1Password |
| C05 Rotation safety | Emergency escrow and operator pack updated/tested after simulated credential change; deliberately stale version recognized as unsafe | Credentials rotated in Infisical and emergency pack breaks |
| C06 No-worker restore | Controlled real restore succeeds with Odoo.sh, Infisical, usual collector and original Mac unavailable; customer data and doc integrity proved | Only simulated test data or operator depends on running developer workstation |
| C06 Owner closeout | All seven receipts PASS with source revisions and no in-scope blockers, actual RPO/RTO/alarms/cost verified, final 1Password packet current | Provider unable to produce 2-hour snapshots but campaign called DONE |

### Full-coverage end states

`CAMPAIGN_DONE` is ONLY the conjunction of D00-D06 in `coordination/DEFINITION_OF_DONE.md`. Partial milestones are valuable but not equivalent. Every blocking issue must identify real outside owner/permission/request, otherwise it remains an in-scope remediation obligation. RPO measured from actual source checkpoint time, not scheduler trigger; last-good source must not advance until immutable closure completes.

### Additional first-year and independent identity counterexamples

- At day 91 simulated, Object Lock's minimum retention elapsed but selected recovery point still survives and is retrievable; at day 366 a selected complete point is eligible for cold tier, not silently deleted. Real lifecycle cannot be shortcut or simulated as deployed history.
- Disable simulated corporate IdP used for normal Odoo/Infisical; emergency AWS and 1Password sign-in still work through proved independent authorized identity/MFA method. If provider/auth topology does not support this, residual availability remains BLOCKED and the final independence claim cannot PASS.

## Post-audit supplemental negative tests and mandatory witness owners

| New gate | Actual PASS witness | Test fails if | Owning contract |
|---|---|---|---|
| R1 Protected release | Independently retrieve the exact deployed DR code/Enterprise/restore dependency artifact from versioned encrypted S3, hash match, reproduce isolated Odoo restore with GitHub and Mac inaccessible | Only open PR/local checkout or floating image tag exists | 02+03, review 06 |
| R2 Early operator pack | After first real full restore, independent operator retrieves/rehearses the complete baseline 1Password document; current resources and last-good checkpoint match | Contract 04 blocker leaves operator with no real emergency pack | 05 |
| R3 Post-optimization pack | After 04 changes worker/role/manifest/schedule, new 1Password version read back, SHA-256 verified, prior known-good version retained until new PASS | Stale 1Password references or missing emergency credentials | 05+06 |
| R4 Isolated account onboarding | Verified company-owned separate AWS account or specifically approved new Organizations member account, documented ownership/MFA/retention cost; deny cross-app credentials | Used normal app AWS account or inferred creation authority from AWS API connectivity | 00+02 |
| R5 Full pack traceability | Every DR-001..DR-048 has one accountable contract and at least one explicit acceptance gate/witness; machine validator rejects removal/mismatch | Invariant exists but has no test or owner | 00+06 |
| R6 Mid-flight provider block | Proven daily independent S3 copy and real operator pack survive; 04 remains BLOCKED_EXTERNAL with precise vendor-capability request and campaign NOT_DONE | False 2h PASS, no emergency instructions, dropped baseline protection | 03+05+06 |
| R7 Independent admission | Ordinary writer writes candidate but cannot change admitted/last-good; separate trusted verifier accepts only fully checked source and retained version references; live IAM denial and canary tests | Writer can forge `last-good`, corrupt candidate becomes admitted or verifier can be assumed by writer | 02+03+04, reviewed by 06 |

These supplement existing gates without superseding them. Synthetic tests do not establish a real AWS/Odoo/1Password restore. Each PASS must name the actual observed source, exact version/time and private evidence reference.


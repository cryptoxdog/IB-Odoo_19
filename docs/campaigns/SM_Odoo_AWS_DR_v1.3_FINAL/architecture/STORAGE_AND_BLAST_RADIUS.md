# Physical design and fully accounted blast radius

**Architecture decision:** Native Odoo.sh remains the primary production platform and built-in recovery service. Scrap Management holds a separate, recoverable, encrypted and immutable AWS vault. AWS is the recovery plane, not a second live ERP or a replacement for `documents.document` / `ir.attachment`.

## 1. Source-to-vault path

```text
Odoo.sh Production                                 Separate Scrap Management AWS account
  Native automatic daily backups (unchanged)
  PostgreSQL + matching filestore
        |  AUTHORIZED READ ONLY: supported native archive and/or
        |  validated read-only, point-in-time export
        v
  Independent on-demand collector --------------> temporary encrypted transfer/cache
                                                      |
                       source-time proof + checksums + database/filestore closure
                                                      |
                           +--------------------------+---------------------+
                           |                                                |
                           v                                                v
                     immutable S3 vault                              recovery manifests
                  baseline / protected chunks                     checkpoints / SHA256
                           |                                                |
                           +--------------------------+---------------------+
                                                      |
                                         independent restore from S3
                                                      |
                                          isolated Odoo 19 Enterprise
```

A backup is `ADMITTED` only when the source-consistent database, all referenced filestore bytes, versions/revisions, integrity and immutability are complete and verifiable. Logs of successful job starts, raw snapshots of individual Odoo rows and transferred byte totals are insufficient.

## 2. Preferred acquisition ladder (proof before assumptions)

**A - Preferred for first proof:** take one real *completed* Odoo.sh native production backup through its documented Backups UI/available SSH artifact, verify it includes PostgreSQL + filestore, transfer and perform independent restore. Its actual creation time controls recovery age. A download of the same daily file at 11/13/15/17 is not four new snapshots.

**B - Preferred for fresh 2-hour proof IF supported and authorized:** From read-only production SSH (or other documented provider-supported surface), produce a transactionally consistent PostgreSQL export at a known point, transfer the referenced filestore as of that point with deterministic checksums and validated relationship closure. Prefer the safest existing provider-native backup generation mechanism if actually available. A PostgreSQL dump plus a concurrently changing directory is not automatically point-in-time consistent: prove append-only/hash-addressed content behavior, existence of every source-referenced binary at the chosen source time, changed/deleted file semantics and a successful restore against real changes. Throttle/observe resource use; no source daemon, Odoo addon, production cron, extension or DB configuration change.

**C - If fresh, consistent B is unavailable:** keep and schedule independent copies of completed daily native backups to S3, prove restore, report `2H_FRESH_SOURCE_BLOCKED` with exact capability missing. Do not pretend Odoo XML-RPC record deltas, `write_date` export, copied `backup.daily` or staging-db dumps are full disaster recovery. Seek provider approval/plan change separately rather than bypass controls.

**No presumption:** Automated creation of native backups via Odoo.sh platform API is NOT established; Odoo's official FAQ states no platform API. Native manual backups have their own daily cap but an exposed manual UI action is not an automation API.

## 3. AWS physical responsibilities (minimum necessary)

| AWS surface | Narrow job / initial design | Security and proof |
|---|---|---|
| **Company-owned backup account** | Vault administration independent of Odoo.sh and ordinary app deployment | Discover actual account ID/region, prove company control and separate admin before mutation |
| **S3 vault bucket** | Encrypted, private, versioned, Object Lock enabled; protected baseline, incremental chunks, checkpoint manifests | Block public access; Compliance retention 90 days for admitted objects; source and routine writer lack delete/retention-shortening privileges; check version IDs |
| **S3 working/cache storage or encrypted EBS** | Temporary acquisition and dedup index/cache ONLY | May be mutable; never the sole location of a committed recovery-point dependency; no business data in plain logs |
| **AWS KMS key** | Encryption/decryption for protected backups and key management separated from writer | Dedicated key admins; backup writer cannot disable, schedule deletion or change policy; independent recovery role can decrypt; test key survival |
| **On-demand worker** | Pull/read, checksum, dedup, commit manifest and verify immutable objects | No always-running service; identity with only required read/write; choose EC2 with persistent encrypted cache if material to avoid full re-transfer, otherwise select simplest measured executor |
| **EventBridge Scheduler** | 4 starts per weekday, time zone `America/New_York`, no overlaps | Start times 11,13,15,17; if previous run active -> fail/alert, never run simultaneously |
| **CloudWatch + SNS or equivalent** | Alert on source freshness failure, incomplete or missing files, late/failed jobs, cost anomalies, IAM policy changes | Independent recipient; failures do not advance last-good checkpoint; protected audit trail |
| **IaC state** | Scoped fresh AWS resources, recoverable owner history | No secrets in state/repo; locked state backend with controlled access; no mutation of unrelated preexisting resources |
| **Independent restore runtime** | Provision only during test or incident | Odoo 19 Enterprise, correct code SHA and dependencies, isolated network and disabled external side effects; secure temporary data deletion after approval |

The exact minimum service choices (for worker and dedup engine) are implementation details, conditional on live source access and measured data volume. Do not create RDS, ECS, DynamoDB, secondary regions, a constant production standby, or extra persistent services just for a diagram. Add only when a falsifying test proves the need. **S3 Object Lock Compliance and KMS key settings create significant irreversibility and cost consequences; inspect account, region, default retention, licensing and budget before committing them.**

## 4. Efficient snapshot construction

- Baseline: preserve one complete independently restorable production point, with original source creation time.
- Filestore: reuse verified identical content based on cryptographic content identity, not filename alone. An Odoo attachment's `ir.attachment.store_fname`, checksum/size and `res_model`/`res_id` cross-check must agree with the restored DB. Preserve exact semantics for renamed files, deletions and updates.
- Database: use a consistent full source baseline and a proven incremental/dedup path. PostgreSQL WAL or CDC is acceptable ONLY if legitimately accessible, continuous enough for every interval, complete for deletes/DDL/sequences and replay verified. Without that, fresh consistent full `pg_dump` per checkpoint is safer; dedup at the backup layer. Do not claim row-only exports are restorable.
- Commit: build new checkpoint manifest in a private temporary state, confirm every referenced byte exists with checksum and retention coverage, record source checkpoint time, only then publish an immutable `admitted` manifest. Last-good changes atomically after verification.
- Integrity: hash recovered raw source and restored bytes; test synthetic data mutations in a disposable Odoo instance and one isolated real-backup restore. Never inspect/emit sensitive customer contents in logs.
- Immutability with dedup: shared chunks may be uploaded once but their retention or legal protection must last through the newest dependent snapshot. The implementation must prove transitive closure on the exact S3 object versions. Routine backup role must have no delete/prune. Do not run a mutable dedup tool's `forget` or `prune` against locked objects without a dedicated, dependency-aware, independently authorized maintenance design.
- Cold tier: only selected independently restorable old recovery points or complete independent archive bundles after >=365 days, including all database, filestore, code and key dependencies. No 365-day lifecycle transition on an old chunk still needed for this week's checkpoint.

## 5. Schedule semantics and measurement

- Config: `cron(0 11,13,15,17 ? * MON-FRI *)` with `America/New_York` and disabled flexible timing window (verify AWS service syntax in deployed IaC).
- Only jobs STARTING at those times; 17:00 job may finish after hours. No duplicate jobs, missed-run silent retries or a cron in Odoo.
- Source checkpoint timestamp, source snapshot completed timestamp, S3 admitted timestamp, recovery elapsed time and successful restore timestamp are distinct.
- Four scheduled tasks do NOT mathematically guarantee <=2h source age around a slow or failed task. Claim <=120 business-minute RPO only when measured gaps and completion behavior support it; alarm when a business-hour window exceeds the target. A failed checkpoint triggers an urgent notice; never shift it to a green future timestamp.
- Keep native Odoo daily backup continuous irrespective of weekday schedule.

## 6. Blast-radius and owner matrix (source/creation/change requirements)

| Concern | Owning surface | Required inspection BEFORE implementation | Permitted planned changes | Explicitly forbidden |
|---|---|---|---|---|
| Existing Odoo.sh backup schedule | Odoo.sh platform | Live Production backups tab, production build identity and history | None; read and verify | Disable/change native backups |
| Acquisition privileges | Odoo.sh authorized production build/SSH | Which account can read complete native archive, DB, filestore; host restrictions; perf | Read-only extraction via supported interface | Vendor platform API invention, writes, agents/daemon on Odoo.sh |
| Transaction/attachment integrity | `ir.attachment`, filestore, PostgreSQL | Native Odoo 19 Enterprise semantics; existing cleanup job and custom Documents bridge | None in Odoo for this recovery work | CRUD on business records, changing native storage owner |
| AWS account/organization | Company-designated AWS | STS caller account/role, region, SCP, cost/budget, preexisting resources | Only new named/taged DR resources in authorized account | Root keys, edit unrelated resources, cross-account role assumption without authorization |
| Vault and cryptography | S3 + KMS | Lock modes, required retention, key lifecycle, IAM ability and costs | IAM/KMS/bucket IaC for DR only | Writer delete/retention admin, KMS deletion by writer, public bucket |
| Runner and schedule | AWS execution service + EventBridge | Source connectivity, executor lifetime, actual transfer size, no daemon support on Odoo.sh | Scoped new worker, scheduler, monitors | Odoo cron or source persistent agent |
| Code and policy | `cryptoxdog/IB-Odoo_19` | `AGENTS.md`, `INVARIANTS.md`, `.cursor` rules, existing `ops/` and infra files at exact HEAD | Prefer *new* `ops/independent_dr/` subtree; minimal pointer in `AGENTS.md`/root invariants if needed | `plasticos_*` addons, account rules, native Documents owners, unrelated CI, sweeping refactors |
| Automated tests | DR-subtree tests + disposable Odoo 19 Enterprise | Current fixture, Odoo.sh download format, actual test access | DR-scoped smoke, unit, integration, independent restore tests | Production restore or sending external mail/webhooks during tests |
| Enterprise / PostgreSQL restore | Isolated AWS restore + license owner | Enterprise source access, Odoo.sh production DB naming, required PostgreSQL compatibility, subscriptions, secrets | Only isolated restore environment | Duplicate live ERP, production failover or Enterprise subscription move now |
| Independent recovery source archives | Odoo.sh-native backup only | Native archive freshness and integrity | Private export and vault upload | CieTrade SQL backup attempts or git upload of source data |
| CieTrade historical extraction | Separate document migration campaign | Out of scope | None | Combining source CieTrade `.bak` or raw document corpus into Odoo.sh system backup as if already imported |

**No code until matrix resolution:** Cursor must name every specific file/addition, cloud resource, permission, caller/consumer, migration, monitoring path and rollback plan under these owners. It may refine *implementation details*, but it cannot silently expand the protected business or source-owner scope.

## 7. Ownership and failure domains

Native Odoo.sh backup: provider-controlled. S3 content + manifests and recovery credentials: Scrap Management-controlled. Odoo operational originals remain native `documents.document` / `ir.attachment`; S3 holds disaster-recovery replicas, not operational attachments or a competing document-authority layer.

A compromise of Odoo.sh must not grant access to delete S3 recovery points. A compromised backup runner must not be able to delete protected data or KMS keys, but it *may* poison new backups; older immutable known-good checkpoints and change/health alerts are necessary to detect and recover from poisoning. A compromised AWS root/KMS admin is still a residual risk; Object Lock alone cannot guarantee availability of encryption keys or of the AWS account.

## 8. Convergence frontier

Decisions locked: scope, schedule, independence, vendor-native continuity, source completeness, dedup intent, immutability minimum, one-year cold-archive threshold and restore proof.

Unknown until P0/P1: actual company AWS account and cost budget, Odoo.sh Production build/backup interface privileges, whether fresh consistent 2-hour source points are supported, whether client can read filestore with acceptable performance, Enterprise restore/license behavior, actual DB+filestore sizes and network throughput. Each is a bounded proof request, not authorization to guess or soften an invariant.


## 9. Original native/AWS ownership boundaries, retained in v1.2

The campaign retains **two distinct provider owners across seven bounded execution contracts**. Native provider backup creation/download/restore are Contract 01's surfaces. AWS vault/KMS/IAM and secrets belong to 02, full off-platform recovery to 03, incremental/schedule to 04, operator emergency custody to 05, and cross-owner closeout to 06. Shared read-only Odoo source proof does not grant AWS contract authority to mutate native settings. Their receipts cannot be substituted for each other.

| New ripple | Owner | Required disposition before code/source action |
|---|---|---|
| Odoo.sh project/build/backup UI, current native automatic schedule/retention | Contract 01, actual Production platform | Verify supported controls and exact native source identity; no fictional hourly native configuration |
| Odoo.sh on-demand native backup action / provider manual cap | Contract 01, native backup UI | Test one supported action within quota; record actual creation time; never overwrite Production |
| Native isolated restore and provider-specific Enterprise rights | Contract 01, disposable recovery target | Disable external effects; prove DB+filestore; no production restore |
| Infisical project/env/folders/machine auth and new secret names | `security/INFISICAL_1PASSWORD_AND_CONFIG.md`, Infisical owner, Contracts 01-05 | Resolve actual scoped existing organization and owner permission; store new secrets, never values in Git |
| AWS STS/IAM, new resource secret bootstrap | AWS IAM and Infisical machine identity | Prefer roles and no long-lived secrets; verify least-privilege; independent escrow for emergency recovery |
| Configuration and IaC remote state | `ops/independent_dr/` safe repo sources, private encrypted state | Enumerate exact files; no Terraform secrets, tfvars or state in Git, ensure reprovisioning works |
| Infisical outage during ransomware response | Independent authorized escrow custody | Prove independent vault read/decrypt and Odoo restore; no circular secret bootstrap |
| Native provider contract and AWS workstream PR/release dependency | Campaign owner plus Cursor-Governance publication interface | Separate receipts/PRs, no competing writes; source evidence precedes real AWS restore claims |

The independent source must be **complete** and consistent at every admitted checkpoint. A native Odoo verified download alone does not establish AWS DR, while an AWS S3 bucket alone is not proof of a recent native backup.

## v1.2 custody/campaign blast-radius expansion (mandatory)

| New concern | Sole owner | Pre-code audit and mandatory planned behavior | Test/recovery effect |
|---|---|---|---|
| 1Password restricted vault, Document and emergency items | `05` + actual operator/1Password account owner | Verify real CLI version, authenticated vault/create/read permissions, independent account recovery, exact item content and retention, off-Infisical only credential escrow; no existing unrelated vault changes | New session/alternate machine retrieval digest, no Mac dependency, bootstrap never self-referential |
| 1Password physical bootstrap | Actual operator/1Password account owner | Verify separately held Emergency Kit or supported organization recovery; C never reads password/Secret Key/MFA | Lost-original-Mac login and actual pack retrieval |
| Infisical secret primary vs 1Password escrow | `02` with `05` custody consumer | New secret owner/path/rotation/access/denial/escrow map, minimum extra secret, no static AWS root keys | `Infisical unavailable` restore and stale rotated secret negative test |
| Repo nonsecret config and paths | Existing `ops/independent_dr/` if current tree confirms | Exact file delta and dependent pointers, no `.tfstate`/real secrets/ZIP/customer bytes in Git or CI | Clean clone/IaC reproduce without original workstation |
| Temporary pack generation | `05`, local authenticated Mac or other authorized secure runner | Prefer streamed/ephemeral generation, Mac never destination; forbid Dropbox/iCloud/Downloads/Desktop, access-scoped temp, cleanup and no false SSD erase promise | File/ACL/audit check and retrieval with source Mac absent |
| Operator ownership and DR packet refresh | `05` + `06` periodic maintainer | Who updates when key/role/license/backup revision changes; verify trusted independent operator access | Quarterly readback/drill and changed-value refresh |
| Final acceptance closure | `06` independent review | Every prior receipt and specific source/permissions/code checked; zero in-scope TODOs; provider unsupported method is blocked, not green | Off-vendor full restore with Infisical and worker unavailable, measured RPO/RTO |

All additions are within the same bounded recovery objective. Each explicit exclusion (PlasticOS addon mutation, permanent ERP, Odoo provider override, CieTrade import) is justified by existing ownership. All changes to exact file inventory after a discovered new ripple require `00` plan reassessment before coding resumes.

## Independent software-release escrow (post-v1.2 closure)

- Add an explicitly owned immutable **recovery software release** containing exact application/worker/restorer code and dependency closure, required Odoo Enterprise source under license, safe IaC and private-state recovery pointers. The deployed code digest must match the independently protected release digest; a GitHub PR or Mac worktree alone is not recovery custody. Test with GitHub, Odoo.sh and original Mac absent.
- Add exact blast-radius owner rows for AWS Organizations member-account creation **if independent company-owned account is missing** (only after explicit account/budget approval), the protected release object/retention, new 1Password baseline upload after first restore, 1Password refresh after 04, and safe lifecycle/cleanup costs of both old and new release versions.
- Protect the working daily known-good recovery and operator pack before deploying experimental two-hour optimizations. Failure of optimization must not erase the company's proven daily protection; release acceptance remains separate and truthful.

## Candidate/admission separation: compromised uploader containment

The AWS backup worker is **not a backup correctness oracle**. It can upload only into a candidate prefix. Separately authorized verifier execution checks candidate source timestamp, DB-filestore closure, cryptographic identity and WORM retention over exact object version IDs, then writes the immutable admitted manifest and last-good pointer through verifier-only IAM. The writer cannot write/overwrite the admitted prefix, assume verifier role or suppress alarms. Count this IAM/policy/verification boundary explicitly in the pre-code blast-radius matrix, including its monitoring, retries, errors and restore consumer.

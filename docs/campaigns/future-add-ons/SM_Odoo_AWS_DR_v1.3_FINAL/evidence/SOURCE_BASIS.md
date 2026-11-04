# Evidence, exact repository observation, and provider capability limits

**Evidence basis as of 2026-10-28.** These sources constrain the contract. Provider links should be rechecked at implementation time; website pages are not credentials or live project observations.

## Existing source ownership

- Repository: `https://github.com/cryptoxdog/IB-Odoo_19` / observed `Staging@78476ddb74861d900992f7f5ec3ec2cc2a63e8bf`.
- Inspected `AGENTS.md`: repository owns an Odoo 19 addon suite and `Staging` integration; publication rule uses Cursor-Governance `make pr` (the global SSOT must be checked fresh before use).
- Inspected `docker-compose.yml`: local test environment persists Odoo data in named `odoo_data` Docker volume, PostgreSQL in `odoo_pgdata`. That is a development environment, not the Odoo.sh production recovery mechanism.
- Inspected `plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md`: native Enterprise `documents.document` / `ir.attachment` own actual original files; `plasticos_documents_native` is the bridge, not a second source of binary authority.
- Inspected `plasticos_base/models/ir_attachment.py`: a scheduled orphan cleanup may remove `ir.attachment` rows if expected filestore file paths are absent. Incorrectly reconstructed filestores can become a destructive operational failure; isolated restore must verify filestore closure before any cron activation.
- No repo-local independent Odoo.sh-to-AWS backup implementation was found from inspection of root `ops/`, `scripts/` inventory at this revision. This is a bounded observation, not a proof no external process exists.

## Odoo official provider statements

1. Odoo.sh Cloud FAQ: `https://www.odoo.sh/faq`. Odoo says production backups every 24 hours, 14 full backups across 7 daily / 4 weekly / 3 monthly, and **no planned Odoo.sh platform API**. Odoo build XML-RPC is not a backup-platform API. FAQ also warns against persistent/daemonized workloads and unsupported long-running source processes. External PostgreSQL read-only access is specifically gated by dedicated hosting.
2. Odoo.sh Branches / Backups: `https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/branches.html` (or same content on documented 18.0 version). Native backups include database + filestore + logs + sessions; up to five manual backups/day (manual UI capability, **not proven automatable**). A downloaded native daily archive is not necessarily a new 11:00/13:00/15:00/17:00 source point.
3. Odoo 19 Odoo.sh Containers: `https://www.odoo.com/documentation/19.0/administration/odoo_sh/advanced/containers.html`. Documented `/home/odoo/backup.daily` and `/home/odoo/data/filestore` paths. Path discovery is not proof of permission or freshness.
4. Odoo forum answer about SSH backup access: `https://www.odoo.com/forum/help-1/can-i-access-odoo-sh-backups-via-ssh-183443`. A user-contributed SSH answer is useful investigative guidance, not a support guarantee or proof of this project's account.
5. Odoo 19 import behavior: `https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/create.html`. Enterprise DB registration/failover rights and restoring off-platform require exact subscription/license treatment. Never assume a backup alone contains licensed Enterprise code or a transferable production registration.

## AWS official provider statements

1. S3 Object Lock semantics: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html`. Compliance mode cannot shorten/delete a locked version during retention; protects a **version**, not the current key name. New versions and delete markers remain possible.
2. Object Lock interactions/key risk: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html`. Object Lock **does not** prevent KMS key loss/deletion. Protected versions may still be hidden behind delete markers. Lifecycle transitions are compatible, but every needed chunk must remain restorable at the intended speed.
3. EventBridge Scheduler DST and time zones: `https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html`. Native `America/New_York` timezone behavior avoids static UTC offsets.
4. S3 Glacier transition and minimums: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html` and `https://docs.aws.amazon.com/AmazonS3/latest/userguide/glacier-storage-classes.html`. Long archive retrieval takes time and incurs storage/minimum duration considerations; not a hot-restore dependency.

## Crucial Unknowns

- Exact Scrap Management Odoo.sh Production project URL, build ID, database name, account permissions and live backup archive history.
- Whether Odoo.sh permits fresh consistent database+filestore retrieval *four times per weekday* unattended, with required performance; no platform API support is currently established.
- Live company-owned recovery AWS account ID, designated region, approved budget, actual role permissions, organizational security policies and existing resource naming collisions.
- Exact Odoo production data volume after historical document import, database size, network throughput, requirements/licenses and actual cost of full/incremental transfer.
- Actual independent restoration time and actual business-hours RPO. Only a real live proof can close them.

## Source integrity and instruction boundaries

These URLs and code observations establish capability constraints, not commands to be run without local authority. Unverified platform features remain Unknown. Do not turn a 2026-10-28 Staging SHA into today's live head. This pack does not carry a producer-validated L9 AuthorityResolution or independent GARReceipt and makes no L9 canonical admission claim.


## Added vendor verification (v1.1, 2026-10-28/29)

- Official Odoo.sh FAQ `https://www.odoo.sh/faq`: production backups every 24h and 7 daily/4 weekly/3 monthly; no Odoo.sh platform management API; read-only remote PostgreSQL on dedicated hosting only. These are platform claims, not verification of this project's live settings.
- Odoo 19 Odoo.sh Branches/Backups documentation: `https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/branches.html`. Backup UI supports list/download/manual/restore; production automatically daily; native backup includes PostgreSQL, filestore, logs, sessions; five manual backups/day; staging/development not automatically backed up. Provider-managed weekly/monthly copies may require Support. UI schedule and controls must be verified on actual project.
- Infisical machine identity documentation `https://github.com/Infisical/infisical/blob/main/docs/documentation/platform/identities/machine-identities.mdx`: scoped machine identities with AWS Auth/other auth; do not assume an already provisioned identity or approved project.
- Infisical Terraform warning `https://infisical.com/blog/how-to-manage-secrets-on-terraform-using-infisical`: secrets passed via Terraform data sources/outputs can still persist in state. Runtime injection avoids state leakage.
- AWS S3 Object Lock `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html`: Compliance mode prevents shortening/deleting locked versions but does not ensure KMS key survivability or protect against logical poisoning of fresh backup content.
- Current target `cryptoxdog/IB-Odoo_19` Staging observed `78476ddb74861d900992f7f5ec3ec2cc2a63e8bf`; repo's `docs/adr/ADR-020-web-lead-inbound-port.md` references Infisical `Cursor-Governance` project for a distinct web-lead secret, demonstrating an existing convention only, NOT permission to use its root for DR.

**Still UNKNOWN:** actual Infisical host/project/path/owner/grants, Odoo.sh actual Production project and privileges, AWS account identity/authorization, required emergency escrow custodian, and any technical route to fresh four-times-daily consistent source points. Contracts must not silently resolve these by guess.

## v1.2 additional provider basis (must verify live at execution)

- 1Password CLI document CRUD, actual `op document create/get` and stdin: https://www.1password.dev/cli/reference/management-commands/document (official, retrieved 2026-10-28/29); use installed `op --help` before execution, do not assume CLI available on user's Mac.
- 1Password CLI item create/get including strict vault selection and avoiding secrets in command arguments: https://www.1password.dev/cli/reference/management-commands/item
- 1Password Emergency Kit and off-1Password account bootstrap: https://support.1password.com/emergency-kit/ (SSO/business accounts may use different supported account recovery, verify).
- 1Password CLI access and identity: https://1password.com/developers/cli and https://developer.1password.com/docs/cli/secrets-scripts
- Infisical machine identities/AWS Auth and scoped permissions: https://github.com/Infisical/infisical/blob/main/docs/documentation/platform/identities/machine-identities.mdx (verify current official owned docs and enabled account methods).

Not observed by ZIP author: user's 1Password CLI installation, vault, login or vault creation authority, actual emergency kit/account-recovery, Infisical role and project, AWS account and permissions, Odoo.sh 2-hour source access. These are real contract-00 discovery gates, not facts from this ZIP.

## 2026-10-28/29 source verification relevant to final pack

- Odoo.sh FAQ `https://www.odoo.sh/faq`: automatic Production backups every 24h, 7 daily/4 weekly/3 monthly; no supported Odoo.sh **platform-management API** announced; external read-only PostgreSQL access only on dedicated hosting. Native automatic backup is provider-managed, not an agent configurable 2-hour setting.
- Odoo Odoo.sh Backups documentation `https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/branches.html`: production Backups UI allows manual point, list/download/restore, with five manual backups/day as documented. This is **manual UI capability**, NOT a proved unattended backup API. Confirm current 19.0 behavior on the live instance.
- Odoo 19 Containers `https://www.odoo.com/documentation/19.0/administration/odoo_sh/advanced/containers.html`: `/home/odoo/backup.daily` and filestore paths are documented but do not prove customer access or a fresh two-hour export.
- 1Password official CLI `https://www.1password.dev/cli/reference/management-commands/document`: `op document create` accepts stdin `-`, `op document get` supports `--out-file`, and the CLI must be tested on the operator's actual authenticated Mac. Never pass secret contents on command-line flags.
- AWS Object Lock `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html`: Compliance mode protects specific immutable *versions*; it can still receive delete markers and does not protect lost KMS keys. Account/retention/cost authorization precedes irreversible writes.
- AWS EventBridge Scheduler `https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html`: named IANA time zones and daylight saving support, but scheduled invocation is not proof of source snapshot freshness.

These are source-owner documentation, **not live Odoo.sh, AWS, Infisical or 1Password inspection**. Independent source/permission/restore checks remain for Cursor execution.

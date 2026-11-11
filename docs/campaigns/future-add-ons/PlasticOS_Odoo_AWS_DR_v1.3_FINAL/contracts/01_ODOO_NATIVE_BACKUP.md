```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```

# CONTRACT 01 | Odoo.sh native production backup and restore assurance

**Campaign:** `SM-ODOO-DR-CAMPAIGN-001` | **Workstream:** `SM-ODOO-NATIVE-DR-001` | **Revision:** 1.3.0
**Objective:** Exercise and configure EVERY vendor-supported native production backup/recovery control available to this project, independently establish a genuinely usable complete production backup, protect native credentials in Infisical, and prove a safe native restore. This is a separate execution contract from the AWS independent-recovery workstream.

## 0. Authorized effects and exact scope

- Operate only on the operator-authorized actual Odoo.sh **Production** project/branch/build and the named **disposable, isolated nonproduction** restore target. Verify all source identities live before acting.
- The operator authorizes supported native actions necessary to create an **on-demand backup** and to verify, download and test a native backup. A backup operation may create a backup artifact/metadata; that is an allowed native backup-control operation, NOT authority to change operational business data.
- Verify native automatic production backup is active and working; inspect provider-supported security, access, backup-list, retention, manual backup, download and restore capabilities. If any genuinely configurable backup setting exists, document its current/desired value and effect, and change only explicitly approved backup settings. Odoo.sh manages automatic frequency/retention; do NOT invent a configurable hourly native schedule, an Odoo.sh platform API, or an unsupported setting.
- Do **not** disable or replace provider-native automatic protection, edit production Odoo records, reload/delete a production database, alter installed addons, PostgreSQL settings, crons, production credentials/roles, DNS, live hosting, subscription or user sessions. Enabling/enforcing MFA or rotating existing identities requires a separately verified operator authorization because it may lock out users.
- Repository writes restricted to the **minimum new scoped `ops/independent_dr/native/` documentation or read-only verification files** and minimal nonduplicating routing pointers under `AGENTS.md`/root `INVARIANTS.md` only where proved necessary. No PlasticOS business-module mutations or copied secrets.
- Read shared `policy/LOCKED_POLICY.yaml`, `policy/INVARIANTS.md`, `coordination/DEFINITION_OF_DONE.md` and `security/INFISICAL_1PASSWORD_AND_CONFIG.md`. Invariants are operator locked. Never rewrite their substance in the execution branch.

## N0 | Full source, owner and blast-radius proof (no mutations)

1. Resolve the exact current `cryptoxdog/IB-Odoo_19` Staging revision and current relevant local rules, the actual Odoo.sh Production project/build/database/backup UI, user access and independent safe restore target. Pin the project/build identity in a **private evidence record**, not in a public PR.
2. Inspect the actual Backups tab and completed recovery-point history, which days are present, bytes/timestamps/revisions, native retention, how restore and download works, and any provider-managed storage warnings or quota. Distinguish a backup file's creation timestamp from download time.
3. Confirm Odoo.sh automatic native production backup is already enabled and current; if not, determine exact provider-support action and block readiness until corrected. Do not assume the 7 daily/4 weekly/3 monthly policy guarantees the project has healthy backups.
4. Inspect the supported native UI or SSH action that can create a manual backup; verify Odoo.sh's per-day cap before triggering. Do not automate a UI control with hidden scripts, session scraping or invented platform endpoints.
5. Inventory new/existing access credentials and all non-secret settings. New persistent credentials go in the correct Infisical environment/path; existing secrets are not copied or rotated without need. Record non-secret source configuration and safe operational procedure in the repo; put sensitive resource identities in private operator inventory.
6. Reconcile **all** owner/source permissions, proposed exact files, backup side effects, native limits, nonproduction restore access, Enterprise software/version requirements, storage/network impact, test isolation, recovery and rollback before any source action or implementation code. Unknown material effects block that action.

## N1 | Native backup configuration and real artifact

1. Using authorized vendor-native controls, confirm/protect the automatic daily backup behavior. Perform allowed provider-native configuration **only where a documented setting is actually exposed**. For provider-managed immutable settings, document `provider-managed / verified`, not fictitious `changed`.
2. Verify at least one genuine recent **completed** automatic Production backup exists and contains the exact PostgreSQL database plus its filestore. Record the source checkpoint time, production branch/revision, native backup identity and download options.
3. Create **one new on-demand Production backup** using the official manual control if permissions/limits allow. Identify this as a native manual backup, not as one of the four automatically scheduled AWS checkpoints. Record start/completion, status, size, source timestamp, actual result and whether its retention differs from the automatic backups. An unavailable button, required permissions, full quota or blocked action must be `BLOCKED`, never silently bypassed.
4. Download or otherwise obtain a completed native backup using a provider-supported method; never choose an option excluding filestore. Validate database payload + filestore presence, expected counts, manifest/checksum and selected business/attachment relations **without publicly exposing real data**. Read/verify only until an isolated test target is fully secured.

## N2 | Safe native restore proof

1. Restore a copied completed Production backup **only to an approved isolated disposable target** using a documented Odoo.sh nonproduction restore route **only if outbound mail, crons, integrations, and external effects can be neutralized BEFORE its first startup**, OR an independently isolated local Odoo 19 Enterprise environment if a safe provider-native target cannot be established. Never use the Production Restore/Import target. A staging restore that can execute production automations before isolation is NOT a safe option.
2. Prove no outbound email, payment, freight, vendor webhooks, jobs or other external side effects; turn off background integrations *in the isolated target* before testing. Avoid handling production secrets in test config.
3. Check that a representative transaction, partner, accounting record, and multiple `documents.document` / `ir.attachment` binaries are present and readable with consistent database relationships, using protected evidence; ensure installed custom addons/Enterprise are correct.
4. Preserve a complete independently repeatable vendor-native restore runbook with real measured duration and exact missing dependencies; record any limits imposed by Odoo.sh. Do not claim provider-native restoration proven if only the download succeeded.

## N3 | Contract closeout and downstream AWS handoff

- Deliver private `NATIVE_BACKUP_EVIDENCE` with Production source/build identity, verification timestamp, actual native backup list including creation times/retention, auto backup state, one manual backup result, verified download artifact checksum/byte size, restore witness, elapsed time, authorized native configuration actions, Infisical references and sanitized config pointers.
- Record factual native capabilities as **one of:** `NATIVE_VERIFIED`, `NATIVE_CONFIGURED_AND_TESTED`, `PARTIALLY_VERIFIED`, `BLOCKED`. These are project-local evidence labels, not canonical L9 receipt states.
- Hand the real **source acquisition method, auth boundary, artifact format and last-good native backup timestamp** to Contract 03. Contract 02 may configure only the independent vault and identities. Without this evidence, Contract 02 may configure and test synthetic vault resources, but Contract 03 may NOT claim a real independently recoverable production backup.
- Make only a scoped repository PR, if any repository files change, through the owner-verified `make pr` publisher. No raw push, direct PR creation, merge or Odoo.sh Production deploy. If no code is needed, a platform-native verification/restore receipt may close this contract without forcing a decorative PR.

## Native negative tests

Missing day / last backup is stale; manual daily quota reached; staging database mistaken for Production; download without filestore; download timestamp mistaken for source time; wrong backup revision; Odoo.sh restored into Production by mistake (must be prevented before action); test target emits mail/webhooks; Infisical unavailable to the recovery operator; old restored attachment cannot be opened; actual native capability marked as `configured` without evidence.

## Output and fail-closed semantics

Report each N0-N3 obligation as `PASS | FAIL | BLOCKED | NOT_RUN` with timestamp, owning source, exact witnessed evidence and minimal blocking dependency. Never change provider-managed backup frequency or retention on the user's behalf if no setting exists. No completion claim until a real current native backup and isolated restore are witnessed. No AWS resource creation belongs to this contract. The only PASS is actual native completed backup and safe restore with real evidence; unresolved in-scope work blocks closure. Complete the checked Infisical inventory, operator handoff and non-production cleanup as part of this same contract. Emit the shared slice receipt; exact source pointers can be private, never user/customer data in Git.

## v1.2 no-loose-end closure amendment

- Consume the `00` source/permission/blast-radius receipt and prove its live applicability; update the owner matrix on any new ripple before acting.
- Remove all temporary nonproduction credentials, disable incidental external integrations, reconcile source times and observed filestore closure, record whether the native restore target was destroyed or intentionally retained at approved cost.
- Finish every native security and documented backup setting that is **actually configurable** before PASS; provider-managed schedule/retention is a verified fact, not a changed option.
- Hand off a machine-checkable native-source record to `03`, including complete file format and the documented rights to re-acquire a production point. Contract 01 owns no AWS role, 1Password Document or long-running custom job.
- Mark `BLOCKED_EXTERNAL`, not PASS, if the current native restore cannot be run due to a genuine support/permission/license block. Keep safe source inventory and exact vendor capability request.

## Contract 01 handoff hardening

- Publish one authoritative native-source receipt that proves backup generation time rather than file download time, payload format and filestore presence, and the authorized repeatable acquisition procedure. An undocumented path or shell availability alone is not an approved automated source.
- Native provider-managed backup cadence and retention are **verified**, not configured, unless Odoo.sh exposes a real supported setting. If an allowed backup-control change is actually made, independently re-read the provider UI and perform a rollback feasibility assessment. Never mutate production business data.
- Contract 01 does not perform the AWS restore or claim the four source-fresh weekday points. It must provide Contract 03 with an actual completed production-native backup even if Contract 04's higher frequency is later blocked.

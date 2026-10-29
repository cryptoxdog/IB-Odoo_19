# Invariant-to-acceptance witness ledger | Local policy coverage v1.3.0

Every case is a **required execution witness**, not an assertion that the underlying production system has passed. Each case has exactly one accountable contract, a primary gate named in `evidence/ACCEPTANCE_MATRIX.md`, and the negative case that must be rejected. Machine-check the complete ledger with `tools/validate_campaign_pack.py`.

### TI-001 | DR-001 | Contract 01 | Gate N1

**Required PASS witness:** Independent recovery must supplement, never disable, replace or silently reconfigure native Odoo.sh production backups.

**Fail if:** Native production backup policy changes or backup status becomes inaccessible.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-002 | DR-002 | Contract 03 | Gate P2-A

**Required PASS witness:** Copies required for emergency restore, decryption keys, the recovery code/artifacts, and restore credentials must remain under Scrap Management control, usable without Odoo.sh connectivity or approval.

**Fail if:** A recovery test requires Odoo.sh to provide a missing byte, key, code dependency or credential.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-003 | DR-003 | Contract 03 | Gate P2-A

**Required PASS witness:** Each admitted checkpoint represents one internally consistent database state and its exact referenced filestore versions; retain exact code/dependency/configuration coordinates separately.

**Fail if:** New/updated/deleted record or attachment references cannot be reconstructed at the checkpoint time.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-004 | DR-004 | Contract 04 | Gate P3-B

**Required PASS witness:** Record-level export or `write_date` alone is NEVER a disaster-recovery backup; a changed parent without dependent rows, deletion/tombstone, sequences, or other durable database state is incomplete.

**Fail if:** Restored PO/SO/transaction relations or deletions disagree with source checkpoint.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-005 | DR-005 | Contract 04 | Gate P3-D

**Required PASS witness:** Reuse previously protected bytes when content hashes match; don't re-upload unchanged content just to create another snapshot. Preserve separately each exact recovery point and its manifest.

**Fail if:** Identical immutable data repeatedly stored without justified platform limitation, or dedup changes file identity/contents.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-006 | DR-006 | Contract 04 | Gate P3-C

**Required PASS witness:** For every protected snapshot, all required chunks/files, database archive, manifests, code metadata and decryption keys must remain available for at least that snapshot's protected lifetime. Never prune or cold-tier a live dependency.

**Fail if:** Deleting/archiving an older object breaks any newer checkpoint restore.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-007 | DR-007 | Contract 02 | Gate P1-B

**Required PASS witness:** Production Odoo credentials and the backup writer cannot delete backup versions, bypass or shorten retention, deactivate independent alerts, administer encryption keys, or grant themselves vault-admin powers.

**Fail if:** A backup-runner credential can alter or destroy a protected checkpoint or key.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-008 | DR-008 | Contract 02 | Gate P0-B

**Required PASS witness:** Vault IAM/bucket/KMS administration is isolated from Odoo.sh and ordinary application credentials. Protect against compromised Odoo accounts and compromised production runners.

**Fail if:** Odoo admin/session or runner principal can administer the independent vault.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-009 | DR-009 | Contract 03 | Gate P2-A

**Required PASS witness:** `PROVEN` requires a successful independent full restoration of the selected source point into Odoo 19 Enterprise with checks for records, attachments, deletion semantics, ACLs and disabled outbound integrations.

**Fail if:** Only object upload/hash, `pg_restore --list`, test-fixture restore, or vendor-side restore was exercised.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-010 | DR-010 | Contract 04 | Gate P4-A

**Required PASS witness:** Independent jobs START Mon-Fri at 11:00, 13:00, 15:00, 17:00 `America/New_York`, with daylight-saving handling and a no-overlap lock. Native Odoo daily backups continue outside that schedule.

**Fail if:** A weekend/night independent trigger starts, a job overlaps, or DST triggers twice. Jobs may complete after 17:00.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-011 | DR-011 | Contract 04 | Gate P4-B

**Required PASS witness:** Track immutable `source_checkpoint_at`, `source_backup_completed_at`, `vault_verified_at`, `restore_verified_at`; calculate age from the source checkpoint, not job start or file upload time.

**Fail if:** An 11:00 re-download of an earlier native backup is reported as an 11:00 recovery point.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-012 | DR-012 | Contract 04 | Gate P4-B

**Required PASS witness:** <=2 operating hours is a target, not a guarantee. Admit the target only when actual source snapshots, transfer latency, missed-job behavior and monitored results support it.

**Fail if:** Dashboard reports green from triggers alone, a failed/stale backup, or a source snapshot older than the claimed RPO.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-013 | DR-013 | Contract 00 | Gate P0-A

**Required PASS witness:** Backups obtain data read-only through authorized Odoo.sh interfaces. No production Odoo modules/fields/cron, database settings, schema, mail, posting or stock changes to support acquisition without separate authorization.

**Fail if:** Any backup step writes to operational Odoo records or installs a persistent backup daemon on Odoo.sh.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-014 | DR-014 | Contract 03 | Gate P1-C

**Required PASS witness:** Failed/partial/corrupt/stale copies never become the latest recoverable checkpoint. Persist per-run evidence, hashes, file counts, checks, gap reason and alerts.

**Fail if:** A partial upload is shown as successful or silently advances last-good.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-015 | DR-015 | Contract 02 | Gate S1

**Required PASS witness:** Never store secrets, live business exports, customer attachments, private keys or unredacted production manifests in Git, logs, chat or public buckets.

**Fail if:** Sensitive bytes appear in a commit, public S3 ACL, telemetry or deployment log.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-016 | DR-016 | Contract 04 | Gate P3-C

**Required PASS witness:** After >=365 days, archive only selected self-contained checkpoints or sets with proven full dependency closure; keep all dependencies of recent points online at the required restore speed. Live business file age does not cause deletion/tiering in Odoo.

**Fail if:** A recent restore blocks on Glacier or a monthly archive is missing its historical chunk.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-017 | DR-017 | Contract 00 | Gate P0-B

**Required PASS witness:** Before cloud mutation, bind exact AWS account/region/role, least privilege, owner/tags, estimated recurring cost, retention liability and a cost alarm. Do not modify unrelated AWS resources.

**Fail if:** Unknown account, uncontrolled spend, root credentials or changes outside declared resource scope.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-018 | DR-018 | Contract 00 | Gate P0-C

**Required PASS witness:** Before implementation, account for all affected repository files, external cloud resources, Odoo.sh access, dependencies, schedules, IAM/KMS, security, cost, restore/license requirements and failure/rollback paths. No code until the dependency/effect matrix is reconciled.

**Fail if:** A hidden required permission, side effect, owner or file appears only after writing the implementation without a documented plan.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-019 | DR-019 | Contract 03 | Gate P2-B

**Required PASS witness:** Restore tests may use synthetic data or protected real backups only inside isolated nonproduction environments with outbound mail/payment/shipping/webhooks disabled. Production restore, DNS switch or subscription reassignment require a separate incident/operator decision.

**Fail if:** Test restore emits customer mail or modifies live Odoo/DNS/subscription.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-020 | DR-020 | Contract 06 | Gate C06

**Required PASS witness:** Source presence, CieTrade corpus success, a ZIP, passing unit tests or an untested Terraform plan cannot substitute for observed Odoo.sh source capture + independent AWS restore.

**Fail if:** A delivery claims `COMPLETE` without exact dated restore evidence.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-021 | DR-021 | Contract 02 | Gate S1

**Required PASS witness:** Every newly generated persistent DR workload credential, private key, password and bearer secret (excluding 1Password account login and AWS KMS nonexportable material) is entered into the authorized Infisical project/environment/folder before use, with owner, scope, rotation and tested retrieval. Prefer zero static AWS keys.

**Fail if:** A newly generated secret exists only in a local `.env`, Git, Terraform state or worker; secret is untracked in Infisical.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-022 | DR-022 | Contract 02 | Gate S2

**Required PASS witness:** Safe non-secret configuration, schedule, AWS/IAM/KMS/S3 definitions, consumer pointers and native-backup procedures are documented in version-controlled source. Sensitive runtime/deployment state is encrypted separately; no secret values or customer data are committed.

**Fail if:** AWS is hand-clicked with no reproducible source, or a secret/runtime state is committed.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-023 | DR-023 | Contract 03 | Gate S3

**Required PASS witness:** A tested, independently controlled sealed break-glass recovery path preserves minimum AWS vault-read/KMS-decrypt/Odoo restore access when Infisical, Cursor, Odoo.sh and the normal runner are unavailable.

**Fail if:** Emergency S3 restoration needs a token retrievable only from the unavailable Infisical instance.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-024 | DR-024 | Contract 06 | Gate C1

**Required PASS witness:** Provider-native backup verification, a supported native manual checkpoint and a safe native restore belong only to Contract 01. AWS vault/identity, full restore, efficient scheduling and recovery custody belong to Contracts 02-05; Contract 06 integrates evidence without taking over owners. Each boundary has a separate receipt.

**Fail if:** AWS executor silently alters native production settings or native executor creates cloud infrastructure.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-025 | DR-025 | Contract 01 | Gate N0

**Required PASS witness:** A native backup readiness claim requires observed Odoo.sh Production project/build/database identity and actual completed full database+filestore backup with source time and revision, not a staging/dev backup or download-time guess.

**Fail if:** An agent reports protected Production while it only inspected staging or an empty backup listing.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-026 | DR-026 | Contract 01 | Gate N1

**Required PASS witness:** Verify and exercise only genuine Odoo.sh native backup controls. Provider-managed cadence/retention is recorded as verified, never falsely marked configured. One manual backup may be requested under official UI/access limits; no invented API or script bypass.

**Fail if:** Claims hourly native scheduling via an undocumented endpoint, or attempts hidden UI scraping.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-027 | DR-027 | Contract 01 | Gate N2

**Required PASS witness:** Native restoration proof occurs only in an isolated approved nonproduction target with external side effects disabled; never restore/import over live Production.

**Fail if:** A backup test overwrites production records or delivers external emails, payments or shipping actions.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-028 | DR-028 | Contract 02 | Gate S4

**Required PASS witness:** For every secret and configuration entry record unique owner, storage, consumer, privilege, rotation/recovery and test; do not create a competing secrets authority or duplicate provider-managed settings locally.

**Fail if:** A recovery secret has no owner, or a backup writer can change Infisical DR admin secrets or KMS administration.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-029 | DR-029 | Contract 02 | Gate S2

**Required PASS witness:** Deployed infrastructure state and outputs, when used, are encrypted, access-scoped, versioned and recoverable outside Git; secret values must not be persisted in the state.

**Fail if:** `.tfstate`, credentials or sensitive deployment inventory appears in repo/CI artifacts, or a re-provisioning test cannot resolve state.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-030 | DR-030 | Contract 06 | Gate C06

**Required PASS witness:** Native verification, AWS protected vault, off-Odoo restore, incremental proof, 1Password custody and two-hour operational proof are separate gates; a succeeding phase cannot inherit a missing predecessor witness. Code changes use bounded, verified publisher, no merge/cutover.

**Fail if:** A native backup created is described as independent AWS ransomware recovery, or AWS vault exists without restoring production.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-031 | DR-031 | Contract 05 | Gate C05

**Required PASS witness:** The emergency recovery package is *actually created and verified* in the restricted company-controlled 1Password vault, with recorded document/item IDs, not merely mentioned in a runbook. Operator-specific access must be tested.

**Fail if:** No live `op document` result; item cannot be found/retrieved from authorized vault or was placed in a shared/general vault.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-032 | DR-032 | Contract 05 | Gate C05

**Required PASS witness:** 1Password sign-in recovery information and required MFA recovery method must exist under independent operator custody OUTSIDE 1Password. 1Password content may not be its own sole unlock method.

**Fail if:** Operator loses all devices and cannot sign in without an item stored only in locked 1Password.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-033 | DR-033 | Contract 05 | Gate S1

**Required PASS witness:** Infisical remains runtime SSOT for all new persistent secrets; 1Password holds only the minimal intentional emergency escrow and recovery document, with owner/revision/rotation mappings to Infisical.

**Fail if:** A routine worker reads passwords from 1Password, a new secret is missing from Infisical, or copied escrow is stale with no rotation rule.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-034 | DR-034 | Contract 05 | Gate C05

**Required PASS witness:** With verified 1Password custody, no long-lived recovery pack is placed on Mac, Dropbox, iCloud, Git, shell history or worker storage. If operator explicitly approves a Mac fallback, it must be encrypted, private, off-sync, access-checked and its custody recorded.

**Fail if:** A secret ZIP remains in ~/Dropbox, ~/Library/CloudStorage, iCloud-synced Documents or an unencrypted desktop folder.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-035 | DR-035 | Contract 05 | Gate C05

**Required PASS witness:** The emergency package contains tested operator instructions, last-good checkpoint selection, AWS/KMS/IAM recovery paths, IaC/state and code provenance, vendor rights, contact/escalation path, safe restoration and integrity/verification steps.

**Fail if:** Recovery requires Cursor's memory, current repo availability or undocumented commands/identities.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-036 | DR-036 | Contract 05 | Gate C05

**Required PASS witness:** A separate operator-authorized session must re-download the exact protected 1Password document, verify SHA-256 and open/rehearse its steps without relying on the creating CLI session.

**Fail if:** 1Password upload says success but download fails, bytes differ, or only the agent can access the vault.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-037 | DR-037 | Contract 05 | Gate C05

**Required PASS witness:** Any transient generation uses an isolated, nonsynced, owner-only encrypted or memory-backed workspace and authenticated CLI, with logs/history/process args/OS metadata protections. Completion confirms cleanup and records remaining forensic limitations; never claim guaranteed SSD deletion.

**Fail if:** Secrets are echoed, written to persistent synced directories, included in CI/state or left in world-readable temp paths.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-038 | DR-038 | Contract 06 | Gate C06

**Required PASS witness:** Independent restore is rehearsed without Odoo.sh, Infisical, normal backup worker, Cursor session and original Mac; authenticated 1Password access plus AWS/KMS control must still suffice.

**Fail if:** A restore step needs an Odoo/Infisical token, a deployed worker secret or a file remaining only on the Mac.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-039 | DR-039 | Contract 06 | Gate C06

**Required PASS witness:** Every slice finishes its own code/config/secrets/tests/alerts/cost/cleanup/handoff and publishes an evidence-bound receipt; unresolved in-scope items prohibit PASS. Genuine externally owned blocker is named and campaign remains NOT_DONE.

**Fail if:** A contract says DONE with a TODO, missing test, missing credential owner or silent postponed work.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-040 | DR-040 | Contract 06 | Gate C06

**Required PASS witness:** Campaign DONE requires every mandatory slice PASS, observed native restore, independent AWS restore, valid fresh and incremental scheduled checkpoints, 1Password custody/retrieval and adversarial rehearsal. No partial milestone or PR may substitute.

**Fail if:** Vault exists but no scheduled fresh point, or four jobs run but no real restore, yet DONE is declared.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-041 | DR-041 | Contract 06 | Gate C06

**Required PASS witness:** Any change in Odoo build/source, backup method, IAM/KMS, 1Password escrow, retention policy, software revisions or restore implementation invalidates specifically dependent proofs until rerun.

**Fail if:** Old PASS receipts are reused after materially changing the source or security configuration without compatibility proof.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-042 | DR-042 | Contract 05 | Gate C05

**Required PASS witness:** Every access route and secret has a named owner, expiry/rotation process, Infisical secret ID reference, emergency escrow refresh procedure and live access test, including disabled credential scenarios.

**Fail if:** Credentials rotate while the emergency package still references revoked values.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-043 | DR-043 | Contract 04 | Gate P4-B

**Required PASS witness:** A 2-hour schedule is not a 2-hour RPO guarantee. Source capture and upload delays, 09:00-11:00 gap, Friday-to-Monday window, and overnight mutations must be measured or explicitly excluded, and failures trigger alerts without fake success.

**Fail if:** A clock trigger alone proves SLA, the 11 AM point is not yet retrievable, or an overnight change is silently claimed covered by the independent schedule.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-044 | DR-044 | Contract 04 | Gate P3-C

**Required PASS witness:** Only source-point-consistent, standalone historical archives older than 365 days may transition cold after trial restore and complete dependency/crypto closure; recent points stay hot.

**Fail if:** A recent restore needs a Glacier-only object or the archive depends on a deleted dedup chunk.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-045 | DR-045 | Contract 05 | Gate C05

**Required PASS witness:** A policy/key/role/license/backup-method/version change must trigger a refreshed 1Password recovery document, restored re-check and removal/retirement of obsolete instructions; quarterly review is mandatory.

**Fail if:** Live AWS identities and documentation diverge or old recovery secrets are trusted indefinitely.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-046 | DR-046 | Contract 04 | Gate P3-A

**Required PASS witness:** No unverified private Odoo API or unauthorized SSH/SQL extraction may satisfy the source checkpoint schedule. If source access cannot produce fresh consistent points, exact provider/plan blocker remains open and campaign is not DONE, while safe partial protection proceeds.

**Fail if:** Re-downloaded nightly backups presented as four fresh captures, or an unsupported Odoo method silently deployed.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-047 | DR-047 | Contract 05 | Gate C05

**Required PASS witness:** Emergency 1Password access and AWS IAM/KMS recovery must not depend on the same compromised Odoo/Infisical/worker identity or on a single unavailable IdP, with required MFA under separate custody. Prove an alternate lawful auth path.

**Fail if:** Both 1Password and AWS recovery access require the disabled SSO/IdP, or possession of the 1Password document alone grants unscoped AWS administrator powers.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-048 | DR-048 | Contract 04 | Gate P3-C

**Required PASS witness:** Selected archival checkpoints must remain accessible through their first 365 days and beyond for explicitly retained cold archive; a 90-day Object Lock minimum is not a 365-day retention policy. Never silently delete a checkpoint at the end of WORM retention.

**Fail if:** All selected monthly/yearly archive checkpoints expire before reaching cold eligibility, or cleanup automatically deletes the last independent historic checkpoint.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

### TI-049 | DR-049 | Contract 02 | Gate R7

**Required PASS witness:** The routine backup writer may submit candidate bytes only; a separately authorized verifier must validate source-time, integrity, complete dependency closure and immutable retention before it alone publishes an admitted manifest and advances last-known-good. The writer cannot promote its own backup or alter the admission index.

**Fail if:** A compromised writer changes `last-good` or creates a forged admitted manifest without independent verification, or a corrupt candidate becomes the selected recovery point.

**Execution evidence:** exact source/version/time, safe proof reference, negative-test outcome, and independent verifier/restore witness where the rule requires one. Not established by this design-pack check.

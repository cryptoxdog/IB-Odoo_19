# Scrap Management | Independent restore and incident operation

**Purpose:** Return Odoo 19 Enterprise service from solely Scrap Management-controlled AWS assets when Odoo.sh is unavailable or compromised. This is a DESIGN RUNBOOK, not a performed restore, and it never authorizes production DNS or billing cutover without the incident operator.

## Emergency entry checks

1. Treat compromised production credentials, source database and latest backups as potentially untrusted. Declare an incident; preserve existing evidence. Revoke/suspend ordinary production integration credentials with appropriate authority; do not run suspect code in recovery.
2. From a separately secured operator machine, authenticate to the isolated AWS recovery account with MFA and emergency read/decrypt roles; require no Odoo.sh login. Verify AWS audit trails and integrity of vault/KMS permissions.
3. List immutable checkpoint manifests by **actual source checkpoint time**, integrity status, retention coverage and available required object versions. Choose last known-clean checkpoint, not necessarily newest. Confirm malware/unauthorized changes do not predate the candidate restore point.
4. Confirm license rights for an emergency Odoo Enterprise instance and obtain exact frozen code revisions/dependencies/configuration/secret recovery envelopes under company control.

## Isolated reconstruction

5. Provision a fresh private, isolated Odoo 19 Enterprise recovery environment from saved IaC (Odoo Community + Enterprise + PlasticOS custom modules at exact archived SHA; correct supported PostgreSQL version and Python dependencies).
6. Disable all external side effects BEFORE Odoo initialization/use: outbound mail, payment posting, shipping updates, webhooks, cron, scheduled jobs, public website access, OAuth callbacks and remote service credentials. Keep test credentials isolated.
7. Retrieve and verify immutable S3 checkpoint manifests and every referenced object/version. Decrypt under emergency role; verify hashes, counts, point-in-time DB/filestore closure, archive corruption and full dependency availability. S3 Glacier objects must be staged/retrieved before restore if the chosen checkpoint requires them.
8. Restore database into a new private PostgreSQL DB, then restore exactly its matching filestore under correct Odoo data_dir/filestore/dbname. Restore any required ancillary state under evidence-controlled rules. Do not restore the current compromised config or external secrets blindly.
9. Start the matching Odoo Enterprise instance in restricted mode. Verify registry initialization, expected installed modules, important schema/upgrade compatibility and access controls. Log exact source and code coordinates.

## Acceptance probes (must be observed)

10. Verify one partner/contact, purchase and sale orders, worksheet transactions and their relationships, account moves, history, record creation/update/deletion semantics, attachment counts and a sample of file SHA-256 hashes. Inspect multiple invoice/BOL/photo/email originals through native Enterprise Documents, not just SQL table row counts.
11. Reconcile totals for business records and filestore references with the chosen checkpoint; missing required attachments, corrupt chunks, incorrect Enterprise module revisions, permission failures or unexpected code changes fail the restore test.
12. Verify no emails, financial postings, stock changes or external webhook calls were emitted during testing. Obtain independent read-only review of the restore evidence and actual elapsed recovery time.
13. If the test fails, do not announce recovery or alter production DNS. Identify smallest missing blob/key/version/dependency, select earlier clean checkpoint or fix isolated environment, repeat entire proof.

## Promotion boundary (separately authorized incident action)

14. Only with explicit incident authority, plan new domain/DNS ingress, reverse proxy, credentials, enterprise subscription reassignment, user access, outbound email and third-party integration reactivation. Document cutover time and necessary catch-up for post-snapshot transactions (a business process, not a fabricated automatic recovery).
15. Before reopening writes, run smoke tests, confirm source system was isolated to prevent split-brain, then selectively restore integrations after security validation.
16. Keep original Odoo.sh and vault data unchanged for investigation until the incident retention owner permits cleanup. Record final RTO/RPO and lessons; refresh known-good immutable backup after the clean recovery environment becomes authoritative.

## Scheduled test cadence

- At bootstrap: one complete real, independent restore proof before declaring full DR.
- After incremental method: two different source checkpoints, including modified/deleted data and an unchanged historical attachment, restored and reconciled.
- After weekday scheduling: at least one actual scheduled checkpoint independently restored.
- During operation: automatic per-run archive/hash/dependency checks, monthly sample restore/validation and quarterly full isolated recovery drill. Confirm Enterprise credentials and KMS key recoverability each time.

## Important failure boundaries

- Odoo.sh native backups remain enabled and separate; this runbook does not need vendor access at *restore time*.
- `backup.daily` timestamps and source data are not guaranteed fresh at four weekday times; use recorded source time.
- Object Lock protects locked S3 object versions against deletion/overwriting but not KMS key deletion, account closure, poisoning of new uploads or loss of independent software/licensing access.
- Historical CieTrade extraction files not yet imported into Odoo are not part of an Odoo filestore restore. Preserve their private archive under its separate owner.

## Proof record (fill on actual run)

- UTC start/end, source checkpoint id/time, AWS account/region, Odoo source build ID, DB name, object version IDs and encrypted key ID.
- SHA-256 and count checks for DB/filestore, custom git revision, Enterprise version, restoration target instance, actual running Odoo smoke evidence, side-effect controls.
- Independent verifier identity and PASS/FAIL, data loss measured in operating minutes, elapsed RTO, remaining Unknowns and escalation path.


## Native backup source and emergency secrets continuity

Contract 01 must first identify the **actual native provider source timestamp** and real backup artifact. Contract 03 acquires and protects the actual independent copy, but must not represent a daily backup re-downloaded at noon as a noon source checkpoint. To recover during an Infisical outage, the emergency operator must use an independently approved sealed escrow and separate AWS role/key-policy access. Do not rely on Odoo.sh, Infisical, Cursor cloud-agent tokens or a deployed backup worker being online to obtain decryption/recovery permission.

Emergency runbook must reference the public-safe IaC source revision and protected private deployment inventory, the encrypted versioned infrastructure state, known-good S3 object version IDs, key ARN, correct Odoo source revision/licensing, runtime configuration and the verified out-of-band authentication procedure. Restore with outbound business integrations disabled; verify filestore and actual business records before incident-authorized cutover. Never put actual secrets in the runbook.

## v1.2 owner-owned emergency packet and clean-room dependency

The practical starting point in a real incident is the restricted company 1Password Document `SM-ODOO-DR-EMERGENCY-PACK`, not the agent's repo or Mac. Account login/bootstrap must be separately held outside 1Password. The operator can read verified S3 manifest references, determine a last-known-clean source point, obtain independent AWS IAM/KMS access and protected pinned code/Enterprise dependency archive, and follow documented restore tests without Odoo.sh or Infisical. 1Password is for bootstrap/runbooks and minimal emergency secrets, **not** for the database/filestore backup itself. If an operator cannot retrieve the pack from an authorized alternate session, no emergency capability can be claimed.

During replay, verify missing filestore data and poisoned snapshots fail closed; use an earlier known-clean point when necessary. Only after the isolated test reaches actual Odoo Enterprise document/transaction parity and proves no external effects may an incident owner authorize live cutover separately. Review operator pack and its 1Password content/hash every quarter and on every material resource/secret change.

## Git-host and original-device absence is a test case

A source-code PR is NOT a backup. Before declaring recovery independent, prove restoration with the current Git host, Odoo.sh, Infisical, normal backup worker and original Mac all inaccessible. Recover tested source/dependencies, runtime/IaC state and installation commands from the protected release artifact using emergency AWS access referenced by the 1Password Document. A service that boots only when a Git branch or third-party package repository is available is not a fully self-sufficient recovery drill; record and close material external dependencies before PASS.

After Contract 03's baseline proof, create and independently retrieve the 1Password recovery pack before attempting efficiency upgrades. This protects a real daily recovery capability even if Contract 04's two-hour Odoo.sh source remains unsupported. Later changes must refresh the emergency document and require another clean-room retrieval test.

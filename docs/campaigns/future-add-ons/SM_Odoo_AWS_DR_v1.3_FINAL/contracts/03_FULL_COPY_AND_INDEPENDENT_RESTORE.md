```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```


# CONTRACT 03 | First complete real backup, S3 admission and AWS-only restore

**Mission:** SM-DR-03-FULL-RESTORE | **Owner:** first genuinely recoverable Odoo source point outside Odoo.sh. Consume the real native source proof (01), vault/secret/identity receipt (02) and source eligibility (00). Does not authorize production Odoo record writes or a production cutover.

## Acquire only a full, consistent real Production point

- Use only the 01-proven Odoo.sh-native completed backup/archive or independently provider-supported equivalent. Record its REAL `source_checkpoint_at`, source DB/build, Odoo Enterprise/custom module revision, backup completion and download time separately. Reject a backup excluding filestore. A dump copied during live filestore mutations is not automatically consistent; prove exact referenced byte/version closure.
- Determine complete database/filestore inventory, `ir.attachment` references, store_fname/size/checksum and exact backing file hash; verify PostgreSQL dump is intact and required external code/dependency/version/config is accessible under Scrap Management control. Preserve source file deletion semantics and sequences. Do not store live DB data in logs or Git.
- Transfer through a private encrypted ephemeral channel/cache to new protected S3; hash and compare content and manifest. Record exact object version IDs/retention/key and proof that protected contents are readable under independent emergency principal. Do not promote last-good until all bytes, decrypt, manifest, code and dependency closure pass.
- Prefer a supported completed native backup for first success, **even if it is daily**. This closes independence from vendor; it does NOT close two-hour freshness, deferred to 04. Preserve current native Odoo backup policy unchanged.

## Reconstruct from independent custody

- Provision the minimum on-demand, private isolated Odoo 19 Enterprise runtime matching the original DB/PostgreSQL/filestore/custom/Enterprise module versions and requirements. Reproduce exact code from an independent pinned artifact/reference, not a floating branch or live vendor download at restoration time; verify license-compatible recovery path.
- Cut off outbound SMTP, payments, carriers, webhooks, website, cron and automatic business writes **before boot**. Never use live production credentials or restore over production.
- Simulate unavailability of Odoo.sh and Infisical and the normal collector. Use only independent S3, KMS/role emergency access, independently held required software assets and verified minimal secrets recovery. 1Password pack is formally assembled in 05, but emergency escrow prerequisite belongs to 02 and must already be usable or this test fails.
- Inspect a representative contact, worksheet transaction, PO/SO, accounting, native Enterprise document metadata and actual opened original files, with SHA checks and relational count/ID parity. Verify missing-filestore/incorrect Enterprise version fails closed; Odoo `ir_attachment` orphan cleanup may delete records if improperly started, so disabled crons and filestore closure are prerequisites.
- Measure real restore elapsed time and last-good source age; produce accurate timestamped witness. Document and remediate missing Odoo modules, license/config, KMS access, network/binary references, alert and cleanup within this contract. A synthetic-only restore does not pass.

## Completion

Deliver a dated, independent **real Production** restore receipt with complete S3/version/hash/source-time references in private custody; public-safe IDs in repo, observed business/document integrity, no outbound side effects, restore time, last-good checkpoint and cost. Provide validated baseline and source access specification to Contract 04. Dispose or explicitly secure the isolated restore instance after results, no indefinite paying instance. Close any in-scope defect and update downstream runbook before PASS.

If Odoo source format or Enterprise access prevents a real restore, report `BLOCKED_EXTERNAL` plus exact rights/API/license owner; preserve the safely protected backup and any independently safe progress. A merely uploaded zip is NOT PASS. No production DNS, merge or failover.

## Independent deployable code closure (mandatory before PASS)

- Record the exact local implementation commit and the *actually deployed* AWS code/configuration digest, including every source file and container/runtime digest required to perform restoration without the current developer workstation or GitHub. Preserve the protected release artifact, its S3 object VERSION ID and checksum under the emergency reader's KMS access before marking the initial backup recoverable. An open PR or floating Git branch cannot be the only copy.
- Test with access to Odoo.sh, GitHub, Infisical, and the original Mac withheld. The operator may use the independent emergency AWS identity established in Contract 02; the complete 1Password incident document is assembled in Contract 05 from the verified results. Do not require Contract 05's full document as an upstream prerequisite for the first baseline restore.
- Once this baseline passes, **immediately route Contract 05 to create and independently retrieve the real operator emergency pack for the working daily recovery path**, even when Contract 04's two-hour source investigation remains blocked. Preserve the last known-good baseline; this is a real intermediate safety milestone, not CAMPAIGN_DONE.

## Candidate-versus-admitted checkpoint boundary

A file arriving in S3 is still a **candidate**, not the last-good backup. The independently privileged verification path established by Contract 02 must inspect the real protected source archive/version and commit an admitted manifest with integrity and source-time evidence. Only after a different authorized consumer retrieves that admitted version may the baseline be marked recovery-proven. Writer-originating status flags and an unprotected `latest` key never substitute for verifier admission.

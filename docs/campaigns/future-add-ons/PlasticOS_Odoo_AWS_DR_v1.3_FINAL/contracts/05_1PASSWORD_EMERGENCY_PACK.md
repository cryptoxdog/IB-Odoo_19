```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```


# CONTRACT 05 | Operator-owned 1Password Emergency Disaster Recovery Pack

**Mission:** SM-DR-05-1PASSWORD | **Owner:** real emergency recovery artifact, secure custody, off-Infisical bootstrap, retrieval and operator usability. This is not a local Mac backup campaign. Consume actual 00-03 source/vault/restore receipts **immediately after Contract 03**. Create the complete **baseline-capability** operator pack first, independent of Contract 04. If 04 remains provider-blocked, Contract 05 may PASS for a genuinely complete, tested daily-recovery operator pack that truthfully identifies the missing 2-hour capability; Contract 04 and the full campaign remain NOT_DONE. After Contract 04 changes any protected release/identity/source/checkpoint details, REFRESH the same 05 deliverable and re-prove retrieval before 06.

## Primary destination and operator permission

- Preferred permanent home: a **restricted, company-controlled 1Password vault**, approved for emergency operator custody. Confirm the actual vault owner, audit/access controls, 1Password account sign-in recovery and CLI permissions before writes. Use current official `op` CLI Document commands, with a real interactive user-authorized 1Password session (biometric/sign-in as needed). Do not obtain or log the user's master password, Secret Key or raw MFA code. Never assume a Cursor agent/service account can independently enroll in the operator's vault.
- 1Password is a separate **emergency escrow and runbook owner**, not a replacement for Infisical runtime secret management. All newly created persistent secrets remain in Infisical as SSOT, except intentionally duplicated minimum emergency credentials documented in 1Password, with one-to-one owner and tested rotation. Prefer identity-based emergency access over permanent AWS access keys. KMS key material never leaves KMS.
- Native official CLI supports `op document create <file>|- --vault ... --title ...` and `op document get ... --out-file ...` / stdout. **Before any executable command**, verify installed version/help, actual vault and scoped permissions on the authorized Mac. Document item's 1Password ID and content digest must be recorded privately. A simulated/preview item is not real custody.
- A *non-secret* 1-page index can be retained in version-controlled repo, but the **actual complete private incident pack** lives only in 1Password, not Git, Dropbox or iCloud. Do not upload the entire Odoo database/40GB filestore to 1Password; its purpose is bootstrap, rights, runbook, trusted artifact pointers and minimal emergency access.

## Required packed material (see operations/EMERGENCY_PACK_SPEC.md)

1. Plain-language `START_HERE.md`: exact steps for operator during Odoo/ransomware/Infisical emergency, first decisions, what to stop/NOT stop and escalation contacts. No undocumented tribal knowledge.
2. Identified native and independent **last-good source checkpoint**, S3 bucket/versioned object manifest paths and digest, region/account/role/key ARN and retention; exact source/recovery timestamp, known-good selection and immutable dependency verification.
3. Fully reproducible Odoo 19 Enterprise + custom addon + dependency/version release pointers, separately protected code/install archive and non-secret IaC configuration; verified lawful Enterprise restore/licensing procedure (no hypothetical vendor access).
4. AWS MFA/emergency IAM permission path, independent KMS decrypt procedure, required 1Password emergency items, Infisical primary secret IDs/path + deliberate emergency counterparts, state backend recovery reference, cost and monitoring access, and source of operator notification.
5. Step-by-step restoration, validation and cutover authorization boundary; exact local script entrypoints only after verified repo ownership; instance is nonpublic with mails, cron, webhooks, payments, shipping blocked. Include rollback, alternate known-good source point selection, evidence-preservation steps and post-incident credential rotation.
6. Consistent SHA-256 content manifest and pack version, creation timestamp, exact code/source versions, missing/unavailable status flags, and maintenance trigger for every key/policy/version/source/role rotation.

## Out-of-band bootstrap is mandatory

- 1Password's own **Emergency Kit / supported account-recovery method** must be under separate operator custody *outside 1Password*, with any required MFA recovery method. Printing and storing this separately is recommended; it is the **small bootstrap artifact**, not a 40GB backup or permanent Mac ZIP. Never upload that Emergency Kit into the same 1Password vault as its sole home. If SSO/enterprise policy prevents Emergency Kits, verify the actual supported admin/account-recovery process and operator control instead, with independent witness. If neither works, `BLOCKED_EXTERNAL`.
- Do not claim resilience to the complete simultaneous outage of 1Password and AWS without a separately approved, proved offline alternative. At minimum, test loss of Odoo.sh, Infisical, Cursor and original Mac while 1Password/AWS remain accessible.
- Prefer a streamed/memory-backed private assembly process without persistent Mac output. A tiny temporary encrypted, local NON-synced workspace may be used only when verified CLI cannot accept streaming, with access mode 0700, no shell traces, no logs containing secrets, explicit cleanup and acknowledgement that SSD deletion is not cryptographically guaranteed. In that case, no *permanent* Mac backup remains. A Mac off-Dropbox encrypted fallback requires an explicit operator decision and cannot be silently used to mark the preferred 1Password path done.

## Actual user/operator custody test

1. Through an authenticated CLI session create the restricted 1Password **Document** using the real private archive, plus only essential separate emergency account/credential items. Immediately record item IDs, vault, title, timestamp, hash and exact scope privately, never field values in Git.
2. From a new authorized operator session/device, independently retrieve the document and verify exact SHA-256 equality, unpackability and readability; retrieve the minimum emergency items without the original agent's shell/environment or Infisical. Never leave real secret output in process args/logs/synced folder.
3. Run a table-top clean-room procedure from retrieved pack: choose clean source checkpoint, identify full S3 object dependency chain, recover AWS IAM/KMS access and code/license, and reproduce safe isolated restore from `03`/`04` evidence. The actual full clean-room destructive-free drill belongs to 06.
4. Verify operator access rights persist after workstation logout/session expiration, and test a simulated rotated emergency credential does not leave the 1Password item stale. Ensure documented refresh path and owner.
5. Confirm no persistent pack remains in Dropbox/iCloud/Mac downloads/Desktop or Git; sensitive temp caches and CLI session/env exposure closed. Verify private vault item cannot be accessed by unauthorized principal or ordinary AWS worker identity.

## PASS boundary

**PASS** only if actual 1Password Document and controlled emergency items are created, operator independently retrieves them with matching bytes, separate 1Password sign-in bootstrap verified, all content and references current, no secrets leaking to Git/Mac/Infisical-only bootstrap, and recovery playbook is usable without creator machine. No missing or `UNKNOWN` item. Any missing user sign-in/biometric/vault authorization is one precise `BLOCKED_EXTERNAL` action request, not an excuse to store a secret ZIP in Dropbox or print it to logs. Hand off exact private 1Password IDs and pack hash to Contract 06.

## Contract 05 acceptance split without weakening campaign DONE

- **Baseline custody PASS:** a real, complete, independently restorable **daily source recovery path** from Contracts 01-03, all its required instructions/credentials/1Password bootstrap, actual user retrieval hash match and rehearsal. A provider-blocked hourly enhancement is accurately labelled `NOT_OPERATIONAL`; this is not an incomplete baseline operator pack.
- **Current-release custody PASS:** after a successful Contract 04, the very same 1Password document is updated with the actual scheduled-source, worker release, manifest, credentials and alarms, then independently retrieved again. The older known-good document remains available until the replacement is verified.
- 06 accepts only the latest, source-current 05 receipt. A 05 receipt for baseline recovery does NOT satisfy D04 or full campaign DONE; it does prevent a 2-hour platform blocker from leaving the user without usable 1Password recovery materials.
- Before an `op document create` or edit, verify the real installed CLI, use stdin when practicable to avoid sensitive Mac files, and NEVER send real emergency material as command arguments or print it. Prove retrieval from a separate operator-authorized session, not the creating agent's session.

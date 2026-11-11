```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```


# CONTRACT 02 | Independent AWS recovery vault, identity and Infisical

**Mission:** SM-DR-02-AWS-VAULT | **Authorizes:** creating NEW, scoped DR AWS resources and new, scoped Infisical DR entries only, after Contract 00 identities/plan are proven. Do not edit Odoo.sh native settings or business records. No actual source backup needed until Contract 03.

## Entry guards

- Consume 00 and 01 source-bound receipts, current exact AWS STS/account/region, company ownership, authorized new-resource namespace, budget/irreversible 90-day cost/retention approval, Infisical organization/env/path and security contacts.
- This is NOT authority to create unrelated AWS accounts, edit unrelated IAM/SCP/KMS/S3/network resources, request root access, make static AWS keys, duplicate the Odoo ERP on a permanent host, or change anything in Odoo.sh. If no independent recovery account exists, **a single newly designated AWS Organizations recovery member account is in scope only after** verifying actual Organizations creation privileges, company ownership, independent administrative bootstrap, explicit account-creation and retention-cost authorization, and its recovery policy in Contract 00. Otherwise stop new-account provisioning with a precise BLOCKED_EXTERNAL request; never substitute the app account.
- Review the exact `ops/independent_dr/` file add/modify/removal plan before code. Prefer one IaC tool already owned by the workspace, and minimal resources. No new implementation namespace without proof existing owner can't serve.

## Build the smallest separately controlled vault

- Before irreversible Object Lock Compliance retention, verify live account ID, company owner, AWS region, exact 90-day/365-day storage liabilities and an authorized cost ceiling; first test retention and denied writer operations on a disposable Governance-mode canary. Then create the isolated final vault with the exact approved Compliance-mode rules. Never attempt a destructive Compliance-mode retention test on live protected objects.
- Company-controlled **independent recovery AWS account**, S3 private/versioned/Object Lock bucket (new), public-access blocks, TLS-only policy, bucket ownership enforced, SSE-KMS with dedicated customer-managed key and least-privilege key policy, checked lock/version IDs and minimum 90-day Compliance mode for admitted protected versions. Preserve selected historical archive checkpoints until >=365 days and beyond per explicit retention policy; 90-day WORM expiration NEVER authorizes deleting the recovery point, and an archive may not disappear before cold eligibility. In an isolated synthetic test verify writer denied delete/version removal, retention weakening and KMS disable/delete/grant escalation. Do NOT run deletion tests on real protected objects.
- New scoped writer identity and different emergency recovery/decrypt identity, key administrator independent of writer. An emergency operator must retain a lawful identity path independent of any shared Odoo/Infisical/worker SSO/IdP and a separately protected MFA factor; 1Password alone must not hold broad administrator powers. Prefer short-lived role/STS; no programmatic root access keys. Prove bootstrap and emergency identity access survive loss of ordinary Odoo/worker/Infisical creds; account MFA and policy boundaries verified. KMS material is nonexportable; 1Password emergency pack holds identity/role recovery instructions, not an imaginary KMS key export.
- Private encrypted, versioned infrastructure state backend with state locking if IaC needs it; never commit state. Safe state paths and owner are recorded in version-controlled config or private inventory, according to exposure policy.
- Minimum event/audit/health monitoring (S3/KMS/IAM unexpected changes, upload errors, failing checksum, unavailable last-good, stale source, key disable attempts and costs). Establish an **actual monitored company-controlled recipient**, test one synthetic alarm and acknowledgement, not just create a CloudWatch rule.
- Secret names and narrow consumer references recorded in repo, actual newly created persistent secrets in the verified Infisical project/env/path **at creation**, with explicit owner, rotation, credential-expiry and 1Password emergency escrow requirement. Prefer workload role auth to Infisical over universal token. Prove expected reads and denied access to unrelated paths. Do not put secret values or runtime tokens in Terraform variables/state, launch scripts, CI logs or user-visible material.
- Choose only infrastructure justified by measured source access (a minimal on-demand worker or temporary test compute, no always-on ERP). Prepare worker identity without using Odoo data if native source is not yet proven.

## Deliverable and negative tests

1. Committed safe IaC plus exact region/bucket/role/key/policies/schedule policy pointers, state handling and output redaction under `ops/independent_dr/`. Name all resources with project/campaign tags and inventory. No plaintext secrets in Git/history/build logs; scan synthetic fixtures.
2. A synthetic canary is uploaded, protected with Object Lock, independently decrypted with emergency identity; writer proves inability to delete, change locked version or key. Verify reader lacks backup-writer powers; independent identity has minimum access.
3. Restore capability of key and encrypted state from a *fresh authorized operator session*, not merely the worker profile. Verify real cloud state matches IaC and cleanup of disposable test resources.
4. Budget alert and source/health alarm tested; record actual monthly-cost projection and retention liability; no cloud spend that was not approved in 00.
5. Credential inventory: Infisical project/env/path/key name, owner/consumer/access tests, vault/KMS/ARNs as safe references, independent 1Password emergency handoff requirements for Contract 05; **never include secret values in receipts**.

**PASS** requires all above observed in live AWS/Infisical, cloud resource inventory complete, no open owned gaps, negative tests passing and precise handoff receipt to Contract 03. `BLOCKED_EXTERNAL` for genuinely unavailable isolated account/budget/Infisical authority; do not weaken isolation, lock mode, KMS or retention to declare progress. No real data is uploaded until Contract 03. Publish code only through the verified `make pr` publication transport, no merge/cutover.

## Pinned independent escrow and operations (mandatory for PASS)

- Name the **recovery software artifact owner and custody interface** before provisioning the worker. Independently preserve a signed or SHA-256-pinned reproducible release bundle in the protected private vault containing the exact DR worker code, immutable runtime/dependency lock or image digest, nonsecret IaC, restore instructions and safe state/backend bootstrap references. Never rely solely on an unmerged PR, workstation clone, ephemeral container registry tag, or Odoo.sh build to restore the backup pipeline. Contract 03 proves a consumer can fetch and execute the release using independent credentials.
- Key/role controls must keep *both the protected data AND the protected recovery software artifacts* accessible to the emergency reader. The active backup writer may append a new version but cannot delete/alter protected versions, suppress independent alarms or change who can decrypt.
- Test that cost alarms and security alerts reach an actual independent company-recipient, and identify the residual risk if the entire AWS account/control plane or company email provider is compromised. No dashboard-only proof.
- If IaC state includes sensitive outputs despite a no-secrets-in-code design, treat the state as sensitive by construction; remove the secret-bearing input where possible, and preserve encrypted, scoped, offline-recoverable state. Never declare state 'secret-free' merely because Terraform flagged values as sensitive.

## Separate verifier authority: untrusted writer is not an admission authority

Create minimally scoped independent verification/admission authority (as a distinct IAM execution identity, without adding a persistent service unless proven necessary). The writer writes only candidate objects. An independent verifier reads the exact protected object versions and source timestamps, checks hashes/filestore/DB completeness and dependency-retention closure, then publishes a protected immutable admitted manifest and advances last-good in a verifier-only namespace. The writer must be unable to `PutObject` into admitted/last-good prefixes, assume the verifier, disable its alarms or change its IAM policy. Test denied writer self-promotion and forged/latest candidate against synthetic objects. This is a real failure boundary, not a label change on the same worker identity.

# Security ownership | Infisical, 1Password, Git, S3, KMS and state

**Applies to ALL contracts 00-06.** Never commit or include actual secret values in this campaign ZIP. Existing Infisical organization/path is not inferred: resolve real authorization at P0. Project-local secret policy does not reassign authority to AWS, Odoo or the agent.

| Information and authority | One primary owner | Recovery/control rule |
|---|---|---|
| Every **new persistent runtime secret**: Odoo backup source credential (only if authorized), worker/repository encryption password, SMTP alert key, API credential, new service bootstrap | **Infisical**, correct verified project/env/DR folder | Create there at generation with scoped owner, consumer and expiry/rotation. Workload identity prefers AWS IAM Auth/short-lived tokens, not static keys. Confirm read and denial tests. |
| Minimal **emergency duplicates** essential while Infisical is down (if no credentialless identity-based method) | Restricted **1Password emergency vault**, operator-administered | Deliberate escrow, separately inventoried; not normal worker source. Refresh on rotation; dry-run recovery, restrict vault access. |
| 1Password account login recovery | Independent operator-held **1Password Emergency Kit** or verified organization recovery method | Must be outside 1Password; print/store securely when supported, not accessible to routine agents or alone on original Mac. |
| AWS S3 backup data | Dedicated private, encrypted, locked AWS recovery bucket | Every checkpoint has source time and immutable manifest. AWS KMS decryption rights verified from emergency principal. |
| KMS key material | **AWS KMS** | Do not export/claim to escrow KMS key bytes. Maintain protected key-policy access and key-disable/delete denial controls. Keep KMS key ARN in safe inventory. |
| IaC source, current job schedule, retention, IAM policy definitions, nonsecret pointers, authoritative runbook | `IB-Odoo_19/ops/independent_dr/` in Git | Current reviewed source under `Staging`; exclude sensitive account IDs/URLs if repository disclosure policy forbids. Never put production objects or credentials in Git. |
| Terraform/OpenTofu operational state and sensitive outputs | Private encrypted, versioned, access-restricted state backend | Outside Git and outside the immutable data vault if mutable state needs a different lifecycle. Prove emergency rehydrate and lock. |
| Live recovery operational receipts incl. private object/version IDs and customer sample hashes | Private encrypted AWS evidence store (or dedicated restricted 1Password items for emergency metadata) | No sensitive manifests in PR, public CI logs or chat. Controlled retention and retrieval. |
| Emergency operator DR package | Restricted **1Password Document and supplementary emergency items** | Real `op` CLI create/get proof and independent authorized retrieval, not Mac/Dropbox copy. Full DB contents stay in S3. |
| Temporary recovery pack assembly | Encrypted or memory-backed private temporary work area, preferably streamed into 1Password | No long-lived Mac file. Avoid shell args/history and logs containing secret bytes; private 0700 temp if needed, clean with limitations noted. |

## Exact Infisical adoption procedure

1. Inspect the approved Infisical organization/project, `prod`-equivalent environment, DR paths, machine identity type and current authorization. Existing `Cursor-Governance` project references in older docs do not authorize using that root for new Odoo DR secrets.
2. Maintain private inventory per secret: `secret_id, actual_project/env/path, purpose, creation/rotation/expiry, owner, readers, producer, consumer, whether emergency duplicate required, 1Password item id, access test time`. Git may hold names and **non-secret** references only; do not record secret content or unredacted inventory there.
3. Prefer AWS STS/workload role and Infisical machine identity AWS Auth where supported. If a bootstrap client secret really must be generated, do not create a self-referential secret that only the locked service can provide; immediately escrow bootstrap separately under operator control and restrict its use.
4. Every source access, IAM privilege, KMS authorization, S3 retention or new secret must have tests showing permitted operations and denial of unrelated environments/resources. Test credentials after session expiration and after rotation. Do not rotate existing shared production credentials without separate explicit authorization.
5. Prefer no static AWS keys. If an externally necessary long-lived secret exists, prove necessity, issue with least privilege, store Infisical SSOT and only emergency copy in 1Password, rotate and audit.

## Exact 1Password operator custody procedure

1. Verify the actual authorized company 1Password account, restricted vault owner and access. Operator personally unlocks the desktop/CLI session; C never demands account password/Secret Key/MFA or captures screen/log output displaying secrets.
2. Use the currently installed `op` CLI help and official `op document create` / `op document get` interface for a Document object. 1Password CLI supports stdin and vault selection (source URL in `evidence/SOURCE_BASIS.md`). Create a **versioned full emergency operator pack** and essential separate credential items. Test restricted-vault denial to unrelated users/workers.
3. Independently retrieve it from a new operator-authenticated session and compare SHA256, unpack/read, follow procedure without original Mac, Infisical or Odoo.sh. The recovery pack is NOT the 40GB encrypted recovery corpus; that remains in S3.
4. Operator must physically retain 1Password account bootstrap outside 1Password (Emergency Kit or equivalent approved recovery process); C verifies the existence/access *without copying its secrets*. Strongly prefer a printed sealed kit in secure custody if provider/account supports it, not in Dropbox.
5. A MacBook-only fallback is conditional on the operator explicitly authorizing it after 1Password failure. It must be encrypted at rest, outside Dropbox and **any** iCloud-synced/managed path, validated with realpaths, access 0700/0600 and FileVault enabled; never use plain Desktop/Downloads/Documents as default. Treat fallback as custody exception, not an invisible replacement for 1Password. Never promise secure deletion of SSD blocks.

## Repo / distribution safeguards

- Detect repository visibility, `.gitignore`, `.gitattributes`, LFS, CI workflows, public PR body generation, cached artifacts and secret scanners before committing. Secret pointer names may be safe, but actual account IDs/usernames/production bucket IDs may be sensitive; respect repo visibility policy.
- Maintain reviewed `config/DR_CONFIG.example.yaml` (or existing suitable file) for schedule/retention/identity reference names; IaC source and restore documentation versioned. No Terraform `*.tfstate`, `*.tfvars` with secrets, `.env`, customer files, 1Password ZIP or Infisical values in Git. Deploy using runtime auth/short-lived credentials and current secrets directly, avoiding persistent CLI credentials.
- No programmatic secrets shown in stdout, command-line arguments, telemetry, chat, screenshots or debug stack traces. Actual credential grant/rotation always recorded privately with independent audit.
- **Do not falsely claim cross-provider independence**: vault protects against Odoo.sh and Infisical loss, but still depends on AWS account/KMS availability and authorized 1Password access. Account-wide AWS lockout and combined 1Password outage require separately approved resilience if desired.

## Required negative tests

- Infisical cannot be reached; emergency operator retrieves 1Password items and S3 data/KMS access, restores Odoo. Test from independently authenticated operator path.
- Normal backup writer denied 1Password emergency vault, Infisical admin path, KMS key policy manipulation, S3 delete/retention bypass, alert disabling. Synthetic canaries only.
- Dummy secrets in disposable fixture logs/tfvars/git paths are flagged by scanners. No actual secrets placed in test artifacts.
- Rotation of necessary emergency secret updates 1Password counterpart and tests it; stale counterpart fails acceptance.
- Lost Mac/agent session does not block 1Password sign-in, pack retrieval and emergency AWS access, given independently retained 1Password account bootstrap.
- Failed/partial 1Password upload does not overwrite the last-good operator document; independent read validates the actual content.

## Release, state and emergency escrow ownership closure

- The exact actual DR code/runtime/Enterprise dependency release required to restore is a **protected source artifact**, not just a mutable Git ref. Store its digest, exact S3 object version and last tested restoration witness in the restricted emergency pack. The artifact cannot contain active customer secrets or production exports unless intentionally encrypted and scoped in the vault.
- AWS KMS policy/bootstrap, protected Terraform state and change history require an emergency read path independent of Infisical, the normal worker and the original Mac. A 1Password emergency vault credential is intentionally an escrow duplicate, NOT a second routine runtime secret authority.
- Never put passwords, temporary access tokens, decrypted archives or private runtime config values in public PRs, shell command-line assignments, build stdout, Terraform diagnostics, system logs or an `op` CLI item-field argument; use the CLI's authenticated/stdin mechanisms and private retrieval, and verify cleanup of temporary files.
- Verify the account custodian has an out-of-1Password Emergency Kit or independently proven organizational recovery method. **Do not treat 1Password as offline storage**: loss of both 1Password service and AWS remains a disclosed residual failure unless a separately approved offline sealed copy is actually tested.

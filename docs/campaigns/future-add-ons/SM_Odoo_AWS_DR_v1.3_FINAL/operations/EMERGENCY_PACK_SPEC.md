# Exact 1Password Disaster Recovery Pack | Operator content specification

**Artifact identity:** `SM-ODOO-DR-EMERGENCY-PACK` at versioned actual campaign completion revision.
**Location:** Dedicated, restricted Scrap Management-controlled 1Password vault, using an actual 1Password Document item (plus separate minimal emergency account items). Do not leave long-lived ZIP on a Mac, put in Dropbox, or place bulk DB archives into 1Password. Built **by Cursor during Contract 05** from current verified provider receipts; this campaign design ZIP is NOT the final emergency pack.

## Required private Document contents (all mandatory, no placeholders at PASS)

| File inside the private operator package | Complete content needed to run recovery |
|---|---|
| `00_START_HERE.md` | 1-page first-response flow, safe operator decisions, known-good backup selection, escalation/incident declaration, step-by-step starting point, what never to click during incident |
| `01_SYSTEM_IDENTITIES.md` | Actual company AWS account/region, trusted emergency IAM role/access steps, Odoo.sh source identity and last healthy native source timestamp, code/version and approved nonproduction/public boundaries |
| `02_S3_RECOVERY_INDEX.json` | Known-good complete S3 point manifests with exact object versions/digests, account+bucket+KMS references, source times, retention, and how to verify current last-good independently |
| `03_KEYS_AND_CREDENTIAL_MAP.md` | No raw secret values; exact operator-only 1Password credential item IDs/labels, Infisical primary secret reference names, role authentication instructions, MFA/recovery custody, rotation owner and emergency KMS decrypt permissions |
| `04_FROZEN_SOFTWARE.md` | Odoo 19 Community/Enterprise+custom module versions, exact code revision/archive digest, correct PostgreSQL/runtime dependencies, access and license rights, stored protected source/dependency recovery artifact pointers independent of Odoo.sh |
| `05_RESTORE_OFF_ODOO.md` | Actual tested step sequence for network isolation, IAM/KMS auth, download of exact S3 versions, DB/filestore integrity, Odoo 19 Enterprise startup in neutralized environment, document/transaction verification, failure rollback |
| `06_CUTOVER_IS_SEPARATE.md` | Real incident owner, DNS/billing/licensing reactivation approvals; Odoo production protection and no split-brain; no automatic production cutover from a test |
| `07_MONITOR_ROTATE_AND_REHEARSE.md` | Emergency contacts and alert ownership, last drill date/result, secret renewal, documentation-refresh triggers, monthly sample restore and quarterly full drill |
| `08_INTEGRITY.json` | Document pack build UTC time, campaign ID, exact source archive version + SHA-256 for all files, 1Password uploaded document item ID filled in receipt after creation, current S3 last-good and AWS configuration revision |
| `09_THREAT_AND_LIMITS.md` | Known residual exposure, RPO/RTO measured, corruption/poisoned source, AWS account/KMS outage and 1Password account outage; do not promise zero loss |

1Password item IDs can be written to the private custody receipt after upload rather than become a self-referential byte inside its own hashed archive; no circular digest requirement. Real sensitive ARNs/snapshot identifiers can stay inside the protected Document and private receipts; Git gets only a non-secret abstract inventory.

## Separate 1Password items

- Emergency AWS sign-in/MFA/identity-provider recovery **only to the minimal extent authorized by actual company IAM/Identity Center access**. Do not rely on a single shared corporate SSO/IdP that could be unavailable alongside Odoo. No creation of a static root or permanent AWS secret key purely for the pack.
- Only required off-Infisical bootstrap secrets or user-recoverable account credentials, with purpose, owner, access and rotation. Do not mirror all Infisical production secrets into 1Password.
- Approved emergency license/Enterprise access details if they are necessary and legally retainable. Source code artifacts should reside in secure S3 or other operator-controlled artifact store, not in ordinary login fields.

## External bootstrap that C cannot put inside its own vault

- 1Password sign-in **Emergency Kit**, actual account password knowledge and 2FA/recovery method, or observed organization-supported SSO/admin recovery. This must be protected outside 1Password, and not solely on original Mac. Operator is responsible for holding it, with evidence of capability and no disclosure to C. A printed sealed copy in a safe can satisfy this; do not print full secret contents from the DR pack unless expressly authorized.
- If no independently usable 1Password bootstrap exists, Contract 05 cannot PASS even if the Document uploaded correctly.

## Assembly, upload and retrieval

- Verify 1Password CLI version/`op document create/get` syntax, actual vault and human authenticated session. Assemble in a memory-backed/encrypted temp space without long-lived synced artifacts, or stream into `op document create -` where supported. Never echo sensitive bytes to terminal or shell history.
- Store a versioned document title and private, nonsecret content SHA-256 receipt. Retrieve **in a separate authorized operator session** using 1Password Document read interface and compare full digest; open/read/start drill. Verify nonprivileged identities cannot access this vault.
- At close, verify no Mac/Dropbox/iCloud permanent ZIP remains. Clear authenticated CLI session and temp material to best available OS controls; document SSD snapshot/forensic residual limitations instead of falsely guaranteeing deletion.
- At each IAM/KMS/source/Infisical secret/1Password role/licensing/backup-method change refresh the Document, reverify its digest and retired references. Keep a prior known-good emergency version until new one tested.

## When the user opens it during an incident

Start from `00_START_HERE.md`. The operator authenticates to 1Password from **any independently authorized, safe device**, uses the separately retained 1Password Emergency Kit if needed, identifies the correct S3 recovery manifest, exercises minimal AWS/KMS role, then follows `05_RESTORE_OFF_ODOO.md` in an isolated host. The procedure may **not** require Odoo.sh, Infisical, the agent's Mac, a connected Dropbox folder, the developer's current IDE or a service account token whose sole copy is stored in unavailable infrastructure.

## Mandatory independent executable release inventory

The private 1Password pack must identify the exact independently stored **working DR executable release** (worker/restore scripts, tool image/digest and dependency locks), infrastructure-state recovery location, and pinned Odoo 19 Enterprise/custom code archive. Record versioned S3 object references and independently tested hashes, not only a branch name or pending PR. Recovery must remain executable when GitHub and the original Mac are both unreachable. The operator pack is generated immediately after first full restore and refreshed again after schedule/identity changes.

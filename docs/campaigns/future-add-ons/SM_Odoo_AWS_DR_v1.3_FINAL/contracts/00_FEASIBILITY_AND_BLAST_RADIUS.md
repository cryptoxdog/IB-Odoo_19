```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
  unlisted_repositories: no_access
```


# CONTRACT 00 | Current authority, capability and complete implementation blast radius

**Mission:** SM-DR-00-FEASIBILITY | **Owner:** bounded preparatory evidence, not provider mutation.
**Prerequisites:** complete campaign pack, current Cursor workstation access, 1Password CLI and provider identities if already authorized.
**Allowed effects:** read-only inspection of GitHub, actual Odoo.sh Production, Infisical, 1Password CLI/account/vault capabilities and AWS account; generation of private operator proof artifacts. **One operator-authenticated nonsecret 1Password canary Document create/read/delete is allowed solely to verify CLI custody and must be cleaned up or accounted for before 00 PASS.** No AWS or Odoo.sh mutation, no real emergency secrets, and no implementation code.

## 00.1 Exact current source inventory

- Freeze `IB-Odoo_19/Staging` HEAD, current working tree, `AGENTS.md`, root `INVARIANTS.md`, `.cursor` rule bindings, `ops/` and any existing DR automation so the implementation does NOT overwrite or duplicate an already owned component. Inspect Odoo module filestore/orphan-cleanup and Enterprise ownership only for restore proof; do not alter business code.
- Resolve current global governance/authority ONLY through the actual read-only owners; if inaccessible, mark L9 constitutional binding UNKNOWN, never invent a projection/receipt. Publication via `make pr` needs current Cursor-Governance SSOT owner proof, not assumed Make targets.
- Resolve the real **Production** Odoo.sh project/build/DB/region/plan, automatic backup timestamps, manual backup and download abilities, SSH authorization, vendor backup constraints, full DB+filestore export options, CPU/network quotas, and supported alternative for an independent consistent 2-hour point. Differentiate permission to READ source from permission to GENERATE fresh backup. No undocumented UI scraping/platform API.
- Resolve exact AWS STS identity, separate company account ownership, target region, IAM/SCP admin boundary, cost authorizer/budget, allowed object-lock/KMS/worker/scheduler permissions, S3/KMS durability and recoverability. If a separate company-controlled recovery account does not yet exist, evaluate a NEW AWS Organizations member account with independent administrators and owner-approved cost/creation permission. Only create such an account when those specific permissions and approvals are verified; otherwise record BLOCKED_EXTERNAL. Never silently use the ordinary application account or assume cross-account writes.
- Inspect the approved Infisical organization/project/env/path, machine identities and auth method. Inspect the authorized operator's 1Password CLI version, interactive Mac desktop auth, restricted vault permissions, `op document create/get` capability, document size limits, operator access and account-recovery arrangement. **Do not ask for operator master password or 1Password Secret Key.** Obtain any necessary interactive biometric approval from the operator.
- Confirm Odoo 19 Enterprise source/version, appropriate license to test restore and emergency failover policy; exact runtime dependency manifest, configuration/secrets needed to boot, PostgreSQL compatibility and no-effect sandbox path.

## 00.2 Account every ripple before code

Produce an evidence-backed matrix with **each** row carrying `owner | exact current source/path/ARN | observed evidence | required change/add/remove | consumers | permission | phase | order | migration/cleanup | test | failure/recovery | disposition`. Rows must cover:

1. Every affected repository file/path and non-change exclusion, down to exact proposed file additions/modifications/removals and owners; why no existing owner is sufficient.
2. Odoo native backups, source privileges, export/consistency behavior, filestore, version and Enterprise rights; explicitly show **no operational production writes**.
3. AWS account/IAM/SCP, KMS key policy and deletion controls, S3 Object Lock/versioning/lifecycle/bucket-policy and access points, optional cache/worker and scheduler, logging/audit/alerts, costs, private IaC state, eventual release/deletion liabilities.
4. Infisical machine identity/bootstrap, secret names/paths/readers/rotation; 1Password vault/document/item IDs and operator custody; encrypted/temporary staging and all exit paths.
5. Ordinary outage, vendor compromise, malicious writer, injected/poisoned snapshot, expired secret, KMS unavailable, 1Password unavailable, failed schedule, backup-source unsupported, restore with wrong code version, missing filestore, business side effects and delete/retention issues.
6. Exact baseline restore/incremental/weekday/archive/1Password/adversarial test witnesses. Reconcile documentary exclusions individually; no assumed 'not affected' module.

Required output: complete `BLAST_RADIUS.md`, `IMPLEMENTATION_FILE_PLAN.md`, `PROVIDER_CAPABILITY_PROOF.md`, and `RUN_AUTHORIZATION.md` in private evidence with a minimal public-safe repo summary. Pin hashes/identity and a dependency DAG across Contracts 01-06. Fail closed when a *material* requirement lacks exact owner/permission/disposition. If a newly discovered ripple arises in a later contract, invalidate affected matrix rows and repair the plan **before continuing code**.

## 00.3 Discriminating feasibility tests

- Prove at least one real native completed Odoo Production backup source exists and the operator can access its contents/metadata with documented rights. Do not make a copy or create a new backup during this preflight.
- Establish whether four fresh 2-hour database+filestore checkpoints are *legally and technically possible* at this Odoo.sh tier. A fresh 11 AM download of a midnight source does NOT pass. If unknown, record the precise Odoo support/capability request; no falsified yes.
- Prove AWS account independent administration and safe new-resource namespace; current AWS account not automatically the right account.
- Prove the operator's **1Password account can hold and later retrieve** an appropriately scoped Document item via CLI using a synthetic non-secret canary. Do not create a permanent secret package here.
- Verify contact/owner for schedule failure alerts, cost alarms and one-hour credential reset/approval in an emergency.

## Acceptance and handoff

**PASS** requires pinned source and code authority, complete blast radius with all changes accounted for, approved resource/cost boundary, correct Infisical/1Password identity, exact supported native path and a testable independent restore design. A still-unknown 2-hour provider capability may be documented as a *bounded external feasibility blocker*; it cannot magically become PASS for the two-hour portion and must remain open in campaign release gating. Close all internal unknowns within scope; produce `coordination/SLICE_RECEIPT_TEMPLATE.yaml` populated with real proof IDs and `open_in_scope_items: []`.

**BLOCKED_EXTERNAL** only when the live provider/account/licensing/owner cannot grant a required permission or feature. Cite requested action and dependency owner, and proceed on independent safe proof, without provider bypass. **FAIL** for an incorrect matrix/test/identity. No invented shell commands, CI result, source name, AWS budget, provider capability or PR.

## 00.4 Material authority, release custody, and baseline-first closure

- Account for a specific physical path to safeguard the **exact deployed executable DR implementation**, runtime/tool images, the required Odoo 19 Enterprise/custom source and dependencies, *plus independently rehydratable IaC state* outside the original Mac, GitHub and Odoo.sh. A PR head alone is not a durable recovery artifact. The implementation path, version, rights, hash, storage and emergency reader all require owners, planned changes and restore tests.
- Distinguish **full-campaign requirements** (all seven PASS, fresh two-hour source) from an **independently functioning daily recovery milestone**. If two-hour source is externally blocked, do not postpone 1Password custody for the already-proven complete daily backup and isolated restore. Contracts 03 and 05 must close that early recovery milestone while Contract 04 and overall campaign remain NOT_DONE.
- For every provider action distinguish observation, native read-only data access, supported manual-native backup action, *new AWS account creation* and irreversible compliance retention. The accepted campaign scope allows only actions for which the exact account owner, permission, spend/retention cost and side effects have been checked. Never infer AWS Organizations account-creation approval merely from general AWS API connectivity.
- The final matrix must also specify the **deployment/PR publication boundary**: exact commit that deployed AWS IaC and worker, protected independent source/artifact copy at the same digest, review status, any unmerged code and the on-call maintainer's upgrade/rollback procedure. No unpublished original-Mac-only source dependency.

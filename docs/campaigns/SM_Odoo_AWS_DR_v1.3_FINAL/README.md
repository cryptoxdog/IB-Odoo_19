# Scrap Management | Odoo.sh + Independent AWS Disaster Recovery

**Campaign ID:** SM-ODOO-DR-CAMPAIGN-001
**Pack version:** 1.3.0
**Decision status:** OPERATOR-LOCKED POLICY, NOT A LIVE IMPLEMENTATION OR APPROVED PRODUCTION CUTOVER
**Target:** cryptoxdog/IB-Odoo_19, integration base `Staging` (pin live HEAD at execution).

## The operator's non-negotiable outcome

Native Odoo.sh protection remains healthy. Scrap Management owns an independent, immutable, cost-bounded AWS recovery capability and a verified operator-accessible emergency recovery pack in **1Password**, with Infisical used for runtime secret management and Git for safe declarative configuration. An outage/compromise of Odoo.sh, Infisical, the normal backup worker or the operator's Mac cannot prevent restoration (provided the independent AWS account, keys and emergency 1Password access remain intact). The preferred custody route creates **no persistent MacBook recovery ZIP**. The 1Password Emergency Kit/bootstrap material must separately be available out of band.

## Locked schedule and efficiency

- Four *fresh, consistent* source checkpoints are targeted at 11:00, 13:00, 15:00 and 17:00 America/New_York, Monday through Friday; 20 starts each operating week. Native platform backups continue at night/weekends.
- Business-hours RPO objective is <=120 minutes, RTO objective <=4 hours; both must be measured, never inferred from a schedule. Source snapshot age includes capture/transfer/admission lag. A 2-hour target is not yet proven attainable on Odoo.sh.
- One complete baseline, then cryptographic deduplication and only changed data transferred where the **real source mechanism** permits it. Consistent PostgreSQL restoration includes all changes, deletions, related tables/sequences and matching filestore, not a collection of `write_date` row exports.
- S3 protected recovery data is encrypted and immutable (initial >=90-day retention); after 365 days only provably self-contained archive sets become cold eligible, never dependencies required for hot restore.
- There is no second live ERP and no operational Documents backend swap.

## Execution contracts, in mandatory sequence

| Slice | Contract | Complete, independently verifiable result |
|---|---|---|
| 00 | `contracts/00_FEASIBILITY_AND_BLAST_RADIUS.md` | Source/authority/permissions/credentials/account, file and cloud blast-radius closure, validated plan, evidence-based go/no-go |
| 01 | `contracts/01_ODOO_NATIVE_BACKUP.md` | Native Production backup controls verified, supported manual checkpoint and isolated native restore proven |
| 02 | `contracts/02_AWS_VAULT_AND_IDENTITY.md` | Independent AWS vault, KMS/IAM, Infisical, IaC, alerts and denial tests working |
| 03 | `contracts/03_FULL_COPY_AND_INDEPENDENT_RESTORE.md` | Real Production DB+filestore safely in S3, independently restorable without Odoo.sh |
| 05 (baseline) | `contracts/05_1PASSWORD_EMERGENCY_PACK.md` | Create and independently retrieve usable emergency custody for the first proven daily restore immediately after 03 |
| 04 | `contracts/04_INCREMENTAL_AND_WEEKDAY_SCHEDULE.md` | Fresh 2-hour source checkpoints, changed-byte economy, 4 jobs/day and independently restored scheduled point |
| 05 (refresh) | Same 05 contract | Refresh and independently retrieve the emergency pack for exact deployed 04 resources, secrets and recovery release |
| 06 | `contracts/06_ADVERSARIAL_REVIEW_AND_CLOSEOUT.md` | End-to-end independent rehearsal, receipts, monitoring/drills, no uncovered gaps, governed PR(s) |

Contract boundaries are **owner boundaries**, not invitations to leave pending work. Every slice must close its own tests, secrets, configuration, receipts, cleanup and dependency handoff before calling `PASS`. External provider blockers are explicit and campaign remains NOT DONE until resolved or operator *formally changes the lock*. A green PR, backup zip, AWS bucket, or report cannot close any runtime gate.

## One place for each kind of truth

- `policy/LOCKED_POLICY.yaml`: project-local operator decisions; implementation agent may not revise.
- `policy/INVARIANTS.md`: sharp falsifiable invariants, one SSOT; downstream pointers, never duplicated law.
- `coordination/DEFINITION_OF_DONE.md`: boolean acceptance and blocker behavior.
- `coordination/SLICE_RECEIPT_TEMPLATE.yaml`: mandatory non-secret handoffs and downstream verification fields.
- `architecture/STORAGE_AND_BLAST_RADIUS.md`: existing code/external owner matrix, expanded secrets/1Password/campaign ripple requirements.
- `security/INFISICAL_1PASSWORD_AND_CONFIG.md`: real ownership of secrets, recoverable operator material, private runtime state and public-safe code.
- `operations/EMERGENCY_PACK_SPEC.md`: exact 1Password document/item inventory and minimum recovery bootstrap.
- `operations/INDEPENDENT_RESTORE.md`: restore algorithm and negative checks.
- `evidence/ACCEPTANCE_MATRIX.md`: detailed witnesses, source and negative tests; no fictional green.
- `evidence/SOURCE_BASIS.md`: bounded repo observation, provider docs, material unknowns.
- `MANIFEST.json` + `CHECKSUMS.sha256`: this pack's own file-integrity hashes, NOT implementation proof.

## Repository and publication boundaries

One writable repository: `https://github.com/cryptoxdog/IB-Odoo_19` on a scoped branch from live `Staging`. `.github` and Cursor-Governance are read-only if required for authority and publication. Most changes should live under `ops/independent_dr/`; no PlasticOS business addon rewrite. Do not modify unrelated AWS resources, Infisical secrets, Odoo records, CieTrade source, production DNS, or Enterprise subscription. Use only the validated Cursor-Governance `make pr` publisher for remote PR changes, no raw push, merge or production cutover. AWS provisioning is separately authorized *within* verified named/new DR resources, with irreversible retention budget/permission gates.

## First execution instruction

Give Cursor this **complete ZIP** and ask it to run the bounded contract train 00,01,02,03,05-baseline,04,05-refresh,06, not to invent its own narrower definition of done. One stopped slice does not authorize a false campaign PASS; the agent must close every in-scope loose end or return a precise externally owned blocker and continue all independently safe work. Follow the reference source and official documentation linked in `evidence/SOURCE_BASIS.md`; validate every executable against its current owner first.

## Critical execution corrections in v1.3

- **Early protection:** Contracts 00-03 establish real daily independent restore; Contract 05 must immediately create/retrieve a complete operator pack for that proven capability BEFORE Contract 04 experimental two-hour optimization. Contract 04's platform limitation cannot strand a genuine daily restore with no operator guidance.
- **Durable recovery code:** An open or unmerged PR, cloud-hosted Git branch and developer Mac are not sufficient. The exact deployed DR recovery software, Odoo Enterprise/custom runtime dependencies, required IaC state pointers and verifiable hashes must be independently protected and restored without GitHub, Odoo.sh or Infisical.
- **Account provenance:** If an independent company-controlled AWS account does not already exist, creating a new member account is conditionally in scope ONLY with proven company ownership, explicit permission and approved spending/irreversible retention; the ordinary app AWS account is not a substitute.
- **Mechanical coverage:** `coordination/INVARIANT_TRACEABILITY.csv` binds all 48 previously locked invariants plus DR-049 independent checkpoint admission to accountable contract/test gates. The strengthened validator has negative tests and rejects unmapped policy claims, missing files, stale references and changed bytes. This is local pack evidence, not runtime acceptance.

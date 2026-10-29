# Locked and source-backed campaign invariants

Plan-level operator obligations are authoritative only within this requested work. They do NOT replace or silently amend active `INVARIANTS.md` v2.2.0. The preserved draft POS invariants remain candidates.

**L01** Only cryptoxdog/IB-Odoo_19 may change in the future. EIE, CEG, Constellation.Gate service and SDK contracts are read-only.

**L02** Retain and complete plasticos_enrichment as a single Odoo-native human approval and writeback shell, not a new addon.

**L03** Keep automatic CRM writeback OFF. No EIE-returned CRM fields may be applied before granular authorized user approval.

**L04** Preserve current data and audit through start-clean: no destructive table wipes, dropped evidence, or fabricated historical review.

**L05** Retired local crawl/extract/inference engine and both old cron entrypoints remain disabled and uncallable.

**L06** Odoo is Gate consumer. Gate -> EIE is external intelligence authority; Odoo never bypasses Gate.

**L07** Approve or reject each proposed field. Run-level EIE confidence is not field-level confidence and missing citations are explicitly labeled.

**L08** Allowlist of eight `res.partner` fields is unchanged; all nonallowlisted fields are evidence-only and cannot write.

**L09** Native CRM existing nonempty/verified values win. Typed source snapshot freshness and approval must be rechecked under target row lock before write.

**L10** Only authorized Odoo enrichment roles may review/apply. Server-side ACL, company rules and method guards must agree. No broad base.group_user CRUD.

**L11** Do not create res.partner for partnerless prospects. Current enrichment run remains existing partner-only.

**L12** Proposal is an immutable projection of stored Gate evidence; provenance records actual applied writes, not arbitrary approvals.

**L13** Human action with no field-level EIE citation must not silently invent one. Allow user-attested evidence where current policy permits, clearly distinguished and attributable.

**L14** No double apply, stale-value overwrite, partial unlogged write, or retry-induced duplicate outcome.

**L15** Run/field state machines deny arbitrary RPC state+payload mutation; preserve historical run records.

**L16** Source/manifest/ADR changes must preserve source-owner meaning and current active INVARIANTS.md. Candidate POS draft is not constitutional.

**L17** No new CEG overnight scheduler, ranked queue consumer, offering/matching, semantic kernel, or automatic EIE callback to Odoo.

**L18** Use native Odoo model security, form/list/one2many, mail.thread and PostgreSQL row locking before adding new infrastructure.

**L19** Migrate additively from actual installed module versions; preserve source UUID/packet/audit, disabled cron state and original DB+filestore snapshots.

**L20** No implementation, PR, merge, live paid calls, migration, deploy or activation is authorized by this planning ZIP.

**L21** Every material direct and transitive source effect has owner, file, disposition, safe migration, recovery, positive and negative proof; new consumer reopens affected plan.

## Falsifying cases

- A `base.group_user` can create/write/unlink a review run, proposal decision or applied provenance via RPC: FAIL.
- `action_inject` on an old run can still create `plasticos.material.profile`: FAIL.
- `gate_auto_writeback_enabled` true can silently apply fields without field-level human review in the scoped addon: FAIL.
- A selected field changes after reviewer saw it; an old approval still overwrites: FAIL.
- Shared/cross-company partner is visible or mutable to a foreign tenant without explicitly accepted source-owner policy: FAIL.
- Confidence is shown as field-specific when only aggregate response confidence exists, or missing value is replaced with 1.0: FAIL.
- A successful EIE response without writable fields is mislabeled as transport failure or dropped without evidence: FAIL.
- Running an upgrade re-enables old crons, recreates manager privileges, or fabricates historical approvals: FAIL.
- Any source write to external CEG/EIE/Constellation.Gate service or anything in Offer/Semantic Kernel: SCOPE VIOLATION.
- A package validator green is used as permission to code, migrate, merge, activate or send live paid requests: FAIL.

**Constitution:** `PLANNING_KERNEL/CORE/INVARIANT_ROUTING.md`; root-case `target.constitution` and the fresh current source lock prove the active hierarchy. **Required precode completeness:** POS-INV-26 operator planning obligation, even though not an admitted constitutional provision.

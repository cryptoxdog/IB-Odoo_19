# Server-side authorization, CRM writeback and audit boundaries

## P0 source findings

`plasticos_enrichment/security/ir.model.access.csv` currently grants `base.group_user` **all four CRUD permissions** for `plasticos.enrichment.run`, `.source`, `.extraction`, `.provenance`. Even a non-enrichment internal user may receive those rights, defeating group-only native form restrictions. A `group_enrichment_manager` is additionally granted to `user_system_cron` at post-install despite both old enrichment crons being retired. `EnrichmentRun.write()` allows editing a protected run when the caller includes `state` among the changed values. No new review feature is safe until these are closed.

## Preferred Odoo-native replacement

- Keep current `group_enrichment_user`, `group_enrichment_manager` and Odoo 19 `res.groups.privilege`. Remove the generic internal **write/create/delete** grants only when installed record/rule consumers are enumerated. If ordinary internal users require visibility, grant company-scoped READ only. The producer of Gate facts may create immutable response lines through an explicit checked internal service, not arbitrary user write.
- Grant enrich Users the minimum initiate/read/approve-or-reject privileges permitted by final policy; Managers may Apply Approved only if registered as a legitimate operator at that company. Do not infer manager role from base.group_user, sudo, XML button invisibility or a context flag.
- Add company-scoped `ir.rule` on review run/line/audit. The run and proposal must carry an explicit `res.company` owner, not a nullable ambiguous partner-as-company alias. Shared `res.partner` records (`company_id=False`) require an explicit source-owner policy; do not assume global visibility grants write authority.
- All public `action_execute`, `action_retry_enrichment`, `action_inject`, `action_apply_approved`, and proposal decisions validate record company, allowed_company_ids, actor group, state and target before effect. Lock rows inside the transaction for CAS. Server defaults alone are not authorization.
- Make Gate-response facts and terminal run fields readonly for normal RPC after creation: forbid caller write of `engine_used`, `gate_proposal`, packet/correlation ID, source digest, company, target partner or state. Only vetted workflow transitions may change lifecycle, and they record who/why.
- `plasticos.enrichment.provenance` is created only alongside successful actual write and is immutable afterward, with source/packet/field/reviewer and a unique applied-effect mapping. Historical provenance preserved in place.
- Retired cron privileges: read actual membership and other jobs before removing `group_enrichment_manager` from `user_system_cron`. Migrate only proven obsolete grant, never broad-revoke shared system groups or alter unrelated cron access.

## Two overlapping flag systems

`plasticos.gate.enrichment_enabled=1` allows **on-demand Gate requests** if URL/SDK configured. This is NOT automatic CRM writeback. The two existing writeback ICPs are both currently seeded OFF (`plasticos.gate.auto_writeback`, `plasticos.gate.auto_writeback_operator_approved`). Their config owner is `plasticos_gate`; this plan leaves it unchanged. The Odoo enrichment run must always route completed Gate results through per-field human review and refuse immediate CRM writes even if legacy ICPs are unexpectedly both true. Flag drift is a release-blocking finding, not approval.

## Compare-and-set semantics

At proposal preparation capture target ID, company, field name, presence/type and actual typed field snapshot; source packet identity/digest and review-time as-of metadata. At Apply Approved, acquire a PostgreSQL row lock through the Odoo ORM/cur cursor in the current transaction (only for concurrency; use ORM `res.partner.write` for business update). Re-evaluate current field under correct allowed-company scope and current allowlist/ACL, compare against proposal snapshot, and deny conflicts. Then write only approved compatible missing fields. On transaction rollback, neither target values nor applied provenance/line states may persist. Do not make manual commits in normal RPC methods.

## Confidence, evidence and retention

EIE's aggregate run confidence may legitimately be missing. Do not substitute 1.0. Applied field provenance must state actual origin: raw/parsed EIE statement when bound, `eie_run_only`, or explicitly operator-attested, never pretend confidence is calibrated per field. Protect raw result JSON/PII per company and keep original historical packet IDs. Do not use `source_sentence=gate_converge:{packet}` as evidence of a particular field's source location unless explicitly labeled a packet trace, not a citation.

## Denials and rollback

No public/portal action, no ordinary employee audit edit, no cross-company records, no partnerless lead-to-partner creation, no Gate SDK bypass, no auto/overnight job enable. On security or data-integrity failure, disable Apply Approved, retain secure review evidence and restore backed-up DB+filestore only when the specific recovery plan supports it. Never silently send data to an external source or resurrect local intelligence.

# ADR-012: CRM Writeback Allowlist, Merge-Not-Overwrite, and Provenance

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** How Gate `converge` results are applied to `res.partner`
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md) (amendment 2026-07-19 elevated here),
[ADR-010-odoo-consumer-trigger-ownership.md](ADR-010-odoo-consumer-trigger-ownership.md),
[ADR-011-intelligence-action-topology.md](ADR-011-intelligence-action-topology.md)

## Context

ADR-002’s 2026-07-19 amendment made enrichment converge live with allowlisted writeback. That rule is easy to miss when reading ADR-002 for hub topology alone. Agents need a dedicated binding ADR for CRM mutation semantics.

## Decision

### 1. Allowlisted partner fields only

Odoo may write from converge responses **only** these `res.partner` fields (unless a later ADR expands the list and bumps allowlist code + tests):

`name`, `website`, `city`, `zip`, `street`, `street2`, `email`, `phone`

Non-allowlisted keys in `final_fields` / `writeback.partner_fields` are ignored.

### 2. Merge-not-overwrite

Writeback fills **blank/falsy** partner fields only. Existing non-empty values are never clobbered by Gate converge auto-writeback.

### 3. Provenance required on live writes

Each applied field creates a `plasticos.enrichment.provenance` row (audit trail). Packet/correlation ids are stored on the enrichment run.

### 4. Auto-writeback toggle

| ICP | Behavior |
|-----|----------|
| `plasticos.gate.auto_writeback=1` (default) | Live apply allowlisted blanks; run → `injected` when successful |
| `plasticos.gate.auto_writeback=0` | Review-only: store `gate_proposal`, state `review`, **no** partner writes |

### 5. Confidence discipline

EIE should return only confidently resolved values. Merge-not-overwrite protects existing data, not empty fields — junk blanks still become live CRM data.

## Consequences

### Positive

- Safe live enrichment without silent overwrites.
- Auditable field lineage for operators and compliance.

### Negative / constraints

- Expanding the allowlist is a deliberate ADR/code change, not a mapper drive-by.
- Review-only mode requires operator follow-through to inject.

### Implementation rules (agents)

1. Change allowlist only with tests + this ADR update.
2. Do not bypass provenance on live writeback paths.
3. Prefer `writeback.partner_fields` when present; else `final_fields` (existing mapper contract).

## References

- ADR-002 amendment 2026-07-19 (historical; this ADR is the binding writeback SSOT)
- `plasticos_gate/services/gate_mappers.py` (`partner_writeback_from_converge`)
- `plasticos_enrichment` enrichment run Gate path

## Amendment 2026-11-13 — converge v2: three targets, a mapping table, an evidence-state write policy

**Authorized by:** operator decisions recorded for the cartridge-driven enrichment consumer campaign (CTO session `session_017xwbxuHzgYyNp8PADvkSnt`): amend this ADR to cover material and facility profiles ("Yes"); the evidence-state write policy ("yes"); three new stored fields ("3 fields approved").

This amendment adds to the decisions above. It does not rewrite them. Every v1 converge run is still governed by §1–§5, and `PARTNER_WRITEBACK_FIELD_ALLOWLIST` is unchanged.

1. **Contract selection.** A run uses converge v2 only when `plasticos.gate.converge_contract=v2` and the cartridge id and version are pinned (`plasticos.gate.converge_cartridge_id` / `_version`). Unset or `v1` keeps v1. The wire contract is EIE `docs/contracts/converge/request.v2.md` and `response.v2.md` (frozen 2026-11-13, including Revision 1).
2. **Three targets.** A v2 run may enrich exactly one record. That record is the partner (`res.partner`), one of that partner's material profiles (`plasticos.material.profile`), or one of its facility profiles (`plasticos.facility.profile`). The request entity stays `res.partner:<id>` (gate-integration ADR-005). A facility profile with no partner (lead-owned) cannot be enriched.
3. **The mapping table is the allowlist.** `CONVERGE_V2_TARGETS` in `plasticos_gate/services/gate_allowlists.py` has one reviewed row per (target, cartridge field). Each row names the Odoo model, the Odoo field, the value kind (char, float, integer, boolean, selection, many2one by code, many2many by code) and, for numbers, the units it accepts with their conversion factors. A cartridge field with no row is not requested and not written. Adding a row needs a change to that table, its tests and this ADR. There is no fixed field ceiling, and no field is open to every reply.
4. **Never targets.** No row may name `partner_id`, `company_id`, `active`, `polymer_id`, `form_id`, `material_grade_id`, `facility_profile_id`, `crm_lead_id`, latitude or longitude (`CONVERGE_V2_NEVER_TARGETS`). Computed, related, readonly and One2many fields are not targets either.
5. **Write policy by evidence state.** After human approval of the whole run, Odoo writes only values whose state is `inferred` or `external_claim` and that the engine marks `admitted`. It never writes `unknown`, `conflicting` or `observed`. A number is written only when the reply states a unit the row accepts. An absent or different unit is skipped and recorded, never converted by assumption.
6. **Merge-not-overwrite and master data.** §2 still applies: a field that already holds a value is not written. A code that resolves to no existing master record is skipped and recorded. No master record is ever created.
7. **Rejection.** An unrecognised `contract_version`, an unrecognised evidence `state`, a requested field with no entry, a malformed entry, or a reply resolved against another cartridge revision rejects all of that reply's evidence. Nothing is written, and the run records why. A v1-shaped reply to a v2 request writes nothing to a profile.
8. **Provenance.** Each field a v2 run considered gets one `plasticos.enrichment.provenance` row. The row names the target model, the target record (`target_res_id`) and the field, with the written value or the skip reason.

Left unmapped on purpose (`CONVERGE_V2_UNMAPPED`): `tier` (no Odoo home), `capacity_tons_month` (the cartridge declares no unit; Odoo stores lb/month), `material_grade`, `material_forms`, `certifications`.

### Amendment 2026-11-13 (b) — facility profile open by model definition

**Authorized by:** operator decision 2026-11-13, verbatim: "All fields in Odoo facility profile are open to https://github.com/Quantum-L9/Enrichment.Inference.Engine to read and write". It was relayed as a CTO directive in the same campaign.

This supersedes point 3 of the amendment above for `plasticos.facility.profile` only. The partner and material-profile tables are unchanged.

1. **Eligibility.** The facility profile has no hand-picked row list. Every data field of the model, including fields added by `_inherit` extensions, is eligible when it is all of the following:
   - stored;
   - not computed, related or readonly;
   - not One2many;
   - of a type converge can write (char/text, float, integer, boolean, selection, or many2one/many2many to a model with a `code` field);
   - not a never target (`CONVERGE_V2_NEVER_TARGETS` plus the mail, activity and stats prefixes).

   Eligibility is derived at run time from the model's own field definitions (`eligible_odoo_fields`, `derive_facility_profile_target`).
2. **Names.** A cartridge-declared field maps to the eligible Odoo field with the same name. `FACILITY_PROFILE_V2_ALIASES` lists only the names that differ:
   - `processed_polymers` → `accepted_polymer_ids`
   - `min_density` / `max_density` → `density_min` / `density_max`
   - `min_mfi` / `max_mfi` → `melt_index_min` / `melt_index_max`
   - `contamination_tolerance` → `contamination_tolerance_pct`
   - `capacity_tons_month` → `capacity_lbs_month`

   A cartridge field with neither a same-named eligible field nor an alias stays unmapped, and the reason is recorded.
3. **Read.** Filled eligible fields that map to a cartridge-declared field go out as request `observations`. That is the only per-field channel the frozen request contract accepts, so fields the cartridge does not declare are not sent.
4. **Write.** The engine can still only target fields the cartridge declares, and Odoo no longer narrows that set for the facility profile. Points 4–8 above still hold:
   - never targets are refused even when a reply proposes them;
   - merge-not-overwrite applies, and no master record is created;
   - only an exact unit converts a number. Capacity is written only as a whole number of pounds.
   - only evidence from an admitted state is written;
   - every write needs whole-run human approval;
   - every write carries provenance.

   A numeric facility field with no reviewed unit stays unmapped.

### Amendment 2026-11-13 (c) — one subject per request; vocabulary per cartridge version

Recorded by the CTO session for the same campaign. This adds to (b).

1. **Vocabulary per cartridge version.** The cartridge's declared field names, their declarations and the subject each one belongs to form a reviewed constant for each pinned cartridge version (`PLASTICOS_CARTRIDGES`; today only `0.5.0`). A pin with no reviewed entry fails closed.
   - Adopting a new revision means adding its names, declarations and subjects, then bumping the pin. An example is the 0.6.0 candidate, which declares facility-profile fields under Odoo's own names in the `facility` subject.
   - A same-named field needs no mapping row.
2. **One subject per request.** A facility-profile request carries one subject:
   - `material` holds the 0.5.0 capability fields. Runs request it today.
   - `facility` holds the 0.5.0 contact fields, `capacity_tons_month` → `capacity_lbs_month`, and future same-named fields. The derivation is ready (`resolve_v2_target(..., subject="facility")`), but no run sends that second request yet.
3. **Declarations compare by typed shape.** A map's `properties` may arrive as the engine emits them (an object keyed by name) or as the spec writes them (a list). `required` and `unit` are not part of the comparison.
4. **Numbers on 0.5.0.** Cartridge 0.5.0 declares no unit, so every number arrives with `unit_status: unknown`. Under decision 4, every number is skipped until a cartridge revision states units. This is the intended result.

### Amendment 2026-11-13 (d) — two targets; governing unit; cartridge 0.6.0 candidate

**Authorized by:** operator decisions of 2026-11-13, made on the engine side and relayed by the CTO session:
- cartridge 0.6.0 adds all 27 facility fields;
- capacity is in metric tonnes;
- contamination tolerance is in percent;
- `food_grade_certified` stays CEG-owned;
- the `material` subject means the facility's material capability.

This supersedes the "three targets" wording of the amendments above.

1. **Two targets.** A v2 run targets the partner or one of its facility profiles. The `material` subject describes a facility's overall capability, not one material, so no reply is written onto a `plasticos.material.profile`. A material profile cannot start a v2 run. The run gains `facility_profile_id`, and provenance gains `target_res_id`. These are the only two new stored fields.
2. **Governing unit.** This replaces the unit wording of decision 4.
   - A number is read in the value's own `unit` when `unit_status` is `stated`. Otherwise it is read in the cartridge's declared `unit` (`field_evidence[name].declaration.unit`, response.v2.md section 10.2).
   - It is written only when that governing unit is one the field accepts (`FACILITY_PROFILE_FIELD_UNITS`). No governing unit means the number is skipped and recorded.
   - On cartridge 0.5.0 no declaration carries a unit, so every number is still skipped.
   - `unit` is never part of a request's `targets[].type`.
3. **Capacity.** `capacity_tons_month` (`t/month`, metric tonnes) is multiplied by 2204.62262185 and rounded to the nearest whole lb, because `capacity_lbs_month` is an Integer. The provenance row keeps the original value and unit.
4. **Subjects.**
   - Capability fields go under subject `material`: `processed_polymers`, the densities, the MFIs and `contamination_tolerance`.
   - `capacity_tons_month` and every same-named 0.6.0 field go under subject `facility`.
   - Each request carries one subject.
5. **Cartridge 0.6.0.** Its names, typed declarations, units and subjects are in `PLASTICOS_CARTRIDGES`, marked as a candidate verified against EIE PR #348 at `bd345a0`. The default pin stays 0.5.0. Adopting 0.6.0 needs only the configuration pin.

## Amendment 2026-11-15 — scheduled EIE enrichment sweep (Odoo side)

**Decided by:** the operator, 2026-11-14/15, confirmed in the CTO session ("build the sweep").
**Contract:** Quantum-L9/Enrichment.Inference.Engine `docs/contracts/enrichment-sweep.md` at `a606791` (PR #352). Section numbers below cite it.
**Status:** built, switched off. Nothing runs until every step under "Switching it on" is done.

1. **What it is.** EIE runs a scheduled sweep over **buyers only**. Odoo picks which buyer facility profiles to offer. Odoo sends them through Gate as one `enrichment-sweep` action (section 3). Odoo then reads the results with `enrichment-sweep-results` (section 6). Odoo reaches EIE only through `plasticos_gate` (`send_sweep_action`, which calls `send_action`). It uses no EIE address and no new transport.
2. **Budget authority.** Odoo sends `daily_budget_usd` (`plasticos.gate.sweep_daily_budget_usd`, default `5.0`), which must be greater than 0. EIE owns the run and caps the budget at `min(daily_budget_usd, L9_SWEEP_MAX_DAILY_BUDGET_USD)` per tenant per UTC day (section 4). Odoo sets no ceiling of its own and never counts spend. It keeps the `budget` and `stats` objects EIE reports as audit data.
3. **Selection (Odoo).** A candidate is an active `plasticos.facility.profile` with an active partner. That partner, or its commercial partner, must have `customer_rank > 0`. The profile must also match the operator's filters (`plasticos.gate.sweep_*`): process type, application class and feedstock type (any of the listed keys), equipment and accepted polymers (any of), and minimum capacity. Three things exclude a profile: a run in `review`, a converge v2 run created inside `sweep_cooldown_days` (default 30), or being named in a sweep whose results are not yet collected. Candidates are ordered never-enriched first, then by oldest enrichment, then by id. The list is capped at `sweep_max_candidates` (default 50). One partner is one candidate, because the entity id is locked to `res.partner:<id>` (gate-integration ADR-005).
4. **Candidates.** One facility profile gives one candidate (section 3.1): `entity_id` is `res.partner:<partner_id>`, `node_label` is `Facility`, and `entity` holds the profile's current values in cartridge field names. The values cover every row of the facility-profile target derived over all the cartridge's subjects. EIE builds each converge request itself from CEG's readiness gaps (section 3.4): the targets, the pinned cartridge, the node, and the key `sweep-<sha256(sweep_id, entity_id)>`. Odoo builds no converge request for a sweep. The sweep refuses to run unless converge is v2 with a cartridge id, version **and sha256** pin, and it stores that pin on the sweep.
5. **Review-only writes.** Each result's `response` is the converge v2 body EIE stored. `parse_sweep_converge_response_v2` validates it against its own resolution echo, which must match Odoo's pinned id, version and sha256 and node `Facility`. It also validates it against the candidate: every identity is the entity id, with no subject type or role. The checks the interactive parser applies to a reply all still apply. `plan_sweep_converge_v2_writeback` applies the interactive per-field policy to every field with evidence. It uses the facility-profile target over all subjects, so any field EIE targeted can be reviewed. An undeclared or unmapped field is skipped and recorded as `unmapped`. A usable result becomes one `plasticos.enrichment.run` in `review`, or a `degraded` run with the reason. Approval (`action_inject`) re-validates the stored reply the same way. Nothing is written to a partner or profile before a human approves the run. The same sweep_id and entity_id never create a second run.
6. **States, skips and refusals.** A results page is `running` or `completed` only (section 6.2). The section 5 reasons (`budget_exhausted`, `no_readiness_gaps`, `no_declared_targets`, `readiness_*`, `converge_failed`, `sweep_failed`, `cartridge_unavailable`, `budget_ledger_unavailable`) are per-candidate skips. They are recorded per candidate on the sweep. Refusals are failure packets whose message begins with a code (section 7):
   - `sweep_not_found`: the sweep passed EIE's 72-hour retention. It is marked `expired` and no longer polled.
   - `disabled` on the send: the sweep fails and is never polled.
   - `disabled` or `sweep_store_unavailable` while polling: the sweep stays open.
   - Any other refusal fails the sweep.
7. **Relationship to ADR-009.** ADR-009 says this repo has no nightly enrichment queue. This amendment makes a narrow, operator-decided exception. Odoo applies **operator filters** to choose which buyers are offered to EIE, and orders them only by time since last enrichment. Readiness ranking and target choice stay in EIE and CEG (section 3.4). ADR-009 carries a dated pointer to this item.
8. **Operator approvals.** Two `ir.cron` records (`cron_enrichment_sweep_send` daily, `cron_enrichment_sweep_results` hourly) are seeded `active=False` and also gated on `plasticos.gate.sweep_enabled` (seeded `0`). The settings are system parameters only; no business model gains a stored field. The audit model `plasticos.enrichment.sweep` is new, with ACL rows: user read, manager read, write and create.
9. **Switching it on.** The steps, in order:
   1. The Gate owner registers both actions for the Odoo caller (Gate #43).
   2. EIE sets `L9_ENRICHMENT_SWEEP_ENABLED`, but only after Gate owns both actions (section 2).
   3. Set converge v2 with the cartridge id, version and sha256 pin.
   4. Set `plasticos.gate.sweep_enabled=1`.
   5. Activate both crons.

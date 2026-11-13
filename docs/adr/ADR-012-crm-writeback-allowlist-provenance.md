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

---
auto_generated: false
authority: derived-index
component_id: plasticos_gate
component_name: PlasticOS Gate Client
module_version: 19.0.1.11.1
layer: 2
installable: true
auto_install: false
application: false
depends:
  - base
  - plasticos_base
models_owned: []
models_extended: []
crons: []
---

# PlasticOS Gate Client

The front matter above is a derived index. `__manifest__.py` wins on any conflict. The manifest does not set `auto_install`; Odoo's default is false.

## What it does

The one Odoo client of the Constellation Gate. PlasticOS modules that need external intelligence (matching, enrichment) send an action and a payload through this module. Odoo never builds a `TransportPacket`.

## How it works

- **Send.** `services/gate_client.py` `send_action(env, action=..., payload=...)` builds the client configuration, admits the Odoo node with the Gate SDK (`ensure_admitted`), then calls `GateClient.execute(action, payload, ...)`. The SDK builds and signs the packet, sends it, and validates the response. Odoo supplies the action, the payload, the tenant, the correlation and idempotency keys, and the timeout budget.
- **Failures.** A Gate transport failure is re-raised as `GateIntegrationError` with a failure class (`TransportFailureClass`) that callers store on their run records. Any other exception is re-raised unchanged.
- **Wrappers.** `send_match_action` and `send_converge_action` call `send_action` with the action named by `get_matching_action` and `get_enrichment_action`.
- **Builders.** `services/gate_builders.py` turns Odoo records into typed requests (`build_converge_request`, `build_match_request`, `build_web_lead_request`, `build_intake_request`) defined in `services/gate_contracts.py`. `services/semantic_payloads.py` projects approved records into supply and demand payloads.
- **Mappers.** `services/gate_mappers.py` turns Gate responses back into Odoo values, such as `map_match_response` and buyer partner ids.
- **Configuration.** `services/gate_config.py` reads the Gate URL from the process environment only, never from a system parameter. `classify_gate_availability` returns a structured verdict and never raises. The other settings are system parameters seeded in [`data/gate_icp_seed.xml`](data/gate_icp_seed.xml) (`noupdate="1"`), for example `plasticos.gate.matching_enabled`, `plasticos.gate.enrichment_enabled`, `plasticos.gate.timeout_seconds`, and `plasticos.gate.auto_writeback`.
- **Allowlists.** `services/gate_allowlists.py` holds the partner field maps used in payloads and writebacks.
- **Converge v2.** `plasticos.gate.converge_contract` selects the converge contract. It is `v1` by default, and v1 requests and replies are unchanged. `v2` also needs `plasticos.gate.converge_cartridge_id` (the Gate tenant, `plasticos`) and `plasticos.gate.converge_cartridge_version`; `plasticos.gate.converge_cartridge_sha256` is optional. A half-configured `v2` fails closed (`resolve_converge_contract`). The contract is EIE `docs/contracts/converge/request.v2.md` and `response.v2.md`, frozen 2026-11-13.
  - There are two v2 targets: the partner and its facility profiles. No v2 run targets a material profile (ADR-012 amendment 2026-11-13 (d)). `CONVERGE_V2_TARGETS` in `services/gate_allowlists.py` is the v2 writeback allowlist for the partner. It has one reviewed row per cartridge field and Odoo field. A cartridge field with no row is not requested and not written. `CONVERGE_V2_UNMAPPED` lists the fields left out and why.
  - The facility profile is open by model definition (ADR-012 amendment 2026-11-13 (b)). The caller passes the model's field definitions (`OdooFieldDef`). `derive_facility_profile_target` maps every cartridge field that has an eligible same-named Odoo field, or an entry in `FACILITY_PROFILE_V2_ALIASES`, and records why the others stay unmapped. An eligible field is stored, not computed, related or readonly, and not a never target. Each request carries one subject. `material` is the subject runs send today. `facility` is derived the same way and is ready. The cartridge vocabulary is a reviewed constant per pinned cartridge version (`PLASTICOS_CARTRIDGES`).
  - `build_converge_request_v2` requests the mapped fields that are empty on the record. It sends the filled ones as `observations`. The entity stays `res.partner:<id>`.
  - `parse_converge_response_v2` validates a reply and freezes it. A reply without `contract_version` is v1. An unknown contract or state, a missing entry, a malformed entry, a different cartridge revision, or a run that did not complete rejects all of the reply's evidence.
  - `plan_converge_v2_writeback` applies the write policy. It writes only admitted `inferred` and `external_claim` values. A number is written only in its governing unit: the value's stated unit, or else the cartridge's declared unit. That unit must be one the field accepts (`FACILITY_PROFILE_FIELD_UNITS`). Capacity converts t/month to whole lb/month. It never writes `unknown`, `conflicting` or `observed` values.
- **Enrichment sweep.** `services/gate_sweep.py` is the only module that knows the `enrichment-sweep` and `enrichment-sweep-results` wire shape. Its authority is EIE `docs/contracts/enrichment-sweep.md` at `a606791` (`CONTRACT_REF`). It defines frozen request and reply types. Its parsers reject a whole reply on an unknown member, a wrong type, a state other than `running` or `completed`, a reason code the contract does not name, or a page for another sweep. `refusal_code` reads the section 7 code from a failure message. `send_sweep_action` calls `send_action`. It asks Gate admission for the two sweep actions on top of `match` and `converge`; the receipt key carries the full action set, so the interactive key is unchanged. EIE builds each sweep converge request itself, so Odoo builds none. `build_sweep_candidate` sends the profile's current values over every cartridge subject (`derive_facility_profile_target_all_subjects`). `parse_sweep_converge_response_v2` validates a stored result against its own resolution echo (Odoo's cartridge id, version and sha256, node `Facility`) and the candidate's entity id. `plan_sweep_converge_v2_writeback` applies the interactive per-field policy (`_decide`) to every field with evidence, and records undeclared or unmapped fields as `unmapped`. The interactive parser and planner are unchanged. (ADR-012 amendment 2026-11-15)
- **Cutover guards.** `services/dual_write.py` and `services/field_family_cutover.py` read their system parameters and fail closed if a decision would restore local intelligence authority.

## Models

None. This module defines no ORM model. [`models/dual_write_audit.py`](models/dual_write_audit.py) holds constants only: the dual-write system parameter key, its default, and the names of retired local authorities.

## Runtime

- Python dependency: `constellation_node_sdk` (manifest `external_dependencies`). `send_action` refuses to run without it.
- The Gate URL comes from the process environment. Credentials and signing keys are deployment configuration and are not stored in this repository.
- No cron, no views.

## Boundaries

- It does not rank, match, or enrich. It carries requests and responses.
- It does not construct, route, or sign a `TransportPacket`; the SDK does.
- Callers are whatever imports `plasticos_gate.services`. Find them with `grep -rn "plasticos_gate.services" --include=*.py .`

## Read next

- [`services/gate_client.py`](services/gate_client.py)
- [`services/gate_config.py`](services/gate_config.py)
- [`../docs/adr/ADR-002-gate-hub-phased-autonomy.md`](../docs/adr/ADR-002-gate-hub-phased-autonomy.md)
- [`../docs/adr/ADR-003-single-external-intelligence-authority.md`](../docs/adr/ADR-003-single-external-intelligence-authority.md)

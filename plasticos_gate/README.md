---
auto_generated: false
authority: derived-index
component_id: plasticos_gate
component_name: PlasticOS Gate Client
module_version: 19.0.1.9.9
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

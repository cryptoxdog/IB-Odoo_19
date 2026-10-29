# Addon placement and dependency integrity

## Current evidence

The bundled manifest census is 30 modules at Odoo Staging `677d734fd88615d673501d91de88734b7150ff50`. The manifest DAG is the source, not old layer diagrams. `plasticos_semantic_kernel` depends on mail, material profile, facility profile and intake. `plasticos_gate` depends on base and plasticos_base. The mandatory CRM bridge already owns prospect facility/material behavior but does not depend on the optional kernel.

## Proposed optional integration addon

`plasticos_semantic_bridge` is a **proposed path**, not an existing addon. Its exact minimum direct dependencies are to be validated against touched fields/imports, initially:

- `crm`, `mail` for explicit native models/actions it extends.
- `plasticos_semantic_kernel` for passive semantic records.
- `plasticos_crm_bridge` for established material/facility ownership and native opportunity links.
- `plasticos_gate` for the sole integration transport seam.
- `plasticos_matching` for current canonical match/run consumption.
- `plasticos_enrichment` only if its actual runtime proposal/results surface is reused by the chosen design; remove this edge if no direct consumer exists.

These edges point from optional integration to existing owners. No existing mandatory addon acquires a dependency on this bridge. The kernel itself remains passive and does not acquire Gate/CRM orchestration code. Adding this leaf cannot create a source-DAG cycle unless an existing owner is also changed to depend back on it; such a reverse edge is prohibited.

## File-placement test

Before each proposed new file is accepted, ask whether an existing source owner can lawfully carry the responsibility. The new bridge is admitted only after F05 establishes that existing owners cannot integrate optional semantic data and native source events without coupling the default install or violating passive-kernel boundaries. A new durable operation model is admitted only if current dual_write/run persistence cannot handle lifecycle publish/replay/disable correctly.

No new hypothesis table is proposed merely because hypotheses are a new feature. EIE's durable evidence remains its owner; existing material/capacity/rule evidence records and native read-only review may be enough. Any additional record requires a discriminating loss-of-meaning proof and a plan revision.

## Protected modules

Do not change base material identity or CRM reconciliation just because the base profile file says partner required: the installed CRM inheritance already makes it optional under a real owner. Do not modify PO/offer code to consume invented semantic events. Native commercial milestones remain the sibling campaign's contract.

## Census limits

The six reverse-manifest candidates are accounted for in `case.json`; extra native/DB/external consumers are separately tracked. The actual installed registry, dynamically generated fields/actions, inherited Enterprise models and optional addons may expose additional effects. F01 blocks dependent implementation until that census is complete. A manifest graph or grep is not proof of runtime completeness.

## Per-version update

Every changed runtime addon gets a monotonic manifest bump above the actual installed version. Register new models, tests, view/security files and data through their actual init/manifest owners. Plan migration directories from those admitted versions at U00/U01; never invent a numeric upgrade path based only on source manifest text.

# Converge v2 reply fixtures (synthetic)

Hand-built replies to the requests `tests/test_gate_converge_v2_codec.py` builds,
shaped by EIE `docs/contracts/converge/response.v2.md` (FROZEN 2026-11-13,
including Revision 1: `resolution`, `declaration`, source type `graph`) at
Quantum-L9/Enrichment.Inference.Engine `b1b295a`.

| File | Target | Shows |
|---|---|---|
| `response_partner.json` | `res.partner:55` (subject `facility`, role `supplier`) | admitted `external_claim`, admitted `inferred` from a claim, `unknown`, `conflicting`, an unadmitted claim, an extra `observed` entry |
| `response_material_profile.json` | material profile of `res.partner:56` (subject `material`, role `supplier`) | stated accepted unit, foreign unit, `not_applicable` unit on a number, admitted `inferred` |
| `response_facility_profile.json` | facility profile of `res.partner:57` (subject `material`, role `buyer`) | list-of-codes value, `fraction` → percent conversion, `unknown` |

All data is synthetic.

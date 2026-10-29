# Equipment semantic owner and integration boundary (v1.1.0)

| Fact | Owner | Export responsibility |
| --- | --- | --- |
| Operational domestic trailer / transport type | Native transport/logistics owner (exact Odoo fit to be verified) | Display link only |
| Available ocean equipment type choice | Existing native transport vocabulary if suitable, else smallest suitable logistics-owned reference | Use for requested booking unit type |
| Export booking requested equipment type and quantity | `plasticos_export` | Preserve booking request and amendments |
| Actual ISO container ID / seal, trucking load, dispatch | Existing Logistics/physical shipment owner; possible narrow export-only identity gap to be proven | Link and display, never duplicate writer |
| Packages, weighed cargo and stock movement | Native Odoo Stock/validated scale facts | Scan and project only through native stock process |
| Original booking confirmation / updated carrier notice / VGM evidence | Native Odoo Documents | Link to exact source only |
| Document classification, verification and compliance verdict | `plasticos_documents` | Project current verdict |
| External communication and carrier coordination | `plasticos_logistics`/Linda via native Mail | No secondary sender |
| Facility capabilities (balers, grinders etc.) | `plasticos_facility_profile` / `plasticos.equipment.type` | NOT a transport type master |

**Semantic distinction:** domestic trailer length/type, nominal ISO ocean container size and height, individual equipment ID, container seal, origin-to-port drayage leg and booking request are not synonyms. Carrier availability and actual payload are never inferred from equipment labels.

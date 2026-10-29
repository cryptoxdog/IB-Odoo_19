# Export transport equipment: conceptual fields and displays

| Field / value | Meaning | Scope | Owner |
| --- | --- | --- | --- |
| transport equipment family | domestic trailer / maritime freight container | shared | logistics/native transport catalog, if absent |
| domestic trailer type | 53-foot, 48-foot, flatbed | domestic leg | logistics |
| maritime type | 40HC (default for plastics), 40STD, 45HC, 45STD, 20STD | ocean booking | catalog/native reuse plus Export booking reference |
| requested count | number of units requested, may exceed one | booking | export booking |
| requested type | nominated equipment type, preserve source | booking | export booking |
| supplied/actual type | actual equipment type and source | physical shipment | logistics/native shipping owner, precise fit TBD |
| ISO container number | unique physical ocean unit; not booking number | ocean unit | existing owner where available, else prove narrow seam |
| container seal | physical cargo security evidence | each ocean unit | linked Logistics/source evidence |
| origin/destination load and cargo package links | exact source inventory and movement | logistics/stock | native Odoo stock and logistics |
| gross/tare/VGM | original scale/verified shipping evidence, not nominal size | physical unit | native stock/evidence owner |

P1 uses both domestic and maritime equipment where applicable to FAS port/rail handoffs; P2 adds seller-booked ocean carriage. No new global transport capacity table or automatic fixed payload limit is justified yet. Unsupported 45STD/other combinations remain available as explicit choices but show carrier/route availability UNVERIFIED until proved. Flatbed length must be supplied when material.

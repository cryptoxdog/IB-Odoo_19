# ADR-126: Odoo semantic Gate payload mappers

## Status
Accepted (TASK-027)

## Decision
`plasticos_gate.services.semantic_payloads` projects supply opportunity and buyer demand ORM records into peer PACK-029 payloads. TransportPacket identity/routing fields stay out of the payload. Quantity and window ordering are enforced at build time. Match wrappers expose `supply_opportunity_to_buyer_facility` and `buyer_demand_to_supply_opportunity` directions only through `plasticos_gate`.

# ADR-125: Split opportunity protocol

## Status
Accepted (TASK-039)

## Decision
Retire the combined opportunity-protocol discriminator. Ship peer payloads `supply-opportunity` and `buyer-demand` with runtime cross-field validators for quantity ordering and time windows. ORM constraints mirror the same rules on `plasticos.supply.opportunity` and `plasticos.buyer.demand`.

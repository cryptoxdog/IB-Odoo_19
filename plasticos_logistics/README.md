---
component_id: "plasticos_logistics"
component_name: "Plasticos Logistics"
module_version: "19.0.1.6.0"
layer: "core"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Load management, dispatch, and delivery tracking"
summary: "Logistics coordination with trucker communications"
---

# Plasticos Logistics

## Purpose
Load management, dispatch, and delivery tracking

## Summary
Logistics coordination with trucker communications

## Structure
```
BOL - DELIVERY-59422.pdf
BOL - PICKUP-59422.pdf
DELIVERY ORDER-59422.pdf
README.md
README.rst
__init__.py
__manifest__.py
data/
models/
report/
security/
services/
views/
wizards/
```

## Dependencies
sale_management, stock, mail

## Models
plasticos.dispatch, plasticos.rate.memory, plasticos.load

## Tier
core

## Linda Deterministic Freight Policy

Linda freight estimation and quote recommendation are owned by this module. They do not depend on
Constellation Gate, Cognitive Engine Graphs, Enrichment Inference Engine, an LLM, or an external
freight-pricing service.

### Nonbinding estimate

`plasticos_logistics.services.freight_estimation` calculates a validated Haversine great-circle
feature, then weights matching-currency executed outcomes using:

```text
weight = 1 / max(origin_delta + destination_delta + lane_length_delta, 1 mile) × exp(-age_days / 180)
target = sum(observed_amount × weight) / sum(weight)
floor  = minimum observed matching-currency outcome
ceiling = maximum observed matching-currency outcome
```

The estimate is immutable evidence, never a carrier assignment or rate confirmation. There is no
embedded road multiplier, fixed dollar-per-mile rule, fuel factor, market coefficient, currency
conversion, or fabricated fallback value. Invalid geocodes and insufficient matching-currency
evidence remain classified evidence gaps.

### Recommendation-only quote ranking

`plasticos_logistics.services.freight_quote_ranking` ranks only valid, active, current-context
quotes. The documented score weights price (55%), lane-history fit (20%), carrier-history fit
(15%), response recency (5%), and timeliness (5%). Invalid, expired, stale, inactive, or blocked
carrier responses are excluded. Ranking never sets `selected`, confirms a load rate, changes a load
state, or sends mail; a logistics operator retains those actions.

### Deferred Gmail intake

Inbound mailbox ingestion for `logistics2@scrapmanagement.com` is deferred until the mailbox OAuth
authorization is supplied. When authorized, it must create idempotent response evidence from Gmail
messages without sending, deleting, or modifying mail.


## Related Documentation

- `ARCHITECTURE.md` — # ARCHITECTURE.md — PlasticOS System Architecture  **Repository**: cryptoxdog/IB...
- `DEPLOYMENT.md` — # DEPLOYMENT.md — PlasticOS Deployment Guide  **Repository**: cryptoxdog/IB-Odoo...

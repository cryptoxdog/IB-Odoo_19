---
component_id: "plasticos_logistics"
component_name: "Plasticos Logistics"
module_version: "19.0.1.8.0"
layer: "core"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Load management, dispatch, delivery tracking, and Odoo-local deterministic freight evidence"
summary: "Logistics coordination with trucker communications plus SAL, manual-only RFQ, estimate, and calibration evidence"
---

# Plasticos Logistics

## Purpose
Load management, dispatch, delivery tracking, and Odoo-local deterministic freight evidence

## Summary
Logistics coordination with trucker communications plus Same As Last (SAL) resolution, manual-only RFQ
evidence, nonbinding local estimates, and append-only calibration observations

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
migrations/
models/
report/
security/
services/
views/
wizards/
```

## Dependencies
plasticos_base, plasticos_transaction, sale_management, stock, mail

## Models
- `plasticos.load` — load spine, SAL provenance, freight context, recorded actuals
- `plasticos.dispatch` — dispatch records
- `plasticos.load.dashboard` — SQL-view dashboard (read-only)
- `plasticos.freight.quote.request` — manual-only RFQ episode (immutable identity, workflow-owned lifecycle)
- `plasticos.freight.quote.recipient` — recipient delivery/response ledger (workflow-owned evidence)
- `plasticos.freight.quote` — immutable carrier response evidence; ranking is recommendation-only
- `plasticos.freight.estimate` — immutable nonbinding local estimate evidence
- `plasticos.freight.event` — immutable correlated freight event log
- `plasticos.freight.calibration.observation` — append-only actual-cost calibration (one initial + one direct successor)
- `plasticos.rate.memory` — legacy rate cache, frozen (read-only outside migration context)
- `plasticos.rate.memory.reconciliation` — immutable legacy-cache reconciliation evidence
- Transient: `plasticos.load.bulk.update.wizard`, `plasticos.freight.actual.correction.wizard`

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

Estimate identities are idempotent for the same source load, freight context, and evidence
fingerprint. Canonical freight context v3 uses only declared structured location facts and current
company-local history; formatted-address presentation fields do not affect the context identity.
All estimate, calibration, and event evidence is server-created through authorized load actions,
immutable after creation, and company-scoped.

### Recommendation-only quote ranking

`plasticos_logistics.services.freight_quote_ranking` ranks only valid, active, current-context
quotes. The documented score weights price (55%), lane-history fit (20%), carrier-history fit
(15%), response recency (5%), and timeliness (5%). Invalid, expired, stale, inactive, or blocked
carrier responses are excluded. Lane and carrier history use only the quote currency; no currency
conversion or cross-company evidence is silently introduced. Ranking never sets `selected`, confirms
a load rate, changes a load state, or sends mail; a logistics operator retains those actions.

### Deferred Gmail intake

Inbound mailbox ingestion for `logistics2@scrapmanagement.com` is deferred until the mailbox OAuth
authorization is supplied. When authorized, it must create idempotent response evidence from Gmail
messages without sending, deleting, or modifying mail.


## Related Documentation

- `ARCHITECTURE.md` — # ARCHITECTURE.md — PlasticOS System Architecture  **Repository**: cryptoxdog/IB...
- `DEPLOYMENT.md` — # DEPLOYMENT.md — PlasticOS Deployment Guide  **Repository**: cryptoxdog/IB-Odoo...

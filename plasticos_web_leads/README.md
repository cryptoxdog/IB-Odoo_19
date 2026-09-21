---
component_id: "plasticos_web_leads"
component_name: "PlasticOS Web Leads"
module_version: "19.0.2.6.3"
layer: "integration"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Provider-neutral inbound web-lead triage"
summary: "Cognito admission, deterministic evidence, and human-reviewed HOT intake handoff"
---

# PlasticOS Web Leads

## Purpose

This module captures inbound seller submissions and routes them through local Odoo Phase-1 triage. Cognito Forms is the current internal adapter. The module preserves raw provider payloads, creates a provider-neutral immutable packet for retries, acquires attachment evidence into Odoo storage, and delegates HOT/COLD decisions to the existing deterministic classifier.

## Boundaries

`plasticos.web.lead` remains the durable state owner. The adapter layer is pure Python and does not make commercial decisions. `classification_engine.py` remains the only HOT/COLD authority. A HOT result creates an intake without a partner and schedules human review; it does not auto-create a partner, call Gate, or send an offer.

## Durable audit data

Packet-backed leads persist `provider_key`, `provider_external_id`, `canonical_payload`, and `evidence_bundle`. The raw payload remains provider provenance. The canonical packet is used for retry without reparsing a provider-specific submission. Attachment evidence records both source identity and content SHA-256; PDFs are stored with explicit unsupported-analysis evidence in V1.

## Quantity semantics

The canonical path keeps per-load mass, current inventory counts, and cadence separate. Explicit pounds, kilograms, and tons are deterministic mass evidence. Unit counts such as loads, pallets, gaylords, and bales are never converted into assumed pounds. Unknown cadence remains unknown rather than being silently represented as zero.

## Dependencies

`base`, `mail`, `utm`, `plasticos_facility_profile`, `plasticos_intake`, `plasticos_material_profile`, and `purchase`.

## Public API compatibility

The existing endpoints remain unchanged:

- `POST /api/v1/cognito-webhook`
- `POST /api/v1/web-lead`
- `GET /api/v1/web-lead/health`

Inbound API key comparison uses a timing-safe comparison. Credentials and signed attachment URLs must never be committed or placed in routine logs.

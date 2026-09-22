---
component_id: "plasticos_web_leads"
component_name: "PlasticOS Web Leads"
module_version: "19.0.2.7.1"
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

`plasticos.web.lead` remains the durable state owner. The adapter layer is pure Python and does not make commercial decisions. `classification_engine.py` remains the only HOT/COLD authority. A HOT result creates an intake, schedules human review, and—when `plasticos_crm_bridge` is installed—creates one traceable CRM lead linked to that intake. It does not auto-create a partner, call matching, create an offer, or send an offer.

## Durable audit data

Packet-backed leads persist `provider_key`, `provider_external_id`, `canonical_payload`, and `evidence_bundle`. The raw payload remains provider provenance. The canonical packet is used for retry without reparsing a provider-specific submission. Attachment evidence records both source identity and content SHA-256; PDFs are stored with explicit unsupported-analysis evidence in V1.

Each HOT lead must receive a broker decision. Approval is blocked until a configured provider has completed the economic-opportunity assessment. It then produces an immutable `plasticos.web.lead.review.snapshot` containing canonical facts, reconciled evidence, deterministic triage, and that assessment. Future matching and commercial automation must use that approved snapshot rather than mutable lead fields.

## Quantity semantics

The canonical path keeps per-load mass, current inventory counts, and cadence separate. Explicit pounds, kilograms, and tons are deterministic mass evidence. Unit counts such as loads, pallets, gaylords, and bales are never converted into assumed pounds. Unknown cadence remains unknown rather than being silently represented as zero.

## Opportunity policy

The normal HOT threshold is retained for polymer grades such as **LDPE film**. A lower configured threshold applies only when admission evidence identifies a code on the explicit reusable-item allow-list, initially `PLASTIC_PALLETS`, `PALLETS`, `TOTES`, or `CRATES`. An unknown commercial source does not lower any threshold. Deterministic qualification remains authoritative, while unresolved commercial evidence produces a broker-review requirement.

## Swappable inference roles

The configuration singleton selects an independent provider, model, and transport for text normalization, visual analysis of each admitted image, and final economic-opportunity assessment. Each role can use a native Anthropic Messages transport or an OpenAI-compatible transport; changing the selected provider or model requires only a Settings update. Provider metadata is stored without API credentials. If a provider is missing or fails, the error is retained as bounded evidence and the lead requires broker review rather than receiving a fabricated commercial recommendation.

## CRM and material-profile handoff

The CRM bridge uses the originating HOT intake to create a single CRM lead, avoiding duplicate intakes during qualification. When a broker or salesperson converts that CRM lead into an opportunity and prepares the intake, the bridge reuses the original intake, creates or links the supplier identity, creates the canonical material profile from the intake if needed, and assigns that profile to the CRM record. This preserves a traceable route from web submission through opportunity preparation without implying that a match or offer was already approved.

All admitted image evidence available at each commercial handoff is copied to both the CRM lead and its material profile. The synchronization reads the linked web lead, originating intake, and any offer already created for that intake. Cognito provider-source identity is preserved so separate uploads with identical bytes remain separate evidence, while legacy or manually added images are deduplicated by checksum. The **Images** smart button on the CRM lead is an idempotent reconciliation action for images added after the initial handoff; it does not re-download external files or expose attachment URLs.

## Dependencies

`base`, `mail`, `utm`, `plasticos_facility_profile`, `plasticos_intake`, `plasticos_material_profile`, and `purchase`.

## Public API compatibility

The existing endpoints remain unchanged:

- `POST /api/v1/cognito-webhook`
- `POST /api/v1/web-lead`
- `GET /api/v1/web-lead/health`

Inbound API key comparison uses a timing-safe comparison. Credentials and signed attachment URLs must never be committed or placed in routine logs.

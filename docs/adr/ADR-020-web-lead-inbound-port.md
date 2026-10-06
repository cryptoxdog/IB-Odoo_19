# ADR-020: Web-Lead Inbound Port

**Status:** Accepted
**Date:** 2026-10-01
**Deciders:** Igor Beylin
**Scope:** How external form tools deliver a seller submission into `plasticos.web.lead`
**Related:**
[ADR-016-web-lead-triage-boundary.md](ADR-016-web-lead-triage-boundary.md)

## Context

`plasticos_web_leads` was built for an n8n agent that posted a pre-classified payload to `POST /api/v1/web-lead`, and for a Cognito-named webhook that still required that agent because Cognito Forms cannot send an `Authorization` header. PR #187 added a provider-neutral packet underneath those Cognito-shaped edges. The HTTP boundary, the legacy agent method, and several Cognito parsers stayed Cognito-specific, so a second form tool would still have required controller and model edits.

Cognito Forms posts JSON to a URL configured per form, retries HTTP 4xx/5xx up to 15 times over 72 hours (except 404, 410, and 413), and does not sign the body. File links expire in about 30 minutes.

## Decision

1. Odoo owns the inbound port in `plasticos_web_leads/adapters/base.py`: `WebLeadAdapter`, `WebLeadPacket`, `InboundEvent`, and `InboundRequest`. Changing a signature there is a port change and must update every registered adapter together. `PACKET_SCHEMA_VERSION` stays `web-lead-packet/v1` until the packet fields change.
2. The only admission route is `POST /api/v1/web-lead/inbound/<provider_key>`. `POST /api/v1/cognito-webhook` is an alias for `cognito`. `POST /api/v1/web-lead` and `create_from_agent` are removed.
3. Authentication is the adapter's job. The default accepts `?access_token=`, `Authorization: Bearer`, or `X-API-Key`, compared with `hmac.compare_digest` against `plasticos.web.lead.config.api_key`. A provider that signs the body overrides `authenticate` without changing the controller.
4. Only a `submitted` event creates a lead. `updated` and `deleted` return HTTP 200 `{"status":"ignored"}` and do not mutate a lead.
5. A parseable submission that fails adapter validation is stored as `state="error"` and answered with HTTP 200 `{"status":"rejected"}`, so the sender does not retry a permanent failure. Malformed JSON is HTTP 400. An unknown provider is HTTP 404.
6. `tests/test_web_lead_adapter_contract.py` instantiates every registered adapter and checks the port. Adding a provider without passing that test fails CI.
7. Triage stays the Phase 1 local pipeline in ADR-016. This ADR does not move triage to Gate, and it does not pull files from a provider REST API.

## Consequences

- Cognito Forms Submit Entry Endpoint posts directly to `/api/v1/web-lead/inbound/cognito?access_token=<api_key>`. n8n is no longer on the path.
- A replacement form tool is one new `adapters/<tool>.py` plus one line in `adapters/registry.py`, plus credentials. The controller, `admit_inbound`, and triage do not change.
- Synchronous triage still runs inside the webhook request. If a staging measurement shows Cognito timing out, a later ADR must move triage off the request. That change is not part of this decision.
- Cognito REST file recovery and a Settings JSON field map are deferred.

## Operator cutover (after this module is upgraded)

1. Regenerate the web-lead API key in Odoo Settings and store it as `ODOO_WEB_LEAD_API_KEY` in Infisical (`Cursor-Governance`, `prod`, `/`).
2. Set `ODOO_WEB_LEAD_WEBHOOK_PATH` to `/api/v1/web-lead/inbound/cognito`.
3. Point the Cognito Submit Entry Endpoint at `https://<staging-host>/api/v1/web-lead/inbound/cognito?access_token=<api_key>`.
4. Submit one real form on staging and confirm one `plasticos.web.lead` with `provider_key=cognito` and a single triage run. Record the request duration.
5. After that submission succeeds, retire the n8n workflow and the Infisical names `N8N_API_KEY`, `N8N_API_URL`, and `N8N_WORKFLOW_HOST`.

## Compliance

- ADR-016 remains binding: no Gate call in triage.
- Rule `50-plasticos-web-lead-guard` still forbids partner creation in the triage path and edits to the write/unlink guards.

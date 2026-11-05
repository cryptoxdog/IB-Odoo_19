# Phase 2 provider contracts and source references

## FindTEU (requested Phase 2 integration)

- Scope: ocean container/booking tracking, carrier and port milestone events, ETD/ETA revisions and source-backed operational exceptions. Exact company + booking + container + journey identity required.
- FindTEU API docs describe `X-Authorization-ApiKey`, container/booking tracking and webhook push updates. Handle provider-specific rate limits and errors without promising coverage for every line.
- Design boundaries: no booking/dispatch or stock ledger; don't infer actual status from an ETA or FindTEU `container.completed`; retain raw event evidence and timestamps.
- Probe: validate provider credentials/coverage and webhook authenticity method, source freshness, out-of-order replay, tenant isolation, and booking 6509024800 with multiple containers before claiming connected status.
- Sources checked 2026-10-28: https://www.findteu.com/api-docs ; https://www.findteu.com/for-developers ; https://www.findteu.com/container-tracking-api

## ACE AESDirect (requested Phase 2 filing support)

- Scope: determine EEI applicability and authorized filer; prepare and validate sourced data; hand off to ACE AESDirect through the portal, and where provider-tested, AES WebLink or supported bulk upload; retain official filing results including acceptance ITN or rejection; support amendments through authorized actor.
- AES WebLink prepopulates the official interface: the filer still logs in and submits. EDI Bulk Upload requires conforming AESTIR/X12 601 data. Uncertified direct transmission is explicitly not in this phase; it requires a separate certification decision.
- Do not treat an ITN as proof of a full legal compliance clearance or international shipment delivery. No auto-filing/certification claims.
- Probe: official sample-format validation, authorized portal login, missing-data blocks, ITN/acceptance/rejection evidence, amendment workflow, role segregation and exact shipment matching.
- Sources checked 2026-10-28: https://www.census.gov/foreign-trade/aes/introduction.html ; https://www.census.gov/foreign-trade/aes/ace-aesdirect.html

## Implementation/admission gates

Source data: cryptoxdog/IB-Odoo_19@04bd0594a7c9dcad53d9c45fc65276d76817c112 was the prior code snapshot used for the underlying Export BRS. This extension is only a source-verified provider-design addition; current Odoo integration code and runtime were not re-inspected or tested. Each provider is optional for tenant operation and feature-gated. Never send actual customer shipment data to providers without applicable authorization, commercial access, security verification and scope approval.

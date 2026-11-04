# BRS-EXP-12: Phase 2 provider integrations (FindTEU + ACE AESDirect)

**Scope:** Phase 2 international-selling functionality ONLY. Native-first, non-blocking external adapters; Phase 1 behavior is unchanged.
**Authority:** Operator selected FindTEU and ACE AESDirect for Phase 2 on 2026-10-28. Precise implementation mechanics remain DESIGN and require source/Enterprise/runtime acceptance.
**Status:** Planning BRS; not admitted into the Odoo repository. Integration credentials, contractual access, external filings, certification and live tests are NOT_RUN.
**Clarification:** The two adapters have distinct responsibilities: FindTEU supplies third-party ocean tracking **evidence**; AESDirect supports an authorized human **filing workflow**, not automatic customs clearance.

## Rules

### BRS-EXP-12-R001: FindTEU Phase 2 tracking adapter

**LOCKED · P2 · owner: `plasticos_export integration boundary; provider is external evidence producer`.** Phase 2 SHALL include a separately configurable FindTEU adapter for available ocean container tracking and ETA/terminal milestones, using its documented API and authorized account. It SHALL be optional for operation of the core ERP and Phase 1, and SHALL not book carriers, set rates, dispatch drayage, perform stock movements or create a competing shipment registry.

- **Positive:** An international shipment with FindTEU enabled displays source-labeled observed container milestones; the same Phase 1 booking works unchanged when the connector is disabled.
- **Negative:** An unavailable FindTEU account blocks Phase 1 purchasing, receiving or Linda dispatch, or tracking status directly creates freight bookings.
- **Related existing BRS:** BRS-EXP-05-R003,R006; BRS-EXP-01-R001,R002.
- **Acceptance:** `AC-EXP-12-001` / NOT_RUN.

### BRS-EXP-12-R002: Exact container identity and optional booking-number tracking

**DESIGN · P2 · owner: `plasticos_export typed mapping; native Odoo shipping identity remains canonical`.** The FindTEU adapter SHALL bind a company-scoped provider observation to the exact known container and applicable ocean booking, with carrier/SCAC when known, including bookings with many containers. Booking-level tracking SHALL never assign a provider event to every container merely because they share an ocean reservation. Unknown, reused or conflicting identifiers require review.

- **Positive:** Booking 6509024800 has five containers: a tracking event for CSNU8490558 is linked only to that identified container and the correct journey.
- **Negative:** A booking-number webhook blindly marks all five containers loaded, or an old container reuse event is attached to the current booking.
- **Related existing BRS:** BRS-EXP-02-R001; BRS-EXP-07; BRS-EXP-08; BRS-EXP-09-R003.
- **Acceptance:** `AC-EXP-12-002` / NOT_RUN.

### BRS-EXP-12-R003: Carrier observation is not commercial or stock authority

**DESIGN · P2 · owner: `plasticos_export evidence projection with Logistics/Stock/Docs retained`.** FindTEU events SHALL preserve observed-at, effective event time, provider, raw payload reference, carrier, location, actual-vs-estimated designation, and normalized milestone; source timestamps and provider certainty shall remain visible. ETA, ETD, gate-in, vessel-loaded, discharge and provider completed flags SHALL NOT by themselves close a sale, prove title change, post invoices, verify documents or bypass guarded Logistics/Stock transitions.

- **Positive:** Estimated port arrival changes and the UI updates the ETA with a source and timestamp but the Odoo sale and physical delivery states remain unchanged.
- **Negative:** Provider "completed" automatically closes the customer invoice, asserts buyer delivery or documents Customs release.
- **Related existing BRS:** BRS-EXP-05-R003,R006; BRS-EXP-09-R007; BRS-EXP-11.
- **Acceptance:** `AC-EXP-12-003` / NOT_RUN.

### BRS-EXP-12-R004: Rolls, replay, reversals and provider discrepancies

**DESIGN · P2 · owner: `plasticos_export booking reconciliation; Logistics authorizes affected actions`.** FindTEU ingestion SHALL be replay-safe and idempotent, preserve previous observations, distinguish later ETA estimates from actual voyage or terminal changes, and flag contradictions with the current verified booking/terminal documentary source. A roll or cancellation SHALL require attributable authoritative booking evidence and affected-container review. Provider errors, stale updates and absent coverage SHALL appear as unknown/exception, not silently overwrite current booking terms.

- **Positive:** A carrier roll causes a reviewable mismatch between the current booking PDF and tracking vessel/ETA; prior events remain inspectable, Linda receives a scoped change request only after approved booking revision.
- **Negative:** An out-of-order webhook deletes a previous actual event or reschedules a confirmed drayage truck without approval.
- **Related existing BRS:** BRS-EXP-02-R004; BRS-EXP-09-R005; BRS-EXP-10; BRS-EXP-11.
- **Acceptance:** `AC-EXP-12-004` / NOT_RUN.

### BRS-EXP-12-R005: FindTEU tenancy, credentials, outages and coverage gate

**DESIGN · P2 · owner: `platform integration/security owner; Export is a consumer`.** FindTEU integration SHALL use tenant-isolated authorization and protected API keys, authenticated webhook ingress using a validated provider-supported verification design, quotas, bounded retries and error classification; protect commercial identity in outbound requests. It SHALL be feature-gated until provider contractual access, supported-carrier coverage, webhook security and a real-booking read-only proof pass. It SHALL not fabricate tracking status when provider data is missing.

- **Positive:** A tenant-scoped API credential successfully tracks a supported container and isolates its webhook events from other companies; provider outage yields a visible no-fresh-data exception.
- **Negative:** An untrusted webhook changes another tenant shipment, or a missing token yields a fabricated on-time event or prevents native order handling.
- **Related existing BRS:** BRS-EXP-01-R005; BRS-EXP-06; BRS-EXP-05-R003.
- **Acceptance:** `AC-EXP-12-005` / NOT_RUN.

### BRS-EXP-12-R006: AESDirect Phase 2 EEI filing support, not autonomous filing

**LOCKED · P2 · owner: `authorized USPPI/agent/filer and applicable regulator; Export filing context only`.** Phase 2 SHALL support ACE AESDirect EEI preparation, an applicability/exemption decision, the legally responsible USPPI or authorized agent, and status/evidence visibility. It SHALL NOT infer a mandatory EEI from an Incoterm or international booking alone, claim a regulatory determination absent the required facts, file EEI without an authorized filer, or require an AES account for Phase 1 or shipments outside applicable requirements.

- **Positive:** The authorized exporter identifies a reportable shipment, selects the responsible filer and prepares an evidence-backed filing case; another exempt case documents its actual exemption basis.
- **Negative:** Every FAS shipment is automatically marked as requiring AES or as filed merely because the shipment has an ocean booking.
- **Related existing BRS:** BRS-EXP-05-R005,R006; BRS-EXP-01-R002; Native-First document-compliance owner.
- **Acceptance:** `AC-EXP-12-006` / NOT_RUN.

### BRS-EXP-12-R007: Validate and assemble filing data from existing business sources

**DESIGN · P2 · owner: `native Odoo Sale/Purchase/Stock and authorized compliance reviewer; Export orchestration`.** The AESDirect filing preparation view SHALL source reportable commodity classification, destination, value, quantities, UOM, dates, parties, port, transport and shipment identifiers from their correct native owner and explicit reviewed inputs. Missing or uncertain EEI elements SHALL remain incomplete and be surfaced before handoff; AI extraction may propose facts but must not silently supply legal classification, reporting party, value, license or exemption determinations.

- **Positive:** A four-container shipment prepares the filing data with traceable stock, commercial and booking references and flags an unverified Schedule B/HS mapping for review.
- **Negative:** A shipping booking PDF alone causes AI to fill an unverified Schedule B and value and claim EEI ready.
- **Related existing BRS:** BRS-EXP-05-R005; BRS-EXP-09; BRS-EXP-08; BRS-EXP-03.
- **Acceptance:** `AC-EXP-12-007` / NOT_RUN.

### BRS-EXP-12-R008: Official AESDirect portal, WebLink or supported bulk handoff

**DESIGN · P2 · owner: `authorized filer; connector only prepares supported handoff`.** Initial Phase 2 integration SHALL provide an authorized-user filing handoff to ACE AESDirect with a reviewable data packet and, where tested and approved, its documented WebLink Submission API for prepopulating the portal or a validated AESTIR/X12 bulk-upload file. AES WebLink still requires the filer to sign in, complete missing elements and submit in the official system. This requirement does NOT authorize an uncertified direct AES transmission service or unattended government filing.

- **Positive:** The responsible filer reviews the proposed EEI data, follows a working validated WebLink/portal handoff, manually submits, and returns with an official response.
- **Negative:** An API implementation posts an uncertified EEI directly to AES or labels a prepared WebLink payload "filed".
- **Related existing BRS:** BRS-EXP-05-R005; BRS-EXP-03; BRS-POS-03-R007.
- **Acceptance:** `AC-EXP-12-008` / NOT_RUN.

### BRS-EXP-12-R009: Official response, ITN or exemption evidence and errors

**DESIGN · P2 · owner: `authorized filing authority + native Documents/PlasticOS verification`.** Only the official AES acceptance response and Internal Transaction Number (ITN), or applicable legally supported exemption evidence, SHALL support the corresponding filing outcome. Record filer, authoritative source, acceptance/rejection status, timestamp, exact shipment/export record and document original; reject ambiguous source matches and preserve rejected messages. Export SHALL display the verified projection and Logistics/other owners may consume it only according to their own lawful guarded workflow.

- **Positive:** A supported AES acknowledgment returns ITN for the intended company and shipment; the original is attached once and the status indicates accepted with traceable source.
- **Negative:** The presence of a draft filing CSV, emailed arbitrary number or filename containing "AES" marks the export officially accepted.
- **Related existing BRS:** BRS-EXP-05-R005; BRS-EXP-09-R007; BRS-EXP-03-R004.
- **Acceptance:** `AC-EXP-12-009` / NOT_RUN.

### BRS-EXP-12-R010: Amendments, cancellations, access control and certification boundary

**DESIGN · P2 · owner: `authorized filer and platform security; Export only coordinates evidence`.** Phase 2 filing corrections, voids, late amendments, role authorization and disclosures SHALL follow applicable official filing rules through the authorized filer. Keep the original filing decision, revised data, ITN/rejection evidence and source-linked audit trail. Optional certified direct transmission is DEFERRED as a separate future authorization/certification decision, not included in this Phase 2 scope. Failure or missing permissions SHALL fail closed without changing native order/invoice or stock state.

- **Positive:** A corrected value prompts the responsible filer to amend via the authorized filing route; old ITN and amendment evidence remain linked and an exception is visible until reconciled.
- **Negative:** AI silently edits an already accepted EEI or a non-filer account transmits a correction, and original evidence is erased.
- **Related existing BRS:** BRS-EXP-05-R005; BRS-EXP-09-R004,R007; BRS-EXP-01-R002.
- **Acceptance:** `AC-EXP-12-010` / NOT_RUN.

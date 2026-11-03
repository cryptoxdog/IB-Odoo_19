# Design frontier and proof obligations

These are **not** unlocked product decisions or reasons to create extra systems. Validate at the actual source owner immediately before any future code contract.

1. **Document verification duplicate authority (existing risk):** at pinned source `plasticos_documents/models/document.py` and `plasticos_documents_native/models/document_native.py` both expose `verified`, with the native bridge exposing `action_verify()`. The accepted working Native-First intent requires one business verification writer (`BRS-POS-03-R004`). Correct/confirm there, **never in Export**.
2. **Documents requirement scope:** `plasticos.document.rule`/`plasticos.document.validation.matrix` currently expose general model/client and supplier/carrier/buyer categories, but may not express exact booking+stage+operation applicability. First check actual installed current behavior. If insufficient, a **generalized Document-owner extension** may be needed, with Export passing its context. Do not invent an Export verifier.
3. **Booking identity:** assess whether Sales/Logistics already hold a fit booking identity. Introduce at most the narrowest missing export context/links if required. Multiple containers per booking, native stock packages distinct from ocean equipment containers.
4. **Terminology:** operator's `FOB pickup` and `FAS inland-to-port/rail` are industry quote terms, not assertions of formal ICC Incoterm meaning. Each actual contract determines responsibilities, delivery location and compliance roles.
5. **Proof of terminal handoff:** actual terminal/rail acceptance must be independently evidenced; a QR scan or dock loading cannot prove terminal acceptance, vessel loading or legal risk transfer. Whether a terminal receipt is a contractual completion condition depends on specific agreement.
6. **Source/time verification:** carrier/terminal/local timezone, source revision, date-only vs timestamp must be retained. Data sources and follow-up owner need selection before automatic alerts.
7. **Enterprise deployment:** Documents bridge requires Enterprise `documents` and `documents_account`; full Inventory Barcode `stock_barcode` may also be Enterprise. Real licensed installation, correct interfaces and chosen CE fallback are NOT_RUN.
8. **Physical shipping vs regulatory clearance:** destination/jurisdiction-specific legal filings, VGM and carrier-issued ocean B/L may be required for Phase 2. No single fixed checklist universally applies. Legal filing approvals and external submissions stay with authorized parties/providers.
9. **Operational sending:** confirm which Linda workflow actually owns ocean booking/forwarder messages; if not existing, explicitly decide a single owner within Logistics before activation. Export only assembles context, never silently assumes control.
10. **Competing requirements:** commercial pickup, export document eligibility, stock delivery and finance readiness are independent. One condition cannot become a global close blocker by convenience.

## Smallest planned acceptance walkthrough (all NOT_RUN)

An approved, real-shape FAS shipment is linked to its order and existing Linda load. The operator records Booking No., Steamship Line, POL, POD, ERD and cargo cutoff from an original carrier notice, including source and timezone. A report prints through native QWeb, current gate receipt is missing, and Documents reports that specific obligation pending. A corrected notice changes cutoff but preserves the first notice. An authorized actor verifies a real gate receipt through the existing Documents owner. One existing Linda send action sends a party-safe report. Stock and accounting remain unchanged except where their separate real authorized operations occur. Phase 2 adds an issued ocean B/L and only applicable international evidence without remapping the original booking.

**Negative discriminator:** a late unauthenticated email, duplicate native verify control or QR scan cannot make export ready, post an invoice or send a second external message.

## v1.2 remaining decisions for correct owner, NOT product permission to invent

11. **Cardinality:** Choose exact one-to-many child association for one transaction / one SO / many loads, one supplier PO/many receipts, and several bookings. Existing singular `transaction.load_id` cannot be the only source. Preserve historical ID compatibility.
12. **Buyerless movement:** Define authorized company/custody/supplier-PO and physical movement path that does not require `sale_order_id`, while preserving genuine sales guards and company isolation.
13. **Quantity source:** Resolve actual unit-of-measure and line-level allocation for a 30-load SO and 4-load PO, including split/partial receipts and each per-week independent booking.
14. **Document AI scope:** Prove installed Odoo 19 AI Documents extraction and server-tool hooks; exact company/booking/physical load match must abstain on ambiguity and never use newest partner.
15. **State actions:** Select allowed evidence-backed owner transitions explicitly. Never auto-promote booking received to delivered/invoiced/closed; require operator-approved state and per-load guards.
16. **Supplier PO copy policy:** Approved PO is a single purchase obligation; per-week booking notifications must not implicitly reissue it, though a controlled reference-copy attachment may be allowed.
17. **In-transit resale:** Stock custody/title, insurance, relevant exporter of record, customs and B/L instructions may change contractually only after authorized process; display historic source truth rather than rewrite prior events.

**Next discriminating proof (NOT_RUN):** Create one 30-load SO and four-load PO in a disposable Odoo Enterprise fixture, ship week 1 against booking A, then ingest booking B by Odoo Documents AI for week 2; ensure exact link and unchanged remaining quantities; also create a buyer-unassigned owned cargo load, record terminal gate-in, sell it while on water, and validate sale allocation without a new stock ledger.

## v1.4 Phase 2 external integration proofs pending

- FindTEU: validate authorized account, pricing/quotas, carrier coverage for real containers, tracking update latency, cross-tenant webhook authenticity and replay/roll handling. No mandatory core dependency.
- AESDirect: decide which party files for each transaction, exact reviewed EEI inputs, official WebLink/bulk workflow validation, response and ITN matching, security and amendment governance. Direct AES software certification and unattended filing are separate future choices, explicitly excluded.
- Neither provider has been connected, queried with a live shipment or independently tested in this planning pass.

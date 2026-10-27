# Documents BRS | exact effective rules

**Origin:** frozen native-first BRS-POS v1.0.0, based on Rev008. **Status:** proposed repository installation; admission on authorized merge, not before. All runtime outcomes NOT_RUN.

This file renders exact `normative_text` statements from `EFFECTIVE_RULES.json`. For full context and original acceptance see the verbatim BRS chapter files and `ACCEPTANCE.json`. No semantic text is rewritten here.

## BRS-POS-02

### BRS-POS-02-R001 — Native original custody
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

The original business file SHALL reside once as an Odoo native Documents file linked to ir.attachment; business evidence links SHALL reuse that original.

Acceptance: AC-POS-02-001 · Runtime: **NOT_RUN**

### BRS-POS-02-R002 — Native internal folder structure
**DESIGN** · **Owner:** Odoo Documents / plasticos_documents_native

Documents Inbox, BOL, scale, receiving, supplier bills and compliance folders/tags SHALL use native Documents organization where suitable.

Acceptance: AC-POS-02-002 · Runtime: **NOT_RUN**

### BRS-POS-02-R003 — External inbound by alias
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

An authenticated inbound email with attachments MAY enter via an Odoo folder email alias and native Mail; this SHALL NOT grant sender access to Documents.

Acceptance: AC-POS-02-003 · Runtime: **NOT_RUN**

### BRS-POS-02-R004 — Internal request placeholders
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

An outstanding file obligation SHALL use an Odoo native Documents Request placeholder with an internal assignee, type/tag and due date where supported.

Acceptance: AC-POS-02-004 · Runtime: **NOT_RUN**

### BRS-POS-02-R005 — Native request fulfillment requires verification
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

Receiving a file or filling a native request placeholder SHALL NOT alone satisfy business compliance before correct matching and authorized verification.

Acceptance: AC-POS-02-005 · Runtime: **NOT_RUN**

### BRS-POS-02-R006 — Native email alias triage
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

Unknown or ambiguously matched files SHALL remain in a native Inbox and create or update one internal review activity rather than auto-assigning to the newest deal.

Acceptance: AC-POS-02-006 · Runtime: **NOT_RUN**

### BRS-POS-02-R007 — Versions and supersession
**DESIGN** · **Owner:** Odoo Documents / plasticos_documents_native

New document versions SHALL use native Documents versions and corresponding PlasticOS evidence supersession links without deleting historical authoritative originals.

Acceptance: AC-POS-02-007 · Runtime: **NOT_RUN**

### BRS-POS-02-R008 — Native shortcuts before duplicating
**DESIGN** · **Owner:** Odoo Documents / plasticos_documents_native

Where a single file belongs in more than one native folder, native Documents shortcuts or links SHALL be considered before copying the file.

Acceptance: AC-POS-02-008 · Runtime: **NOT_RUN**

### BRS-POS-02-R009 — Native file actions only when fit
**CONDITIONAL** · **Owner:** Odoo Documents / plasticos_documents_native

Native PDF split, merge, lock and file centralization MAY be used when they preserve the original source and its provenance.

Acceptance: AC-POS-02-009 · Runtime: **NOT_RUN**

### BRS-POS-02-R010 — AI classification without authority
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

Optional installed Documents AI/OCR MAY propose tags or folder routing for internal review; it SHALL NOT verify evidence, set weights, decide liability or post journals.

Acceptance: AC-POS-02-010 · Runtime: **NOT_RUN**

### BRS-POS-02-R011 — No external Documents sharing
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

The workflow SHALL NOT grant external Documents folder/file access, request links, portal invitations, external Sign requests or share URLs.

Acceptance: AC-POS-02-011 · Runtime: **NOT_RUN**

### BRS-POS-02-R012 — Document journal intake
**DESIGN** · **Owner:** Odoo Documents / plasticos_documents_native

Native Accounting purchase-journal email aliases and bill-upload actions SHALL be preferred for real supplier invoices, preserving the submitted PDF.

Acceptance: AC-POS-02-012 · Runtime: **NOT_RUN**

### BRS-POS-02-R013 — No mandatory digitization charges
**LOCKED** · **Owner:** Odoo Documents / plasticos_documents_native

Paid Odoo document digitization/IAP SHALL NOT be required for the initial workflow unless separately selected and cost-authorized.

Acceptance: AC-POS-02-013 · Runtime: **NOT_RUN**

## BRS-POS-03

### BRS-POS-03-R001 — One canonical business classification
**DESIGN** · **Owner:** plasticos_documents compliance owner

PlasticOS document tag plus party category SHALL be the compliance vocabulary; native classification fields shall project it without becoming a second verifier.

Acceptance: AC-POS-03-001 · Runtime: **NOT_RUN**

### BRS-POS-03-R002 — Typed exact association
**LOCKED** · **Owner:** plasticos_documents compliance owner

Each validated evidence link SHALL identify the exact company, transaction/load or PO/picking when appropriate, and applicable source request/version.

Acceptance: AC-POS-03-002 · Runtime: **NOT_RUN**

### BRS-POS-03-R003 — Multi-record original reuse
**DESIGN** · **Owner:** plasticos_documents compliance owner

One original attachment MAY create multiple typed evidence associations when each reference is independently established; this SHALL NOT duplicate its bytes.

Acceptance: AC-POS-03-003 · Runtime: **NOT_RUN**

### BRS-POS-03-R004 — Authoritative verification writer
**DESIGN** · **Owner:** plasticos_documents compliance owner

Only the approved PlasticOS document verification/override operation SHALL authoritatively set verified, verified_by, verified_at and override evidence, with native views delegating to that owner.

Acceptance: AC-POS-03-004 · Runtime: **NOT_RUN**

### BRS-POS-03-R005 — Verification is attributable
**LOCKED** · **Owner:** plasticos_documents compliance owner

Verification SHALL retain signer/actor, instant, file version, exact party and object, decision and override reason where applicable.

Acceptance: AC-POS-03-005 · Runtime: **NOT_RUN**

### BRS-POS-03-R006 — Expired, inactive or superseded evidence
**DESIGN** · **Owner:** plasticos_documents compliance owner

Expired, inactive, superseded, unverified or irrelevant-party evidence SHALL NOT satisfy a required document rule.

Acceptance: AC-POS-03-006 · Runtime: **NOT_RUN**

### BRS-POS-03-R007 — Operation-scoped compliance
**LOCKED** · **Owner:** plasticos_documents compliance owner

Compliance queries SHALL be read-only and honor operation-specific requirements for invoice, logistics close and dispatch rather than a universal complete flag.

Acceptance: AC-POS-03-007 · Runtime: **NOT_RUN**

### BRS-POS-03-R008 — No financial side effect from recompute
**LOCKED** · **Owner:** plasticos_documents compliance owner

Creating, editing, classifying, verifying or recomputing a document SHALL NOT call account.move.action_post, issue a note, make a payment or create an accounting recovery.

Acceptance: AC-POS-03-008 · Runtime: **NOT_RUN**

### BRS-POS-03-R009 — Buyer receiving authority
**LOCKED** · **Owner:** plasticos_documents compliance owner

A buyer Receiving Report matched and verified for the correct delivery SHALL be authoritative documentary evidence for buyer invoice eligibility and operational delivery proof.

Acceptance: AC-POS-03-009 · Runtime: **NOT_RUN**

### BRS-POS-03-R010 — Partial receiving attribution
**DESIGN** · **Owner:** plasticos_documents compliance owner

A buyer Receiving Report covering only part of an order SHALL not silently authorize an invoice or final close for additional unproven delivered quantities.

Acceptance: AC-POS-03-010 · Runtime: **NOT_RUN**

### BRS-POS-03-R011 — CST is a distinct carrier obligation
**LOCKED** · **Owner:** plasticos_documents compliance owner

Missing carrier certified scale/CST evidence SHALL remain a collection/claim issue; it SHALL NOT block ordinary buyer invoicing or documented commercial close.

Acceptance: AC-POS-03-011 · Runtime: **NOT_RUN**

### BRS-POS-03-R012 — Receipt versus certified proof
**DESIGN** · **Owner:** plasticos_documents compliance owner

An uploaded scale image SHALL NOT be treated as certified CST without the agreed document form and required fields.

Acceptance: AC-POS-03-012 · Runtime: **NOT_RUN**

### BRS-POS-03-R013 — Human weight capture until extraction admission
**LOCKED** · **Owner:** plasticos_documents compliance owner

Authoritative supplier/buyer/scale weights SHALL be entered from verified filed source evidence by an authorized human until a separately admitted extraction capability is proven.

Acceptance: AC-POS-03-013 · Runtime: **NOT_RUN**

### BRS-POS-03-R014 — Company-aware evidence controls
**LOCKED** · **Owner:** plasticos_documents compliance owner

Every evidence relation SHALL preserve the legal company and enforce company-consistent source links and view rights.

Acceptance: AC-POS-03-014 · Runtime: **NOT_RUN**

## BRS-POS-09

### BRS-POS-09-R001 — Use all applicable native primitives
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Missing files, internal exceptions, field-change triggers, time evaluation, template mail and accounting dunning SHALL reuse native Odoo mechanisms where fit is verified.

Acceptance: AC-POS-09-001 · Runtime: **NOT_RUN**

### BRS-POS-09-R002 — Internal Documents Request purpose
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Native Documents Request SHALL present missing-file assignments and due dates to internal staff only; external parties shall get ordinary authorized email via Linda.

Acceptance: AC-POS-09-002 · Runtime: **NOT_RUN**

### BRS-POS-09-R003 — One internal Activity per unresolved obligation
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

An exception SHALL have at most one active native mail.activity for exact company, business record, document/obligation, reason and revision; reevaluations update or resolve it.

Acceptance: AC-POS-09-003 · Runtime: **NOT_RUN**

### BRS-POS-09-R004 — Simple event trigger on native automation
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Odoo base.automation/ir.actions.server SHALL handle safe deterministic on-create/on-write effects and exact mail.message intake; domain approvals remain in their business owners.

Acceptance: AC-POS-09-004 · Runtime: **NOT_RUN**

### BRS-POS-09-R005 — Native scheduler is the only job platform
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Due evaluations SHALL use Odoo ir.cron or supported native timed actions, not an independent scheduler; legitimate separate jobs may coexist for distinct owners.

Acceptance: AC-POS-09-005 · Runtime: **NOT_RUN**

### BRS-POS-09-R006 — Only one external reminder writer
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

For the same file, recipient, fulfillment episode and due date, Linda SHALL own at most one approved external reminder; PlasticOS Documents and Activities shall supply status, not duplicate mail.

Acceptance: AC-POS-09-006 · Runtime: **NOT_RUN**

### BRS-POS-09-R007 — Supplier document business clock
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Supplier missing-document chase SHALL start on the actual pickup event with business-day +1 reminder and +5 escalation for the applicable supplier obligation.

Acceptance: AC-POS-09-007 · Runtime: **NOT_RUN**

### BRS-POS-09-R008 — Carrier document business clock
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Carrier missing-document chase SHALL start on actual pickup with +2 business-day reminder and +6 escalation, independent of buyer invoice eligibility.

Acceptance: AC-POS-09-008 · Runtime: **NOT_RUN**

### BRS-POS-09-R009 — Buyer document business clock
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Buyer missing Receiving chase SHALL start on actual delivery with +1 business-day reminder and +5 escalation for that buyer obligation.

Acceptance: AC-POS-09-009 · Runtime: **NOT_RUN**

### BRS-POS-09-R010 — No duplicate daily touch
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Routine reminders SHALL not repeat more than once per exact party, obligation and local business day; retries shall preserve delivery uncertainty and revision identity.

Acceptance: AC-POS-09-010 · Runtime: **NOT_RUN**

### BRS-POS-09-R011 — Quiet hours and locale aware deadlines
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Linda-origin routine supplier/carrier appointment or document notices SHALL honor approved recipient/source local clocks and quiet hours; urgent internal exceptions remain visible.

Acceptance: AC-POS-09-011 · Runtime: **NOT_RUN**

### BRS-POS-09-R012 — Stop on verified or inapplicable
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Document verification, cancellation, source supersession or irrelevant fulfillment episode SHALL cancel/close pending reminder intents, requests and Activities while preserving the audit trail.

Acceptance: AC-POS-09-012 · Runtime: **NOT_RUN**

### BRS-POS-09-R013 — No hidden financial triggers
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Native automation on Documents or claim state SHALL NOT post customer/vendor invoices, credits, penalties or payments.

Acceptance: AC-POS-09-013 · Runtime: **NOT_RUN**

### BRS-POS-09-R014 — Automation last live stage
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

External recurring reminders, automated dispatch and dunning SHALL remain off or shadow until manual finance/Documents/stock proof, exact ownership handoff and separate activation approval.

Acceptance: AC-POS-09-014 · Runtime: **NOT_RUN**

### BRS-POS-09-R015 — Accounting follow-ups later than operational automation
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Native Accounting follow-ups SHALL only be activated after a separately authorized QB exit, even if other Linda logistics messages have been activated.

Acceptance: AC-POS-09-015 · Runtime: **NOT_RUN**

### BRS-POS-09-R016 — Optional Studio or AI costs
**LOCKED** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

Studio UI automation and AI extraction SHALL not be mandatory or purchased without evidence of necessity and separate cost authorization; version-controlled Odoo-native rules may suffice.

Acceptance: AC-POS-09-016 · Runtime: **NOT_RUN**

### BRS-POS-09-R017 — Time-based native engine limitations
**CONDITIONAL** · **Owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail

The exact installed time-trigger cron frequency, last-run window semantics and historical-run behavior SHALL be inspected before relying on native timed automation for 2-hour/4-hour Linda obligations.

Acceptance: AC-POS-09-017 · Runtime: **NOT_RUN**


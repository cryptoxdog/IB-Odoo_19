# BRS-POS-02: Native Documents originals and intake

**Status:** FROZEN WORKING BRS, pending independent repository adoption. No test/code/live authorization.
**Business / semantic owner:** Odoo Documents / plasticos_documents_native
**Native capabilities and objects:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
**Planned implementation lane:** NAT-02
**Governing baseline:** PlasticOS Primary Campaign Rev008 exact archive digest in `SOURCE_PROVENANCE.json`.
**Status labels:** LOCKED = accepted operator intent or previously accepted business rule; DESIGN = converged working architecture but repository admission pending; CONDITIONAL = require named proof/approval.

## Rules

### BRS-POS-02-R001: Native original custody

**LOCKED.** The original business file SHALL reside once as an Odoo native Documents file linked to ir.attachment; business evidence links SHALL reuse that original.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-001`. Two linked loads refer to one attachment and maintain independent evidence meaning.
- **Required negative control:** Two cloned BOL PDFs are stored to satisfy one original.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R002: Native internal folder structure

**DESIGN.** Documents Inbox, BOL, scale, receiving, supplier bills and compliance folders/tags SHALL use native Documents organization where suitable.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-002`. A received BOL is browsable in its intended native folder without a second file system.
- **Required negative control:** PlasticOS creates a parallel custom directory or binary table.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R003: External inbound by alias

**LOCKED.** An authenticated inbound email with attachments MAY enter via an Odoo folder email alias and native Mail; this SHALL NOT grant sender access to Documents.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-003`. Carrier email produces internal Inbox file(s) without portal permission.
- **Required negative control:** Supplier receives an editor or viewer invitation as a side effect.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R004: Internal request placeholders

**LOCKED.** An outstanding file obligation SHALL use an Odoo native Documents Request placeholder with an internal assignee, type/tag and due date where supported.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-004`. The missing buyer report is visible as a single internal Requested Document activity.
- **Required negative control:** An external customer is sent a native Documents upload link.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R005: Native request fulfillment requires verification

**LOCKED.** Receiving a file or filling a native request placeholder SHALL NOT alone satisfy business compliance before correct matching and authorized verification.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-005`. An unverified attachment remains pending.
- **Required negative control:** Merely attaching a PDF clears invoice compliance.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R006: Native email alias triage

**LOCKED.** Unknown or ambiguously matched files SHALL remain in a native Inbox and create or update one internal review activity rather than auto-assigning to the newest deal.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-006`. Same supplier with two open POs produces an ambiguous Inbox task.
- **Required negative control:** A latest-created transaction is selected without proof.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R007: Versions and supersession

**DESIGN.** New document versions SHALL use native Documents versions and corresponding PlasticOS evidence supersession links without deleting historical authoritative originals.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-007`. An old scale certificate remains inspectable after a corrected one replaces it.
- **Required negative control:** Uploading a replacement erases the previous original and verification trail.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R008: Native shortcuts before duplicating

**DESIGN.** Where a single file belongs in more than one native folder, native Documents shortcuts or links SHALL be considered before copying the file.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-008`. The same BOL can be reached from a second folder without duplicate attachment bytes.
- **Required negative control:** Folder convenience creates another authoritative document file.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R009: Native file actions only when fit

**CONDITIONAL.** Native PDF split, merge, lock and file centralization MAY be used when they preserve the original source and its provenance.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-009`. A split PDF retains the immutable original as evidence.
- **Required negative control:** A split page silently replaces a signed full BOL without reference.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R010: AI classification without authority

**LOCKED.** Optional installed Documents AI/OCR MAY propose tags or folder routing for internal review; it SHALL NOT verify evidence, set weights, decide liability or post journals.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-010`. Auto-tagged file waits for authorized verification.
- **Required negative control:** OCR-generated weight is posted as buyer settlement truth.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R011: No external Documents sharing

**LOCKED.** The workflow SHALL NOT grant external Documents folder/file access, request links, portal invitations, external Sign requests or share URLs.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-011`. An ordinary email reply succeeds with no external Documents ACL grant.
- **Required negative control:** An external portal user opens the internal load folder.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R012: Document journal intake

**DESIGN.** Native Accounting purchase-journal email aliases and bill-upload actions SHALL be preferred for real supplier invoices, preserving the submitted PDF.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-012`. A vendor invoice creates a draft vendor bill through the native intake path.
- **Required negative control:** The uploaded supplier PDF becomes an auto-posted bill merely because it arrived.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-02-R013: No mandatory digitization charges

**LOCKED.** Paid Odoo document digitization/IAP SHALL NOT be required for the initial workflow unless separately selected and cost-authorized.

- **Native owner:** documents.document, ir.attachment, folder alias, versions, locks, shortcuts, Requests
- **Acceptance:** `AC-POS-02-013`. A manual draft bill path operates with OCR unavailable.
- **Required negative control:** Vendor bill processing blocks because a digitization token subscription was not purchased.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

## Design frontier and sources

This chapter uses primary Rev008: NATIVE_AUTOMATION_ODOO19_ALIGNMENT.md, NATIVE_CAPABILITY_REGISTER.md, CONSOLIDATED_DECISIONS.md.
No operator-open gate is implicitly closed by a conditional rule. See `GOVERNANCE/OPEN_DECISIONS.md`.
A source/model name is a design candidate until installed Odoo Enterprise evidence validates its exact shape.

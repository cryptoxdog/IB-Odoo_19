# BRS-POS-10: Linda logistics commercial and physical communication

**Status:** FROZEN WORKING BRS, pending independent repository adoption. No test/code/live authorization.
**Business / semantic owner:** plasticos_logistics (Linda) + Odoo Mail
**Native capabilities and objects:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
**Planned implementation lane:** NAT-01 / NAT-03
**Governing baseline:** PlasticOS Primary Campaign Rev008 exact archive digest in `SOURCE_PROVENANCE.json`.
**Status labels:** LOCKED = accepted operator intent or previously accepted business rule; DESIGN = converged working architecture but repository admission pending; CONDITIONAL = require named proof/approval.

## Rules

### BRS-POS-10-R001: Independent PO and SO issue

**LOCKED.** Linda SHALL issue a genuinely released native PO or SO independently and exactly once per authorized business cycle/revision, even if the counterpart order does not exist.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-001`. PO-only and SO-only authorized releases each have one matching outgoing message.
- **Required negative control:** An unreleased draft triggers an order-issue email.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R002: Native commercial approvals remain intact

**LOCKED.** Linda SHALL observe actual Odoo native confirm/approve operations and SHALL NOT invent an extra Linda approval step or bypass native manager gates.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-002`. Two-step approval waits for purchase state purchase.
- **Required negative control:** An agent flips native order state without the standard approval.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R003: Native reports with party-safe redaction

**LOCKED.** Linda SHALL attach native Odoo PO/SO reports or verified audience-safe QWeb variants, with no buyer details on supplier PO or supplier economics on buyer SO.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-003`. Dropship supplier PDF has no buyer destination or buyer email.
- **Required negative control:** Native dropship PO leaks the customer shipping address.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R004: Native queue and exact delivery-state semantics

**LOCKED.** External mail SHALL be queued/tracked through Odoo Mail; queued is not sent; a timeout of unknown remote effect SHALL not be blindly retried.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-004`. Interrupted send retains unknown outcome and avoids another automatic send.
- **Required negative control:** mail.mail queue creation is treated as proof the supplier received it.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R005: Reply evidence by original headers

**LOCKED.** Linda inbound response identity SHALL use original MIME and exact In-Reply-To/References ancestry and appropriate sender attribution, not order chatter last-message matching.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-005`. Two parallel supplier requests result in correctly bound reply only if headers disambiguate.
- **Required negative control:** Last chatter message is guessed to be the reply parent.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R006: Free-form response authority

**CONDITIONAL.** Unstructured supplier/buyer replies MAY be proposed for extraction only when a verified installed authorized native AI tool exists; missing AI SHALL leave them unresolved, not become accepted readiness.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-006`. Native reply intake retains ambiguous natural language with review status.
- **Required negative control:** Free-form LLM guessed date directly changes dispatch.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R007: Real physical READY

**LOCKED.** Real supplier or actual warehouse pickup-site custodian SHALL confirm exact material/quantity and readiness before physical dispatch; stock reservation alone is not that confirmation.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-007`. Reserved warehouse goods without site-ready confirmation remain nondispatched.
- **Required negative control:** stock.picking assigned sends carrier packet immediately.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R008: Existing carrier rate authority

**LOCKED.** Linda SHALL NOT choose, invent or override carrier quotes/rates/awards outside the existing guarded freight approval path.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-008`. Dispatch follows confirmed authorized carrier award.
- **Required negative control:** A reminder timer invents a freight rate and dispatches.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R009: Dispatch packet and source guard

**LOCKED.** The carrier dispatch packet SHALL use existing guarded logistics report/three-PDF evidence after source, approved award, appointments, READY and correct company are established.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-009`. A real ready load receives one carrier-only complete dispatch packet.
- **Required negative control:** A PO-only warehouse receipt gets a fabricated outbound dispatch packet.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R010: Carrier acknowledgment milestones

**LOCKED.** After a true carrier dispatch, the approved +2-hour acknowledgment reminder and +4-hour carrier/ops escalation SHALL be evaluated against the real send event.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-010`. T+2 reminder is single; T+4 escalates correctly if unacknowledged.
- **Required negative control:** Every 4-hour cron run resends an identical packet forever.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R011: Native order cancellation lifecycle

**LOCKED.** A real canceled order with already sent or potentially delivered issue SHALL produce one eligible cancellation notice; unsent queued issues are withdrawn rather than announced as canceled.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-011`. Cancel/reconfirm retains historic notice and issues a new cycle once.
- **Required negative control:** A withdrawn unsent PO sends a cancellation email to a party never contacted.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R012: Native reopening is new release cycle

**LOCKED.** After native order cancellation, re-confirmation MAY legitimately restart the same authorized issuance sequence; same-cycle replay shall remain deduplicated.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-012`. Reconfirmed unchanged PO issues one new cycle after valid cancellation.
- **Required negative control:** Reopen causes multiple copies on the same active cycle.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R013: Transport revision and sequencing

**LOCKED.** A materially changed order SHALL invalidate unsent stale PDFs; a reissue SHALL NOT outrun a still-pending cancellation notice to the same party.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-013`. A changed buyer address withdraws stale queue before sending.
- **Required negative control:** Two contradictory orders are delivered in reverse business sequence.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R014: No fake load for warehouse inbound

**LOCKED.** PO-only 3PL receipt and paperwork SHALL be attached to the native PO/picking and company, not to an invented SO-backed plasticos.load.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-014`. Inbound picking documents associate to actual warehouse receipt.
- **Required negative control:** Company-less load bypasses company security for PO-only case.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R015: External channel owner handoff

**LOCKED.** At live Linda ownership of a specific operation, legacy generic PO/SO/carrier automations SHALL stand down for that operation; off/shadow fallback remains explicitly reconciled.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-015`. One source sends each authorized order issue in all three modes.
- **Required negative control:** Odoo native send_email and Linda send duplicate SO confirmations.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-10-R016: Deterministic exception inbox

**DESIGN.** Linda shall create native Activities for genuinely unresolved human decisions only, preserving the business record, company, due time and safe choices; routine eligible orders need no extra approval.

- **Native owner:** native PO/SO reports, mail.template/mail.mail/mail.message, stock.picking, mail.activity
- **Acceptance:** `AC-POS-10-016`. An ambiguous carrier reply creates one action for correct internal owner.
- **Required negative control:** Every ordinary released PO requires a human Linda approval click.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

## Design frontier and sources

This chapter uses primary Rev008: NATIVE_AUTOMATION_ODOO19_ALIGNMENT.md, STACKED_AUTOMATION_CORRECTION_PR_PLAN.md, PR_STACK_SOURCE_CENSUS.json.
No operator-open gate is implicitly closed by a conditional rule. See `GOVERNANCE/OPEN_DECISIONS.md`.
A source/model name is a design candidate until installed Odoo Enterprise evidence validates its exact shape.

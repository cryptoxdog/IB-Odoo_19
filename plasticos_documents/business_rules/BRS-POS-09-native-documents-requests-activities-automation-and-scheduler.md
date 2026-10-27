# BRS-POS-09: Native Documents Requests, Activities, automation and scheduler

**Status:** FROZEN WORKING BRS, pending independent repository adoption. No test/code/live authorization.
**Business / semantic owner:** Odoo Documents/Activity, PlasticOS obligation service, Linda external mail
**Native capabilities and objects:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
**Planned implementation lane:** SAFETY / NAT-02 / NAT-03 / NAT-04
**Governing baseline:** PlasticOS Primary Campaign Rev008 exact archive digest in `SOURCE_PROVENANCE.json`.
**Status labels:** LOCKED = accepted operator intent or previously accepted business rule; DESIGN = converged working architecture but repository admission pending; CONDITIONAL = require named proof/approval.

## Rules

### BRS-POS-09-R001: Use all applicable native primitives

**LOCKED.** Missing files, internal exceptions, field-change triggers, time evaluation, template mail and accounting dunning SHALL reuse native Odoo mechanisms where fit is verified.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-001`. Every automation design identifies the native primitive used.
- **Required negative control:** A new Celery/cron service duplicates base.automation and ir.cron.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R002: Internal Documents Request purpose

**LOCKED.** Native Documents Request SHALL present missing-file assignments and due dates to internal staff only; external parties shall get ordinary authorized email via Linda.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-002`. Document obligation visible in native Documents Activity view.
- **Required negative control:** Supplier receives a Documents Request portal/share link.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R003: One internal Activity per unresolved obligation

**LOCKED.** An exception SHALL have at most one active native mail.activity for exact company, business record, document/obligation, reason and revision; reevaluations update or resolve it.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-003`. Six cron runs maintain one current missing-CST escalation Activity.
- **Required negative control:** Each tick creates another unresolved activity.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R004: Simple event trigger on native automation

**LOCKED.** Odoo base.automation/ir.actions.server SHALL handle safe deterministic on-create/on-write effects and exact mail.message intake; domain approvals remain in their business owners.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-004`. A new inbound message is handed to one Linda response handler.
- **Required negative control:** Two automated actions independently dispatch carrier packets.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R005: Native scheduler is the only job platform

**LOCKED.** Due evaluations SHALL use Odoo ir.cron or supported native timed actions, not an independent scheduler; legitimate separate jobs may coexist for distinct owners.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-005`. A Documents due check and Linda transport tick coexist without duplicate sends.
- **Required negative control:** A custom external timer races two Odoo crons.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R006: Only one external reminder writer

**LOCKED.** For the same file, recipient, fulfillment episode and due date, Linda SHALL own at most one approved external reminder; PlasticOS Documents and Activities shall supply status, not duplicate mail.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-006`. Carrier receives at most one scheduled CST reminder in the daily window.
- **Required negative control:** Documents cron plus Linda both email the same attachment request.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R007: Supplier document business clock

**LOCKED.** Supplier missing-document chase SHALL start on the actual pickup event with business-day +1 reminder and +5 escalation for the applicable supplier obligation.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-007`. Friday pickup produces Monday supplier due date under stated work calendar.
- **Required negative control:** An old transaction create_date triggers reminders months early.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R008: Carrier document business clock

**LOCKED.** Carrier missing-document chase SHALL start on actual pickup with +2 business-day reminder and +6 escalation, independent of buyer invoice eligibility.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-008`. Friday pickup yields Tuesday carrier first due date under Mon-Fri.
- **Required negative control:** Scale tag receipt clears a required certified CST without verification.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R009: Buyer document business clock

**LOCKED.** Buyer missing Receiving chase SHALL start on actual delivery with +1 business-day reminder and +5 escalation for that buyer obligation.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-009`. Verified buyer report terminates the outstanding chase.
- **Required negative control:** Supplier pickup timestamp is used to calculate buyer reminder due date.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R010: No duplicate daily touch

**LOCKED.** Routine reminders SHALL not repeat more than once per exact party, obligation and local business day; retries shall preserve delivery uncertainty and revision identity.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-010`. Two overlapping ticks yield one sent/unknown intent.
- **Required negative control:** Two crons each send a separate carrier reminder.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R011: Quiet hours and locale aware deadlines

**LOCKED.** Linda-origin routine supplier/carrier appointment or document notices SHALL honor approved recipient/source local clocks and quiet hours; urgent internal exceptions remain visible.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-011`. A quiet-hours routine notice is delayed without deleting the obligation.
- **Required negative control:** UTC midnight sends a routine local 2AM message contrary to schedule.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R012: Stop on verified or inapplicable

**LOCKED.** Document verification, cancellation, source supersession or irrelevant fulfillment episode SHALL cancel/close pending reminder intents, requests and Activities while preserving the audit trail.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-012`. A fulfilled CST halts subsequent overdue outgoing mail.
- **Required negative control:** A canceled PO continues daily supplier chasers.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R013: No hidden financial triggers

**LOCKED.** Native automation on Documents or claim state SHALL NOT post customer/vendor invoices, credits, penalties or payments.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-013`. A compliance auto action updates readiness status only.
- **Required negative control:** A document received event invokes account.move.action_post.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R014: Automation last live stage

**LOCKED.** External recurring reminders, automated dispatch and dunning SHALL remain off or shadow until manual finance/Documents/stock proof, exact ownership handoff and separate activation approval.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-014`. Planned XML actions exist but produce no external mail before go-live gate.
- **Required negative control:** A newly installed addon enables active carrier emails by default.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R015: Accounting follow-ups later than operational automation

**LOCKED.** Native Accounting follow-ups SHALL only be activated after a separately authorized QB exit, even if other Linda logistics messages have been activated.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-015`. Operational supplier notice can be live while customer dunning remains off pre-cutover.
- **Required negative control:** Odoo collection letters send against unverified historical QB AR.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R016: Optional Studio or AI costs

**LOCKED.** Studio UI automation and AI extraction SHALL not be mandatory or purchased without evidence of necessity and separate cost authorization; version-controlled Odoo-native rules may suffice.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-016`. An existing XML base.automation works without new custom Studio subscription.
- **Required negative control:** A developer assumes all Studio/AI paid services are free and deployed.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-09-R017: Time-based native engine limitations

**CONDITIONAL.** The exact installed time-trigger cron frequency, last-run window semantics and historical-run behavior SHALL be inspected before relying on native timed automation for 2-hour/4-hour Linda obligations.

- **Native owner:** Documents Requests, mail.activity, base.automation, ir.actions.server, ir.cron, Mail
- **Acceptance:** `AC-POS-09-017`. An overdue timer replays safely without retroactively sending historical mail.
- **Required negative control:** A default four-hour periodic check is assumed to meet a strict two-hour SLA.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

## Design frontier and sources

This chapter uses primary Rev008: NATIVE_AUTOMATION_ODOO19_ALIGNMENT.md, NATIVE_AUTOMATION_CAPABILITY_MATRIX.json, AUTOMATION_EXPLORATION_NEXT.md.
No operator-open gate is implicitly closed by a conditional rule. See `GOVERNANCE/OPEN_DECISIONS.md`.
A source/model name is a design candidate until installed Odoo Enterprise evidence validates its exact shape.

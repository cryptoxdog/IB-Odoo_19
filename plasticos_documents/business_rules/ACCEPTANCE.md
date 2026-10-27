# Documents BRS Acceptance

## Original 44 rule-level cases

Original cases are **verbatim records** in `ACCEPTANCE.json`. Every case status is **NOT_RUN**; no Enterprise runtime behavior was exercised during documentation installation.

## Cross-domain negative vectors

### AC-DOC-X01: Native original across several typed links
- **Positive:** One Documents original, several exact company-scoped evidence references
- **Negative that MUST fail:** Copy BOL binary into another authoritative file or overwrite prior verification
- **Trace:** BRS-POS-02-R001, BRS-POS-03-R003
- **Runtime:** NOT_RUN

### AC-DOC-X02: PO-only supplier evidence
- **Positive:** Exact native PO identity accepted without a fictitious SO or load; record gap if current schema cannot express it
- **Negative that MUST fail:** Fabricate a plasticos.load for PO-only inbound or match newest transaction
- **Trace:** BRS-POS-03-R002, BRS-POS-02-R006
- **Runtime:** NOT_RUN

### AC-DOC-X03: Ambiguous reply or alias intake
- **Positive:** File remains in Inbox with one review Activity and no auto-compliance
- **Negative that MUST fail:** Recency or partner-only matching chooses wrong order
- **Trace:** BRS-POS-02-R006, BRS-POS-03-R002, BRS-POS-09-R003
- **Runtime:** NOT_RUN

### AC-DOC-X04: Two companies same reference
- **Positive:** File and verification never leak across companies
- **Negative that MUST fail:** Sudo matcher binds another company due to colliding order number
- **Trace:** BRS-POS-03-R014
- **Runtime:** NOT_RUN

### AC-DOC-X05: Receipt is not verification
- **Positive:** A native Request placeholder can be filled, yet business compliance remains pending until authorized verification
- **Negative that MUST fail:** Just uploading a file clears invoice close
- **Trace:** BRS-POS-02-R005, BRS-POS-03-R004
- **Runtime:** NOT_RUN

### AC-DOC-X06: Partial buyer Receiving
- **Positive:** Only quantity and loads explicitly covered become eligible; rest remain pending
- **Negative that MUST fail:** One received PDF confirms all loads or full order
- **Trace:** BRS-POS-03-R009, BRS-POS-03-R010
- **Runtime:** NOT_RUN

### AC-DOC-X07: CST certificate sufficiency
- **Positive:** Certified CST proof inspected; SCALE tag is only a category
- **Negative that MUST fail:** Bare scale tag satisfies certified document requirement
- **Trace:** BRS-POS-03-R011, BRS-POS-03-R012
- **Runtime:** NOT_RUN

### AC-DOC-X08: Side-effect-free compute
- **Positive:** Compliance recompute returns missing IDs without posting or communicating
- **Negative that MUST fail:** Automated file receipt calls account.move.action_post
- **Trace:** BRS-POS-03-R007, BRS-POS-03-R008, BRS-POS-09-R013
- **Runtime:** NOT_RUN

### AC-DOC-X09: Internal-only Documents Request
- **Positive:** Request to authorized internal assignee, external supplier only receives Linda Mail
- **Negative that MUST fail:** Native Request sends upload/share link to supplier
- **Trace:** BRS-POS-02-R004, BRS-POS-02-R011, BRS-POS-09-R002
- **Runtime:** NOT_RUN

### AC-DOC-X10: Native reminder control collision
- **Positive:** No native Documents external reminder if Linda is authoritative; one outbound per party/day/revision
- **Negative that MUST fail:** Documents Activity automatic reminder and Linda both email same supplier
- **Trace:** BRS-POS-09-R006, BRS-POS-09-R010
- **Runtime:** NOT_RUN

### AC-DOC-X11: Calendar and clock source
- **Positive:** Pickup +1/+5 supplier, +2/+6 carrier; delivery +1/+5 buyer, all business-day under approved locale
- **Negative that MUST fail:** Use transaction create_date or pickup for buyer clock
- **Trace:** BRS-POS-09-R007, BRS-POS-09-R008, BRS-POS-09-R009
- **Runtime:** NOT_RUN

### AC-DOC-X12: Business day and holiday unknown
- **Positive:** Known Mon–Fri test passes; holiday behavior remains UNKNOWN until operator policy
- **Negative that MUST fail:** Invent holiday exception or silently send during quiet hours
- **Trace:** BRS-POS-09-R011
- **Runtime:** NOT_RUN

### AC-DOC-X13: Cancel / supersede while pending
- **Positive:** Stops outstanding intent, preserves historical evidence, no new duplicate Activity
- **Negative that MUST fail:** Stale superseded evidence sends reminder after cancellation
- **Trace:** BRS-POS-02-R007, BRS-POS-09-R012
- **Runtime:** NOT_RUN

### AC-DOC-X14: AI auto-sort cannot approve
- **Positive:** Native AI proposes folder/tag, authorized evidence verification remains separate
- **Negative that MUST fail:** AI output sets weights, accepts certificate or posts vendor bill
- **Trace:** BRS-POS-02-R010, BRS-POS-03-R013
- **Runtime:** NOT_RUN

### AC-DOC-X15: Provider/Studio gate
- **Positive:** Manual/native workflow functions with Studio and paid digitization disabled
- **Negative that MUST fail:** Installation triggers AI subscription or external digitization billing
- **Trace:** BRS-POS-02-R013, BRS-POS-09-R016
- **Runtime:** NOT_RUN

### AC-DOC-X16: Native versions and shortcuts
- **Positive:** New version retains historic original; shortcut points to same source
- **Negative that MUST fail:** PDF merge destroys sole original and provenance
- **Trace:** BRS-POS-02-R007, BRS-POS-02-R008, BRS-POS-02-R009
- **Runtime:** NOT_RUN

### AC-DOC-X17: No blanket accounting lock
- **Positive:** Absent CST does not block buyer AR or commercial close; open carrier issue remains
- **Negative that MUST fail:** Missing carrier CST blocks unrelated buyer invoice
- **Trace:** BRS-POS-03-R011
- **Runtime:** NOT_RUN

### AC-DOC-X18: Two-worker due evaluation
- **Positive:** Two cron workers do not create duplicate external intents or Activities; failed SMTP retains unknown
- **Negative that MUST fail:** Race yields two sends or treats queued as sent
- **Trace:** BRS-POS-09-R003, BRS-POS-09-R010
- **Runtime:** NOT_RUN

### AC-DOC-X19: Use Odoo platform only
- **Positive:** Existing Odoo native automation and ir.cron schedule separate domain jobs
- **Negative that MUST fail:** Create separate worker service or global Linda-only scheduler
- **Trace:** BRS-POS-09-R004, BRS-POS-09-R005
- **Runtime:** NOT_RUN

### AC-DOC-X20: Activation still separate
- **Positive:** Installing BRS files changes no Odoo registry, templates, tasks, records, messages or finance
- **Negative that MUST fail:** Install BRS ZIP activates live automation or bank movement
- **Trace:** BRS-POS-09-R014, BRS-POS-09-R015
- **Runtime:** NOT_RUN

### AC-DOC-X21: 3PL vs dropship proof
- **Positive:** Document evidence can associate genuine PO, native picking and load when present without inventing missing entities
- **Negative that MUST fail:** Require SO or PlasticOS load for every PO-only warehouse document
- **Trace:** BRS-POS-03-R002, BRS-POS-03-R014
- **Runtime:** NOT_RUN

### AC-DOC-X22: Native invoice intake draft
- **Positive:** Vendor PDF creates appropriately scoped draft only when accounting owner authorizes
- **Negative that MUST fail:** Native digitization auto-posts or self-bills without vendor invoice
- **Trace:** BRS-POS-02-R012, BRS-POS-09-R013
- **Runtime:** NOT_RUN

### AC-DOC-X23: Confidential double-blind output
- **Positive:** Only recipient-authorized evidence leaves via owner Mail template; no internal folder grant
- **Negative that MUST fail:** Supplier receives buyer Receiving document or access to Documents folder
- **Trace:** BRS-POS-02-R011, BRS-POS-03-R014
- **Runtime:** NOT_RUN

### AC-DOC-X24: Source law versus implementation
- **Positive:** First implementation checks accepted ADRs and installed EE behavior; remains bounded if conflict
- **Negative that MUST fail:** Working BRS suppresses accepted ADR or claims EE test PASS without execution
- **Trace:** BRS-POS-09-R017
- **Runtime:** NOT_RUN

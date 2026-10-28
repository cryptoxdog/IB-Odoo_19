# PlasticOS System Invariants

**Repository:** `cryptoxdog/IB-Odoo_19`  
**Proposed version:** `3.2.0`  
**Status:** DRAFT successor to working v3.1.0 r1, not admitted, not implementation authority  
**Original draft review baseline:** `Staging@e22eb6c0c34d9ea124ae4a04715f7948c3316d86`  
**Current bounded source comparison:** `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112` (not a full-repository assurance receipt)  
**Draft predecessor:** working v3.1.0 r1 (SHA-256 `7b764e9a08430f47e03469b3573c014332215d1d80c4a28c470825e222db45ba`); original operator v3.0.0 r3 remains the immutable source in the uploaded pack  
**Supersedes:** `INVARIANTS.md` v2.2.0 only after explicit approval

## Constitutional scope

These invariants define durable, falsifiable boundaries of PlasticOS on Odoo 19 Enterprise. They govern **who may establish a fact, what evidence makes it valid, and which operations may change it**. They do not replace the Logistics BRS, document-rule configuration, accepted ADRs, Odoo's native contracts, or executable tests.

**MUST** and **MUST NOT** are proposed requirements until admission. A source assertion, observation, inference, proposal, approval, business event, and posted financial fact are different kinds of truth. Storage, projection, visibility, and API access do not independently confer authority. A missing fact remains unknown, not zero, false, confirmed, or successful by default.

A candidate belongs here only if it is **durable, cross-cutting, consequential, and independently falsifiable**. A threshold, formula, deadline, model field, cron interval, specific document matrix, or implementation recipe belongs to its BRS, ADR, or code owner.

## I. Platform, authority, and identity

### POS-INV-01 | Native Odoo Before Custom Machinery

PlasticOS **MUST** use applicable native Odoo 19 Enterprise capabilities before implementing a parallel model, workflow, scheduler, document store, mail processor, stock mechanism, or accounting process. Custom behavior **MUST** address a demonstrated domain gap while preserving the native owner's lifecycle and data semantics.

**Rejects:** building a second mail queue or inventory ledger because native integration requires more work.

### POS-INV-02 | One Writer per Business Fact

Each consequential business fact **MUST** have one authoritative writer. Sales/Purchase own native order state; Inventory owns physical stock; Accounting owns Odoo postings; native Documents/attachments own original files; PlasticOS domain services own explicitly delegated verification and operational decisions. Other representations **MUST** be projections, evidence, or governed commands to the owner, not competing writes.

A mirror, dual-write, feature flag, imported record, or installed semantic model **MUST NOT** acquire authority by existence. Any authority cutover requires an explicit scope, approved transition, observable reconciliation, and a safe recovery boundary. Cross-system settlement has the additional rule in POS-INV-14.

**Rejects:** a compatibility document mirror independently overturning the native verification decision.

### POS-INV-03 | No Fabricated Business Reality

An order, load, stock change, readiness or delivery confirmation, approval, commitment, posting, or settlement **MUST** arise from a real eligible source and its authorized business operation. Evidence **MUST** preserve whether it is a requirement, assertion, observation, inference, proposal, or accepted fact; neither AI confidence nor an unverified source claim may silently promote it.

Unknown or contradictory prerequisites remain unresolved. A provisional review record is permitted; a fictional counterpart, event, or completed state is not. Native workflow-generated records remain valid when their real prerequisites are satisfied.

**Rejects:** creating a fictitious PO to complete an SO, or accepting carrier-reported delivery as verified receipt without required evidence.

### POS-INV-04 | Stable Identity, Complete Accounting, Replay

Each ingestion or integration path **MUST** use its approved stable source identity and a single authoritative ingestion seam. Historical ERP data uses the accepted SQL-projection pipeline; CRM data uses its approved provider API and crosswalk. Names, emails, guessed associations, and mutable content are not identity keys. Accepted semantic entity identities must remain stable through changes and supersession.

Replaying the same logical input **MUST** neither duplicate records/effects nor lose earlier evidence; concurrent attempts must resolve consistently. Every in-scope source item **MUST** have an explicit disposition, counts and relevant financial populations **MUST** reconcile, and checkpoints **MUST NOT** advance ahead of committed work. Test extracts are not replacement production import authorities.

**Rejects:** a rerun duplicates contacts, silently drops unmatched payables, or advances a CRM watermark beyond a failed page.

### POS-INV-05 | Company, Party, and Privilege Isolation

Every consequential read, association, write, report, attachment, and message **MUST** enforce its applicable legal-company scope, authorized role, and counterparty audience. Participation in the same transaction does not entitle a supplier, buyer, carrier, follower, or automation identity to another party's confidential information. Legitimate explicitly authorized intercompany operations remain possible, but isolation may never be bypassed implicitly.

Privilege elevation **MUST** be narrowly scoped after effective access checks. Credentials and sensitive business data belong only in approved stores and communication paths.

**Rejects:** a buyer-facing report or chatter follower exposing confidential supplier documents through an indirect link.

## II. Documents, approval, and compliance

### POS-INV-06 | One Original, Exact Associations

Each source-document identity **MUST** preserve one canonical original in native Odoo Documents/attachment storage. It **MAY** support multiple independently justified, typed associations to orders, loads, pickings, transactions, parties, evidence obligations, and later-defined booking or fulfillment identities without multiplying the original. Identical bytes do not automatically imply identical source-document identity.

Candidate matches and verified business associations are **different states**. A candidate may be proposed from document content, message identifiers, source references, or AI extraction, but an authoritative link **MUST** be established only from sufficient attributable identifiers and context: the correct company, party, subject, purpose, applicable physical/commercial scope, and source revision. Filename resemblance, nearest date, partial order number, shared partner, or AI score **MUST NOT** finalize an ambiguous association. The absence of a suitable current relationship or native schema **MUST** remain a named capability gap, not justify fabrication of an order, transaction or load.

Corrections, reclassification, revisions, and supersession **MUST** preserve source bytes and earlier accepted associations as attributable history. Neither a native file shortcut nor a new evidence projection is a second original or a verification writer.

**Rejects:** a booking PDF auto-linked to the newest transaction for a partner, or one verified original copied into several independent authoritative files to attach to partial movements.

### POS-INV-07 | Classification Is Not Verification

Receipt, OCR, parsing, tagging, matching, hashing, and AI inference **MUST NOT** themselves verify a document or authorize an override. Verification **MUST** be an attributable action by the designated authority against the correct original, classification, party, purpose, and current revision; an override **MUST** retain its authorization and reason. Earlier approved evidence remains immutable, with material corrections recorded as successors.

Only current verified evidence or an explicitly authorized override may satisfy a documentary obligation. The BRS and document-rule owner determine the particular required classes and conditions.

**Rejects:** a high-confidence classification toggling `verified` or an updated attachment inheriting approval of older bytes.

### POS-INV-08 | Evidence Gates Are Operation-Specific

An evidence requirement **MUST** be assessed for the exact action, company, responsible party, and current document/evidence revision. Commercial order issue, dispatch, receiving, customer invoicing, supplier settlement, operational close, and financial close have distinct prerequisites; a requirement for one **MUST NOT** silently block or satisfy another.

The applicable BRS or configured rule determines the exact required documents, permitted equivalents, and overrides. Present-but-unverified, stale, expired, or unrelated evidence cannot satisfy a verification gate.

**Rejects:** missing carrier scale evidence automatically blocking an otherwise eligible buyer invoice without a rule applicable to that invoice.

### POS-INV-09 | Compliance Evaluation Is Observational

Reading or computing compliance **MUST** assess existing evidence and rule state without exercising separate business authority. It **MUST NOT** post or reverse accounting, mutate commercial or stock state, dispatch a load, approve a document, or send external correspondence. An authorized command may act *after* evaluating the applicable gate; the evaluation itself may only maintain ordinary derived assessment state.

**Rejects:** a computed compliance field calling `account.move.action_post()`.

## III. Commercial, physical, and financial truth

### POS-INV-10 | Orders Are Independent; State Changes Are Real

A legitimate PO or SO **MUST** be independently creatable, approved, issued, canceled, or reopened through its actual native Odoo lifecycle. Neither order requires a fabricated counterpart, transaction, or load. An Odoo-native downstream transaction created by a genuinely eligible workflow is not fabrication. Draft/creation is not confirmation, and confirmation is not physical readiness.

Cancellation and legitimate reconfirmation represent distinct lifecycle events. Historical imports **MUST NOT** synthesize procurement, postings, shipments, or other events merely to imitate a source status.

**Rejects:** a PO-only inventory purchase being forced through a company-less load or fictitious SO.

### POS-INV-11 | Stock Truth Is Not Dispatch Permission

Physical inventory **MUST** derive from valid native Odoo stock movements and stock records, respecting actual ownership, custody, location, quantities, and route. Dropship and third-party custody must not invent on-hand stock. Documents, invoices, and PlasticOS load states **MUST NOT** independently modify physical inventory.

Reservation or picking assignment alone **MUST NOT** establish site readiness, accepted appointment, carrier authorization, packet acknowledgment, or physical dispatch. Every dispatch path must pass the same applicable logistics-release checks. Physical milestones remain distinct from financial completion.

**Rejects:** `stock.picking` becoming `assigned` and automatically sending a carrier to an unready facility.

### POS-INV-12 | Commercial Weights Have Distinct Authorities

Supplier settlement weight, buyer billing weight, carrier-certified measurements, and operational estimates **MUST** retain their own sources, units, and acceptance authority. Gross, certified tare, certified net, packaging tare, and billable material net **MUST NOT** be treated as interchangeable facts. A computed `final_weight` or convenient fallback cannot silently replace an accepted commercial weight.

Conflicts remain unresolved until the designated adjudication. Arithmetic, tolerances, minimums, and chargeback thresholds stay in the BRS or contractual rules.

**Rejects:** using carrier-certified net weight to overwrite independently accepted buyer billing weight.

### POS-INV-13 | One Economic Effect; Corrections Preserve History

Claims, discrepancies, and logistics exceptions are operational evidence, **not** accounting postings. Each economic adjustment **MUST** be recognized at most once through authorized native accounting and applicable stock valuation; credits, debits, claims, allocations, and reconciliations cannot independently book the same effect.

Physical close protects historical fulfillment and original records, **not** an absolute ban on later authorized financial corrections. Such corrections use proper native credit, debit, reversal, or adjustment operations without silently rewriting posted originals or reopening physical events.

**Rejects:** a vendor credit booked once in Accounting and again as a separate posted claim recovery, or a legitimate credit note denied solely because the physical load closed.

### POS-INV-14 | Exactly One Settlement Writer per Scope

For each legal company and accounting period, **one designated system** MUST own operational settlement posting and payment reconciliation. Any expressly authorized partial cutover **MUST** define disjoint obligations and prevent overlapping writers. An imported historical document **MUST NOT** imply that Odoo collected, paid, posted, or reconciled it. External settlement ownership remains intact until an explicitly authorized, reconciled accounting cutover establishes the new boundary.

Cutover **MUST** preserve opening positions, payment and source identities, and a nonoverlapping writer transition; it cannot double-post or silently discard prior settlement evidence.

**Rejects:** paying or reconciling one historical obligation in both the external accounting system and Odoo.

## IV. Automation and correspondence

### POS-INV-15 | Authorized Automation; One Outbound Intent

Automation **MUST** distinguish disabled, shadow, and live effects and prevent installation, import, test, and replay from causing unauthorized external action. Each consequential outbound communication through the approved Odoo Mail path **MUST** bind a durable obligation to its actual order/load/request owner, company, recipient, purpose, and lifecycle revision. Due times derive from real business milestones with the applicable local-time and business-day contract.

Native order release, not draft creation, authorizes order issuance. An unsent issue withdrawn on cancellation is not a sent cancellation; a previously communicated cancellation creates its own ordered obligation. Legitimate reopening and reconfirmation begin a new issuance cycle, while repetition within a cycle does not. Native/provider queuing, acceptance, uncertain outcome, acknowledgment, and business acceptance **MUST** remain distinguishable. Uncertain delivery is reconciled before any unsafe resend: **exactly-once intent is not exactly-once external delivery**.

Documents Requests and internal file access **MUST NOT** become an ungoverned external authorization or sharing channel; external party requests use a suitably scoped approved communication path.

**Rejects:** shadow-mode email, double-sending after provider timeout, or a new issue overtaking an unresolved cancellation to the same recipient.

### POS-INV-16 | AI Interpretation Is Not an Authorized Business Action

An inbound document, mail message, reply, or machine-produced result **MUST** retain its exact original, source revision, company, party, subject, purpose and attributable provenance before it can inform an operation. Replies to unrelated, canceled or superseded requests cannot satisfy present obligations. Sender address, thread position, forwarded content, bearer links, OCR output, a model confidence score, and extracted fields are each individually insufficient proof of identity, business commitment or event completion.

Native Odoo Documents AI, bounded deterministic parsers, and approved external intelligence **MAY** propose typed evidence, source fields, exact-link candidates, contradictions, missing prerequisites, affected downstream objects and suggested next actions. Every consequential proposal **MUST** preserve source coordinates, field-level provenance, revision, confidence/uncertainty, and the distinguishing acceptance or rejection reason. The designated Document/Logistics/Commercial/Stock/Accounting owner **MUST** validate the action's exact prerequisites, rights and current state before any write or outbound side effect. An AI server action, inference response or workflow suggestion **MUST NOT** directly impersonate that owner, and an unapproved action remains proposed or blocked. This does not impose an extra human approval where a deterministic owner rule already lawfully authorizes the operation.

**Rejects:** a booking extraction silently overwrites the current ERD, a reply to the wrong Linda request establishes READY, or a native AI action changes dispatch or invoice state without going through the domain owner's operation gate.

## V. External intelligence and trustworthy outcomes

### POS-INV-17 | One External Intelligence and Transport Plane

For canonical matching/scoring and enrichment/inference, **CEG and EIE own intelligence**, **Constellation.Gate owns routing/admission**, and **Gate_SDK owns transport**. Odoo owns the domain request, operator interaction, and resulting business persistence. Production calls **MUST** pass through the single designated `plasticos_gate` SDK seam; Odoo **MUST NOT** recreate packets, signing, transport retries, routing, or direct worker access.

A missing SDK capability is an upstream capability gap, not license for a local shadow implementation. The same logical attempt preserves its operation identity; a genuinely new authorized attempt uses a new correlatable identity. Local web-lead triage is not an alternative canonical matching or enrichment engine.

**Rejects:** Gate failure triggering a local matcher, or an Odoo-side custom HTTP transport to EIE.

### POS-INV-18 | External Results Cannot Invent Success or Writeback

Transport receipt, canonical domain completion, durable persistence, and business success **MUST** be judged separately. Disabled, unreachable, malformed, incomplete, or failed matching/enrichment **MUST** produce classified, durable, operator-visible failure evidence, not empty success or substituted local output.

External results are **proposals**, not CRM write commands. Only Odoo's approved allowlist, review policy, merge-not-overwrite rules, and provenance controls may modify authoritative partner data. A field-family cutover cannot silently override those business protections.

**Rejects:** a noncompleted Gate response mutating an existing customer field or being displayed as a successful match.

## VI. Structural integrity and release proof

### POS-INV-19 | Installable, Acyclic, Migratable Odoo 19

The addon dependency graph **MUST** remain acyclic and accurately declare consumed dependencies. Models, fields, XML IDs, access rules, views, imports, and data load order **MUST** resolve on the supported Odoo 19 Enterprise runtime. Changes requiring reload **MUST** version the affected addon and use an appropriately scoped upgrade; migrations **MUST** preserve identities and be repeatable and recoverable under approved safety conditions.

A conceptual layer diagram, universal `noupdate` rule, or blanket ACL formula **MUST NOT** override actual lifecycle and model semantics. Destructive migrations require separate authorization and verified recovery capability.

**Rejects:** a green source lint with an addon that fails to install because a dependency or referenced model is absent.

### POS-INV-20 | Proof and Activation Are Separate Decisions

A claim of correctness, readiness, or completion **MUST** identify the exact code revision, environment, executed assertions, and limitations. Static checks and mocks do not prove Enterprise registry behavior; Community tests do not prove Enterprise integration; simulated provider responses do not prove live delivery. Transaction, concurrency, rollback, import replay, and external SDK paths need proof at the actual affected seam. `NOT_RUN`, skipped, partial, blocked, and unknown are never `PASS`.

Test execution **MUST** protect production data and use authorized, compatible isolated environments. Passing tests or merging code **MUST NOT** authorize production deployment, financial-writer cutover, live mail, or other consequential activation; those remain operator-controlled decisions.

**Rejects:** claiming full Enterprise acceptance from pure-Python CI, or activating live correspondence because a migration installed a scheduler.

## VII. Cross-module trade and transport integrity

### POS-INV-21 | Independent Commitments, Allocations, Movements, and Bookings

Commercial purchase and sale commitments, actual stock/custody, fulfillment allocations, physical loads/containers, and transport bookings **MUST** retain distinct identities and independently correct cardinalities. A single PO or SO **MAY** fulfill across many partial movements; a single booking **MAY** group containers from more than one supplier, PO, transaction or allocation; one movement **MAY** remain legitimately unsold while owned or in transit. A buyer, sale or universal one-to-one order/load/booking relationship **MUST NOT** be fabricated or imposed as a prerequisite for an otherwise valid native purchase or movement.

Quantities, physical identities, allocations and economic effects **MUST** reconcile through the authorized native commercial/stock lifecycle. Splitting, grouping, in-transit sale allocation, or reporting an aggregate **MUST NOT** duplicate or erase movements, source commitments, custody or postings. These are **future-compatible product obligations** where current singular legacy fields cannot represent a scenario; they **do not themselves authorize schema expansion, deletion of a current constraint, migration, warehouse launch, or Export activation**. The precise relationship and recovery design belongs to the affected native/Logistics/Document BRS or ADR owner and must first prove compatibility with existing data.

**Rejects:** changing a four-load PO into four artificial POs, fabricating a buyer to dispatch real owned material, or treating five containers on one booking as one transaction/load without an approved allocation model.

### POS-INV-22 | Revision-Bound Downstream Validity

When authoritative source facts, document versions, terms, schedules, equipment, party identity or other prerequisites change, the successor **MUST** preserve its source attribution, prior value, candidate/current value, revision, temporal precision and required approval. For each downstream action, document/report, carrier commitment, outstanding communication and evidence gate, the designated owner **MUST** determine whether it actually depends on the changed fact and re-evaluate only that affected scope against the authoritative current revision. This includes native Documents evidence, Linda obligations and any later-approved booking context; a copy of old booking text is not proof that a current booking remains valid.

An amendment **MUST NOT** itself authorize a replacement booking, change an approved rate, dispatch or resend, reverse inventory or financial history, complete a customs filing, or erase a completed physical event. Unaffected commitments and actual history remain intact. Conflicting source versions or unclear linkage remain reviewable candidates rather than silently overwriting stored facts. This strengthens, but does not replace, POS-INV-04 identity/replay and POS-INV-15 outbound-intent authority.

**Rejects:** an updated cutoff invalidates all loads under a commercial order indiscriminately, resends an earlier booking unasked, or removes an already accepted terminal event from historical evidence.

### POS-INV-23 | Explicit Trade Roles, Physical Destinations, and Milestones

Commercial buyer/supplier, title or inventory owner, physical custodian, freight arranger/payer, contracted delivery/risk point, container/terminal destination, exporter/filer, and document/message audience **MUST** remain separately attributable roles. Industry quotation shorthand, formal Incoterms, a booking reference, a consignee, a port/ramp destination, or a tracking event **MUST NOT** independently determine another role, legal obligation, or commercial handoff.

Supplier readiness, empty-container pickup, cargo loading, truck departure, arrival at a port/ramp, accepted gate-in, vessel loading, sailing, discharge, customer delivery, filing acceptance, and financial completion are distinct events with their own eligible evidence and authorized acceptance. External provider updates **MAY** contribute attributed observations but cannot impersonate regulator, carrier, stock, accounting, or contractual authority. Site-specific operation details and required proof remain with their relevant BRS owner.

**Rejects:** assuming the buyer's factory is a port-bound truck's destination; inferring official FAS risk transfer from industry 'FAS port'; treating a supplier's 'booking complete' email or third-party ETA as verified terminal gate-in, ocean arrival, customs filing, or customer receipt.

## BAN001 | Permanent Legacy Identifier Prohibition

**Preserved authority:** Former `INVARIANTS.md` v2.2.0 invariant 20. Its scope, all-case ban, and blocking enforcement remain intact; its stable compatibility identity is **BAN001**.

The designated eight-character legacy vendor identifier has ASCII code points `99, 105, 101, 116, 114, 97, 100, 101`. It **MUST NOT** appear as a contiguous sequence, in any casing, in **any tracked repository path or tracked content**.

This includes application code, tests, fixtures, documentation, comments, configuration, manifests, Odoo metadata, migrations, generated artifacts, filenames, directory components, symlink targets, and binary files. **There are no exemptions, allowlists, ignore comments, per-file waivers, or historical carve-outs.** Correct the generating source, never silence the checker or merely patch ephemeral output. Necessary external identifiers must be supplied or reconstructed at runtime without placing the forbidden bytes in the tracked tree.

`ci/check_banned_identifier.py` remains the **single canonical blocking guard**. It evaluates git-index paths and content, resolves indexed symlink targets, checks bytes including binaries, and fails closed when the index or object cannot be read. CI, `make ban-check`, and the pre-commit hook must continue to invoke this guard; its negative regressions must preserve their existing coverage. Violation blocks acceptance.

## Ownership, precedence, and admission

- **This file** owns repository-level architectural boundaries only, **once approved**.
- [`plasticos_logistics/business_rules/README.md`](plasticos_logistics/business_rules/README.md), its seven BRS chapters, and [`SUPERSESSION.md`](plasticos_logistics/business_rules/SUPERSESSION.md) own their applicable specific business policy and narrow later operator corrections. Preserve stable BRS IDs and source history.
- Accepted [`docs/adr/`](docs/adr/) and [`docs/adr/gate-integration/`](docs/adr/gate-integration/) decisions own their specific architecture and integration contracts until explicitly superseded. In particular, external-intelligence and import authorities are not redefined by abbreviation.
- Native Odoo and installed Enterprise features provide actual platform contracts; code and test results provide **implementation evidence**, not power to amend an invariant.

**Admission requires** explicit operator approval of meaning, a documented v2.2.0-to-v3 mapping, reconciliation of material BRS/ADR conflicts, and test/proof expectations for each applicable boundary. Only then should implementation, agent guidance, and enforcement be aligned. Do not mark unimplemented target behavior as currently compliant. BAN001 may not be weakened in this process.

**Current status:** Architectural draft only. No repository modification, PR, database migration, Export or warehouse/shop-floor implementation, external email, financial cutover, or activation is authorized by this document. The MVP may progress using already admitted, applicable authority without waiting for optional future scope.

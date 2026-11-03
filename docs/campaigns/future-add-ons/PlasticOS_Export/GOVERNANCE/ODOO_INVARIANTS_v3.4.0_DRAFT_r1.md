# PlasticOS System Invariants

**Repository:** `cryptoxdog/IB-Odoo_19`  
**Proposed version:** `3.4.0`  
**Status:** DRAFT working successor to v3.3.0 DRAFT r1, not admitted or an assertion of implementation conformance  
**Original draft review baseline:** `Staging@e22eb6c0c34d9ea124ae4a04715f7948c3316d86`  
**Additional Export source review:** `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112` (not a new full-repository assurance receipt)  
**Draft predecessor:** operator upload `ODOO INVARIANTS_v3.0.0_DRAFT_r3.md`, SHA-256 `5df7eae3aed672d68311c9717697e3f3cfe5ac05d0e962e13a7c340513e55d0e`  
**Immediate working predecessor:** `ODOO_INVARIANTS_v3.1.0_DRAFT_r1.md` SHA-256 `7b764e9a08430f47e03469b3573c014332215d1d80c4a28c470825e222db45ba`
**Latest draft predecessor:** `ODOO_INVARIANTS_v3.3.0_DRAFT_r1.md`, SHA-256 `771bae3682d2e3f49e800492bdf7be97c904c6e203884fc9f25053db87b7f781`  
**New scope:** POS-INV-26 for pre-code ripple-effect accountability; POS-INV-01 through POS-INV-25 and BAN001 retained without changing their normative contents  
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

Each source-document identity **MUST** preserve one canonical original in native Odoo Documents/attachment storage. It **MAY** support multiple independently justified, typed associations to orders, loads, pickings, transactions, parties, and evidence obligations without multiplying the original. Identical bytes do not automatically imply identical source-document identity.

Authoritative links **MUST** be established from sufficient attributable identifiers and context, including the correct company, party, subject, purpose, and revision. Filename resemblance, nearest date, partial order number, shared partner, or AI score may propose candidates **but MUST NOT** finalize an ambiguous association. Corrections and supersession preserve the source bytes and prior associations as audit history.

**Rejects:** attaching a supplier PDF to the newest PO for that partner and treating the guess as verified evidence.

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

### POS-INV-16 | Inbound Interpretation Has No Decision Authority

An external response **MUST** bind to the exact current request, authorized party, company, purpose, subject, and revision before it can inform a business transition. Replies to unrelated, canceled, or superseded requests cannot satisfy present obligations. Sender addresses, thread position, forwarded content, bearer links, and LLM interpretations are individually insufficient to authenticate a commitment.

AI may extract **candidate facts**; only authorized deterministic domain validation can accept them, schedule a permitted next action, or create an attributable exception. This does not impose an extra human approval on routine actions already authorized by the business rules.

**Rejects:** a forwarded old email automatically establishing supplier READY or carrier acknowledgment.

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

Commercial purchase and sale commitments, actual stock/custody, fulfillment allocations, physical loads/containers, and transport bookings **MUST** retain distinct identities and independently correct cardinalities. A single PO or SO **MAY** fulfill across many partial movements; a single booking **MAY** group containers from more than one supplier, PO, transaction, or allocation; one movement **MAY** legitimately remain unsold while owned or in transit. Neither a sale, a buyer, nor a one-to-one order/load/booking relationship **MAY** be fabricated or required universally as a surrogate for a missing physical or commercial fact.

Quantities and allocations **MUST** reconcile through the authorized native commercial/stock lifecycle; splitting, grouping, changing a sale allocation in transit, or reporting an aggregate **MUST NOT** duplicate or erase physical movements, source commitments, custody or economic effects. Any exact ownership/relationship realization belongs to the applicable BRS/ADR/model owner, never to an invented second quantity ledger.

**Rejects:** five booking containers being treated as five loads from a single PO when they actually originate from four supplier POs; one four-load PO being replaced by four artificial POs; requiring a fictional buyer before a legitimate purchase or transport move.

### POS-INV-22 | Revision-Bound Downstream Validity

When authoritative source facts, terms, schedules, equipment, evidence, or identities change, the change **MUST** preserve source attribution, the former value/revision, the new candidate/current value, temporal precision, and the governing approval. Each dependent action, document/report, appointment, freight commitment, outstanding communication, or acceptance gate **MUST** be re-evaluated only for its actual affected scope against the authoritative current revision. A stale projection or previously issued artifact **MUST NOT** remain silently eligible for a new consequential operation.

A source amendment **MUST NOT** on its own authorize a replacement carrier booking, changed approved rate, physical dispatch, resend, financial posting, customs filing, or retrospective erasure of a completed event. Unaffected obligations and historical actual events remain intact, and an ambiguous amendment remains a reviewable candidate rather than an automatic overwrite. This supplements, without replacing, the identity/replay and outbound-intent protections in POS-INV-04 and POS-INV-15.

**Rejects:** a rolled ocean booking silently changes four unrelated drayage loads; a new cutoff automatically dispatches a truck or resends an earlier email; a prior gate-in event disappears when a booking date changes.

### POS-INV-23 | Explicit Trade Roles, Physical Destinations, and Milestones

Commercial buyer/supplier, title or inventory owner, physical custodian, freight arranger/payer, contracted delivery/risk point, container/terminal destination, exporter/filer, and document/message audience **MUST** remain separately attributable roles. Industry quotation shorthand, formal Incoterms, a booking reference, a consignee, a port/ramp destination, or a tracking event **MUST NOT** independently determine another role, legal obligation, or commercial handoff.

Supplier readiness, empty-container pickup, cargo loading, truck departure, arrival at a port/ramp, accepted gate-in, vessel loading, sailing, discharge, customer delivery, filing acceptance, and financial completion are distinct events with their own eligible evidence and authorized acceptance. External provider updates **MAY** contribute attributed observations but cannot impersonate regulator, carrier, stock, accounting, or contractual authority. Site-specific operation details and required proof remain with their relevant BRS owner.

**Rejects:** assuming the buyer's factory is a port-bound truck's destination; inferring official FAS risk transfer from industry 'FAS port'; treating a supplier's 'booking complete' email or third-party ETA as verified terminal gate-in, ocean arrival, customs filing, or customer receipt.

### POS-INV-24 | Actionable Dashboards and Source-Traceable Drill-Down

Every PlasticOS / RecycleOS dashboard **MUST** act as a truthful, actionable summary and navigation layer over its in-scope authoritative operational views and reports. It **MUST** expose the most decision-relevant current measures and exceptions from each material report it is meant to represent and provide a direct contextual path from each dashboard summary to the precise supporting report population, constituent records, and evidence when the user is authorized to inspect them. A dashboard may deliberately omit a nonmaterial or restricted report, but may not misleadingly claim coverage it does not provide. The exact report set and metrics belong to the applicable module BRS.

Dashboard summaries and linked detail **MUST** use the same explicit business grain, company/user rights, audience restrictions, effective filters, reporting period, relevant operational scope, and source/revision/time semantics. A click or navigation action **MUST NOT** broaden access, silently drop a material filter, double-count underlying joins, or convert a current/live report into a falsely reproducible historical snapshot. When records change between summary and drill-down, display the changed-as-of context or refresh the summary rather than pretending the numbers still reconcile. Unknown, unavailable, stale, provisional, and confirmed values **MUST** remain distinguishable, including zero versus no evidence. Restricted data must never leak through cards, counts, links, exports or report destinations.

Dashboards **MUST NOT** establish competing business-fact authority, post/approve/send/dispatch by rendering, or require an independent dashboard database, reporting engine, scheduler or duplicate state ledger where native Odoo views, pivot/chart, spreadsheet dashboards and ordinary authorized actions suffice. Module-specific report coverage, metric definitions, navigation context and performance thresholds belong to their BRS and tests; this invariant governs all dashboards, not a compulsory fixed number of reports for unrelated modules.

**Rejects:** a bookings dashboard listing six reports without surfacing any of their key values; an "at-risk" metric opening an unfiltered list; a cross-company booking count exposed to a restricted user; five containers appearing as ten after a PO/document join; an unknown document status shown as zero missing; or a booking card linked to an outdated revision while labeled current.

### POS-INV-25 | Operational Modality Independence and Truthful Capability Optionality

Core commercial, inventory, document, logistics, and accounting workflows **MUST** remain operable through an authorized, evidence-sufficient non-scanning path when a site elects not to use barcodes, mobile dock applications, device integrations, or other optional automation. Product-wide availability of a capability **MUST NOT** imply that every company, site, work center, role, or operation adopts it. Site configuration **MUST NOT** silently disable requirements imposed by the actual transaction, governing law, safety policy, contract, or chosen stock operation.

Paperwork, manually entered facts, device readings, and AI-assisted extraction **MAY** serve as alternative input or evidence channels only when each meets the applicable source attribution, exact association, freshness, verification, authorization, and replay controls. **All consequential stock, manufacturing, commercial, logistics, and financial changes MUST still pass through their existing authoritative owner and valid state transition**, regardless of capture channel. Neither scanning a paper document nor scanning a barcode **MAY** independently certify a physical event or confer posting authority. Evidence granularity **MUST** remain truthful: without attributable package, lot, custody, or weight evidence, a report **MUST NOT** claim that level of traceability.

Changing a site's adoption mode **MUST** preserve prior identities, evidence, revisions, business events, and active obligations, and **MUST NOT** create parallel ledgers, duplicate stock postings, or fictitious devices, packages, or operator attestations. A disabled or unavailable optional capability **MUST** result in a supported manual/evidence route or an explicit blocked applicable operation, never a false successful action. Specific capture methods, document classes, scan configuration, validation matrices, automation thresholds, and user experiences belong to their domain BRS owners, not to this invariant.

**Rejects:** refusing a valid supplier receipt because a facility has no barcode scanners; marking an unsigned supplier packing slip as an accepted dock receipt solely because AI read it; manufacturing package-level genealogy from a paper total that contains no package identities; or double-posting a movement when a facility switches from scanner to paper intake.

### POS-INV-26 | Pre-Code Ripple-Effect Accountability

**No code gets written until every ripple effect is accounted for.** Before any implementation code, test code, migration, or generated source change begins, the proposed change **MUST** have a revision-bound, evidence-based impact closure covering every materially reachable direct and transitive effect across its authoritative owners and consumers. The closure **MUST** establish the intended change and its actual source coordinates; affected modules, dependencies, models, fields, identities, state transitions, read/write paths, access rules and company boundaries; native Odoo and external interfaces; background jobs and messages; reports and downstream projections; legacy data, upgrade/rollback and recovery; and positive, negative and regression proof obligations. It **MUST** account for effects both inside and outside the immediately edited module, including consequences that require **no code change**.

For each affected or credibly affected surface, the change owner **MUST** record its authoritative owner, exact source/revision and consumer path, expected effect, disposition (change, verified no-change, separately authorized dependency, or not applicable), rationale and evidence, test/proof owner, required migration/recovery, and execution order. An unexplored, disputed, unowned, unverified or otherwise unresolved **material** effect is a **blocking Unknown**, not a completed checklist item. Evidence of no-change **MUST** be a grounded finding, not silence or an empty search result. The closure **MUST** prove that affected downstream contracts remain valid or explicitly identify what must change before coding.

The scope is the bounded, source-discoverable dependency and effect closure for the requested change, not a claim to know unknowable future behavior. **Accounting for an effect** means establishing an actionable owner, disposition, dependency and proof obligation before coding; it does not falsely claim that planned implementation/tests have already passed. Newly discovered material effects, source revision changes or invalidated assumptions **MUST** stop the affected coding until the closure is updated and reaccepted. Neither a completed map, an agent's estimate nor this invariant grants permission to change another owner, revise frozen business meaning, bypass repository publication controls or deploy.

**Rejects:** editing Load company identity without tracing Security Base record rules, freight, dashboards, consumers and backfill; changing native Documents verification without accounting for legacy synchronization, reminders and compliance; adding a booking mail purpose while overlooking SQL constraints, reply attribution and native mail send-time guards; or writing a model first and discovering its dependent schema migration and access policy later.

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

**Current status:** Architectural draft only. No repository modification, PR, database migration, external email, cutover, or test execution is authorized by this document.

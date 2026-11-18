# INVARIANTS.md — PlasticOS System Invariants

**Repository:** `cryptoxdog/IB-Odoo_19`
**Status:** ACTIVE
**Version:** 3.0.0
**Admitted:** 2026-11-08
**Supersedes:** `INVARIANTS.md` v2.2.0
**Admission baseline:** `Staging@b5b6056f01639212e722ccdec5b964b36deee9f5`
**Source:** `docs/campaigns/future-add-ons/PlasticOS_Export/GOVERNANCE/SOURCES/ODOO_INVARIANTS_v3.0.0_DRAFT_r3.md`

This file is the canonical invariant source. It does not certify implementation conformance. Unimplemented behavior must not be described as compliance.

## Constitutional scope

These invariants define durable, falsifiable boundaries of PlasticOS on Odoo 19 Enterprise. They govern **who may establish a fact, what evidence makes it valid, and which operations may change it**. They do not replace the Logistics BRS, document-rule configuration, accepted ADRs, Odoo's native contracts, or executable tests.

**MUST** and **MUST NOT** are binding. A source assertion, observation, inference, proposal, approval, business event, and posted financial fact are different kinds of truth. Storage, projection, visibility, and API access do not independently confer authority. A missing fact remains unknown, not zero, false, confirmed, or successful by default.

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

### Single External Intelligence Authority

Preserved detection wiring for POS-INV-17 and POS-INV-18. Former v2.2.0 invariant 19. Local Odoo algorithmic engines are not architectural authority.

**Authority** (binding):
[`docs/adr/ADR-003-single-external-intelligence-authority.md`](docs/adr/ADR-003-single-external-intelligence-authority.md)
(supersedes ADR-002 §2 fallback-as-authority). Hub topology and “never Odoo → CEG/EIE direct”
from ADR-002 remain in force.

**Detection**: `tests/contracts/test_external_intelligence_authority.py`, `tests/contracts/test_no_local_intelligence.py`, `ci/check_no_local_intelligence.py`

**Enforcement**: Blocking contract tests + CI/pre-commit/Makefile drift guard + ADR-013 fail-closed transport. Reintroduction of retired modules or consumer-path local authority fails the build.

## VI. Structural integrity and release proof

### POS-INV-19 | Installable, Acyclic, Migratable Odoo 19

The addon dependency graph **MUST** remain acyclic and accurately declare consumed dependencies. Models, fields, XML IDs, access rules, views, imports, and data load order **MUST** resolve on the supported Odoo 19 Enterprise runtime. Changes requiring reload **MUST** version the affected addon and use an appropriately scoped upgrade; migrations **MUST** preserve identities and be repeatable and recoverable under approved safety conditions.

A conceptual layer diagram, universal `noupdate` rule, or blanket ACL formula **MUST NOT** override actual lifecycle and model semantics. Destructive migrations require separate authorization and verified recovery capability.

**Rejects:** a green source lint with an addon that fails to install because a dependency or referenced model is absent.

### POS-INV-20 | Proof and Activation Are Separate Decisions

A claim of correctness, readiness, or completion **MUST** identify the exact code revision, environment, executed assertions, and limitations. Static checks and mocks do not prove Enterprise registry behavior; Community tests do not prove Enterprise integration; simulated provider responses do not prove live delivery. Transaction, concurrency, rollback, import replay, and external SDK paths need proof at the actual affected seam. `NOT_RUN`, skipped, partial, blocked, and unknown are never `PASS`.

Test execution **MUST** protect production data and use authorized, compatible isolated environments. Passing tests or merging code **MUST NOT** authorize production deployment, financial-writer cutover, live mail, or other consequential activation; those remain operator-controlled decisions.

**Rejects:** claiming full Enterprise acceptance from pure-Python CI, or activating live correspondence because a migration installed a scheduler.

## BAN001 | Permanent Legacy Identifier Prohibition

**Preserved authority:** Former `INVARIANTS.md` v2.2.0 invariant 20. Its scope, all-case ban, and blocking enforcement remain intact.

### 20. Legacy Vendor Identifier Prohibition (BAN001)

**Rule**: The legacy vendor identifier designated **BAN001** is permanently prohibited from
every tracked repository path and every tracked repository content byte, in **every casing**.

BAN001 denotes the 8-character ASCII sequence with code points
`99, 105, 101, 116, 114, 97, 100, 101`. This document, the guard, the CI wiring, and the
guard's tests deliberately never spell that sequence contiguously — a policy that named its
own banned string would violate itself.

**Scope** (no carve-outs): application source, tests, fixtures, documentation, comments,
configuration, manifests, Odoo metadata (models, fields, views, external IDs, security files,
data files), migrations, generated artifacts, filenames, directory names, symlink targets, and
binary files.

**Exceptions**: **NONE.** BAN001 has no exclusion list, no allowlist, no ignore comment, and no
per-file waiver. It does not appear in the *Known False Positives* table below and must never be
added to it. Satisfying this invariant by suppressing the scanner is itself a violation.

**Generated content**: generated output is fully in scope. Repair the canonical source or the
generator and regenerate — never hand-patch a generated artifact that would reintroduce the
sequence on the next run, and never exempt it.

**Historical content**: files that are old, archival, captured from an external system, or kept
for compatibility are **not** exempt while they are in the active tracked tree.

**Deployed legacy identifiers**: where a real external server, database, or column name must be
addressed, supply it at run time (environment variable, parameter, or programmatic
reconstruction). Do not store the contiguous sequence in repository bytes to preserve a
connection default.

**Detection**: `ci/check_banned_identifier.py` — the single canonical implementation, invoked
identically by CI, `make ban-check`, and the `banned-identifier` pre-commit hook. It reads
every tracked path and its content from the **git index** — not the worktree, so a staged
violation cannot be hidden by deleting the file, and an unrelated deletion in a dirty tree
cannot false-block the build. It inspects every path component, resolves every symlink target
from the same index, and matches raw bytes, so binary files are covered. It fails closed: an
unreadable index or object exits non-zero rather than reporting clean.

**Enforcement**: blocking. `ci.yml` → `static-checks` (aggregated by `ci-gate-result`), plus
`tests/test_banned_identifier_guard.py`, which proves the guard rejects lowercase, uppercase,
capitalized and mixed-case content matches, filename-only matches, directory-name-only matches,
symlink-target matches (including a symlink absent from the worktree), binary matches, and
content staged then deleted on disk — while allowing near-miss lookalikes and not
false-blocking on an unrelated deletion. Violating fixtures are built at run time in a temporary repository, so no
prohibited literal is ever committed.

**Violation effect**: CI failure.

## Known False Positives

| Check | Excluded File/Path | Reason |
|-------|-------------------|--------|
| BAN001 | none | No exclusion. Do not add one. |

## Ownership and precedence

- **This file** owns repository-level architectural boundaries.
- [`plasticos_logistics/business_rules/README.md`](plasticos_logistics/business_rules/README.md), its seven BRS chapters, and [`SUPERSESSION.md`](plasticos_logistics/business_rules/SUPERSESSION.md) own their applicable specific business policy and narrow later operator corrections. Preserve stable BRS IDs and source history.
- Accepted [`docs/adr/`](docs/adr/) and [`docs/adr/gate-integration/`](docs/adr/gate-integration/) decisions own their specific architecture and integration contracts until explicitly superseded. In particular, external-intelligence and import authorities are not redefined by abbreviation.
- Native Odoo and installed Enterprise features provide actual platform contracts; code and test results provide **implementation evidence**, not power to amend an invariant.

Existing CI, pre-commit, and contract checks stay in force. This admission does not align agent guidance and does not change addon code.

## Invariant change process

To modify an invariant:

1. Propose the change with justification.
2. Obtain architectural review and approval.
3. Update this file.
4. Update enforcement tooling.
5. Remediate the existing codebase.

**No silent invariant violations.**

> **2026-11-13 amendment to POS-INV-18 (additive; this file is append-only).**
> Authorized by the operator for the cartridge-driven enrichment consumer campaign.
> POS-INV-18 covers more than partner data. A converge result may also propose values for a partner's
> material profiles (`plasticos.material.profile`) and facility profiles (`plasticos.facility.profile`).
> It is still a proposal and never a write command. Only the converge v2 mapping table may write to these
> records (ADR-012 amendment 2026-11-13), after whole-run review approval, under merge-not-overwrite,
> with provenance. A reply is written only when its evidence state is admitted `inferred` or `external_claim`.
> `unknown`, `conflicting` and `observed` values are never written. A number is written only in a unit the
> row accepts. A reply whose evidence cannot be fully validated writes nothing and records why.
> **Rejects:** a v1-shaped or malformed reply to a v2 request mutating a profile, and an unmapped
> cartridge field reaching any Odoo record.

> **2026-11-13 correction to the POS-INV-18 amendment above (additive; this file is append-only).**
> A converge result may propose values for the partner and its facility profiles only. It never proposes values for
> a material profile: the cartridge's `material` subject describes a facility's capability (operator decision 2026-11-13,
> ADR-012 amendment 2026-11-13 (d)). A number is written only in its governing unit: the value's stated unit, or else
> the cartridge's declared unit. It must be a unit the field accepts.

> **2026-11-15 amendment to POS-INV-18 (additive; this file is append-only).**
> Authorized by the operator (2026-11-14/15) for the scheduled EIE enrichment sweep (ADR-012 amendment 2026-11-15).
> A sweep result is a proposal like any other converge v2 reply. It is never written before review: each usable result
> becomes one `plasticos.enrichment.run` in `review` and is written only through whole-run approval (`action_inject`),
> under the same mapping table, evidence-state policy, merge-not-overwrite rule and provenance. An unusable result
> becomes a `degraded` run with its reason. A malformed sweep reply ingests nothing. One sweep and entity yield at most one run.
> **Rejects:** a sweep result writing to a partner or facility profile without an approved run, and a sweep reply
> that does not match the contract module (`plasticos_gate/services/gate_sweep.py`) creating any run.

> **2026-11-17 addition (additive; this file is append-only). Operator decision 2026-11-17. Realized by ADR-135.**
>
> ### POS-INV-21 | Soonest Full-Weight Opportunity
>
> Linda's scheduling objective **MUST** be the earliest pickup and delivery, or the earliest export sailing, that both the shipper and the receiver accept for a load meeting its minimum net weight. Shipping sooner **MUST NOT** outrank shipping full weight. Linda **MUST NOT** propose, accept, load or dispatch a truckload or export container below its minimum net weight. She **MUST NOT** offer to waive, or ignore, a light-weight deduction.
>
> - **Present the real calendar, early.** When the shipper's ready date is later than an available delivery slot or booking cutoff, Linda tells the shipper as soon as she knows. She gives the date the full load must be staged by to make it, the date of the next slot or sailing after it, and asks whether they can be full-weight ready in time.
>   - If they can, she books the earlier slot or keeps the booking.
>   - If they cannot, or have not answered by the date she must decide, she books the next available slot or asks for the booking to be rolled.
> - **Export.** A skipped port call or a long wait for the next cutoff is communicated in advance, never after a cutoff has passed, so the shipper can choose to speed up production.
> - **Ready early.** When a load is confirmed ready ahead of its accepted delivery slot or booking, Linda **MUST** ask for an earlier one. A refusal leaves the accepted slot or booking unchanged.
>
> A load that ships sooner frees the shipper's space for the next load and brings payment and margin sooner. Minimums, tolerances and deduction arithmetic stay in the PO, the transaction and the BRS. Waiving a deduction or paying a roll fee is a human commercial decision.
>
> **Rejects:**
> - dispatching a partial load to make an earlier slot;
> - offering to waive a light-weight deduction;
> - silently booking a slot weeks out when the shipper was never told an earlier slot existed;
> - telling a shipper only after the cutoff that the next sailing is a month away;
> - leaving a ready load waiting without asking for an earlier slot or sailing.

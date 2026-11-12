# BRS-EXP-06: Security, exceptions, readiness and acceptance

**Class:** additive design rules; distinct from existing `BRS-POS-*` chapters.
**Primary semantic owner:** existing security owner plus export presentation
**Authority:** previously operator-locked scope is LOCKED; unapproved technical recommendations are DESIGN. This is an unadmitted planning artifact.
**Phases:** P1 = recycler FOB/FAS; P2 = actual international seller; BOTH = shared.
**Runtime and independent acceptance:** NOT_RUN.

## Rules

### BRS-EXP-06-R001: Audience/confidentiality and company isolation

**LOCKED · BOTH · owner: `native Odoo ACLs + Documents/Linda owners`.** Every booking, document link, generated report, outgoing recipient and related stock/order lookup SHALL enforce the exact company and approved audience. Supplier economics, buyer identity, freight economics and sensitive documents SHALL NOT leak across a brokered trade or company boundary; Export SHALL not grant external Documents access.

- **Positive:** Forwarder booking sheet contains authorized load details without exposing hidden supplier buy price.
- **Negative:** A read-only export user can download every native Documents original or a buyer sees supplier invoice.
- **Related existing BRS:** BRS-POS-11-R001..R006.
- **Acceptance:** `AC-EXP-06-001` / NOT_RUN.

### BRS-EXP-06-R002: Unknown and contradictory evidence remains visible

**LOCKED · BOTH · owner: `export projections with source owner decisions`.** Missing, wrong-party, stale, superseded, conflicted or uncertain export evidence SHALL remain UNKNOWN/pending with an attributed exception. Export SHALL NOT use fuzzy linking, optimistic defaults or AI/OCR inferences to declare a validated booking, shipment, compliant document, gate acceptance or regulatory result.

- **Positive:** Carrier and terminal disagree on Cut Off; both originals are retained and action is assigned for verification.
- **Negative:** The newest unauthenticated email silently changes the confirmed booking and makes it green.
- **Related existing BRS:** BRS-POS-01-R011; BRS-POS-03-R006.
- **Acceptance:** `AC-EXP-06-002` / NOT_RUN.

### BRS-EXP-06-R003: Order, shipment, evidence and transaction states remain scoped

**LOCKED · BOTH · owner: `native commercial/state owners; Export read-only projection`.** Purchase/Sale ordered quantity, each physical receipt/dispatch, each booking/terminal milestone, document verification, transaction state, invoicing and financial settlement SHALL remain independent and scoped to the correct child/line. One of four weekly loads delivered SHALL NOT mark the entire four-load PO fulfilled nor a 30-load SO delivered. AI may propose a transition but the existing validated state owner SHALL apply it only if the explicitly required evidence, quantities and authorization permit it.

- **Positive:** A first-week load has a verified gate receipt while three future PO quantities remain open and the 30-load SO remains partially fulfilled.
- **Negative:** One extracted booking or scanned container marks its parent transaction and all sibling loads Delivered/Closed, or invoices all remaining quantities.
- **Related existing BRS:** BRS-EXP-08-R003..R006; BRS-EXP-09-R007; BRS-POS-06.
- **Acceptance:** `AC-EXP-06-003` / NOT_RUN.

### BRS-EXP-06-R004: Minimality and acceptance gate

**DESIGN · BOTH · owner: `product owner/repository implementation owner`.** A future proposed export field, model, menu, QWeb report, cron or automation SHALL carry a source-owner census, a concrete unmet business action and one positive plus one failure acceptance case. Rules are planning requirements until separately admitted and implemented. Each real test SHALL cite its BRS ID, exact repo revision and observed evidence; no unrun scenario may be labeled PASS.

- **Positive:** A future export PR maps each changed file to a rule and shows no duplicate sender/verifier/stock writer under tests.
- **Negative:** A new generic document engine is approved solely because a QWeb template could not find a field.
- **Related existing BRS:** BRS-POS-12-R010,R013.
- **Acceptance:** `AC-EXP-06-004` / NOT_RUN.

### BRS-EXP-06-R005: Safe change and activation boundaries

**LOCKED · BOTH · owner: `operator + live owner of each capability`.** The export BRS pack SHALL not itself install a module, activate mail or cron, create shipment transactions, approve legal filings or change Native-First BRS semantics. Any implementation/cutover requires a bounded separately authorized contract; changes to prior locked decisions require explicit dated supersession, preserving old rules and acceptance trace.

- **Positive:** The BRS pack can be reviewed with all operational services unchanged.
- **Negative:** Publishing a document BRS silently enables Linda email or makes a compliance rule legally operative.
- **Related existing BRS:** BRS-POS-12-R001,R011,R015.
- **Acceptance:** `AC-EXP-06-005` / NOT_RUN.

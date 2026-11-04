# PlasticOS Export v2.7 | Bounded technical architecture closure

**Status:** PRODUCT-ARCHITECTURE SELECTION LOCKED FOR THE WORKING PACK; SOURCE-OWNER ADOPTION AND ENTERPRISE PROOF PENDING. **This is NOT a claim that the proposed methods or models already exist, nor permission to write code or deploy.**

**Scope:** exactly the five closure deliverables requested on 2026-10-28: physical identity/fulfillment; technical schemas and commands; owner adoption/dependencies; migration/Enterprise evidence; and a small ordered implementation handoff. No new product capability, rule ID, queue, original-file store, fulfillment/accounting ledger, architecture authority, or Phase 2 dependency is created.

**Source baseline:** `cryptoxdog/IB-Odoo_19`, `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`; applicable constitutional repository law `INVARIANTS.md` v2.2.0. `Quantum-L9/.github`, `main@3dcdeaae355b6de08562993f705084d7a3714bfd` was inspected for semantic context, but a producer-validated GAR-observer projection, AuthorityResolution, independent EvidenceAssessment, Semantic Integrity Audit and GARReceipt are **not provided**. `GOVERNANCE/ODOO_INVARIANTS_v3.3.0_DRAFT_r1.md` is a working DRAFT, not a replacement for v2.2.0. Before code, rebind target/head and independently validate owner acceptance.

**Reading/precedence:** frozen business intent in `CONVERGENCE/OPERATOR_DESIGN_FREEZE.md`, all 120 unchanged `RULES/BRS-EXP-*.md` and 120 unchanged `ACCEPTANCE/cases.json`, accepted owner BRS/ADRs and current repository constitution control their own domains. This file **supersedes only the tentative technical realization choices** in v2.5 `MODULE_DESIGN/IMPLEMENTATION_READINESS_CONTRACT.md` and v2.6 `INTEROP/CROSS_MODULE_INTEGRATION_CONTRACTS.md`, not their evidence, acceptance tests or source-owner law. Where proposed technical placement conflicts with an actual admitted owner contract, the affected path is BLOCKED for owner reconciliation, never silently backpatched. Private `SOURCES/` and the full ZIP are for internal review only; do not commit them.

## 1. Selected and protected physical identity / fulfillment model

### 1.1 Distinct grains and selected cardinalities

| Identity / grain | Owner | Selected representation and cardinality | Never conflated with |
| --- | --- | --- | --- |
| Native PO/SO line | `purchase.order.line` / `sale.order.line` | One line may have several partial real fulfillments; independently legitimate PO-only and SO-only routes | A container, a terminal acceptance, a truckload or a confirmed booking |
| Native stock execution | Odoo Stock, `stock.move.line` / real `stock.picking` as applicable | Record only actual owned-custody stock moves; one movement can serve an order line partially | A supplier's reported non-stock physical delivery |
| Business execution / transaction | `plasticos.transaction` | Existing one-to-one **transaction-to-load when that relationship is valid**; many transactions may refer to the same actual SO and to source POs | All movement legs; do not widen transaction/load purely to solve SO cardinality |
| Inland movement / truckload | `plasticos.load` under Logistics | A real load is its own execution, with stable real `company_id` independent from a sale; zero, one, or several such real feeder movements can contribute to one ocean ISO journey | An ocean-carrier booking or ISO shipping container; a third-party FAS delivery needs no fictitious company-dispatched load |
| **Physical ISO-container journey** | **Logistics**, not Export | **J1, distinct stable physical subject.** One journey identifies one actual shipping-container movement on its attributable voyage/transport cycle. The same ISO number can be reused in another journey. One journey may have multiple real feeder sources. A single feeder movement may supply more than one journey if physically evidenced. | Booking slot, packaging `container_no`, company trailer, native stock package, sale/purchase line |
| **Journey-to-source association** | **Logistics**, not Export | **J2, exact typed association** from J1 to one real load, native stock execution, or authenticated non-stock movement evidence; many-to-many physical source cardinality is legitimate. A commercial PO alone does NOT constitute physical execution. | Quantitative fulfillment/economic posting; J2 is a provenance edge, not an inventory ledger |
| Ocean reservation | Export E1 `plasticos.export.booking` | One identified carrier reservation, multiple accepted revisions, potentially many reserved equipment slots | SO, PO, truckload or actual vessel departure |
| Accepted carrier revision | Export E2 `plasticos.export.booking.revision` | Append-only, source-attributed acceptance decision; exactly one effective accepted revision pointer per booking, potentially none for candidates | Native original-file version, OCR candidate, mail send state |
| Booking capacity unit | Export E3 `plasticos.export.booking.slot` | One **confirmed** ocean equipment-space unit, never the physical ISO itself; zero or one active J1 per slot; at most one active slot for a J1; one slot can have many cargo links | One source PO, one feeder truck, one cargo link, actual shipped quantity |
| Planned cargo participation | Export E4 `plasticos.export.booking.cargo.link` | A scoped planned part of a slot, tied to exact source line/physical evidence and UoM. Many E4 rows per slot; quantities sum under native owner authority. | Stock reserve, dispatch, shipment receipt, supplier AP or buyer AR |

**Frozen clarification of the earlier E3 proposal:** `booking.slot.load_id` is **removed from the selected target**; it falsely imposes one feeder load per slot. Replace it with a nullable **`journey_id`** reference to the Logistics-owned J1. Transaction/load references are obtained through J2/native records and are not duplicate authoritatively written onto E3. J1 and J2 are owner-local physical *identity and provenance*, not a second movement status machine or stock ledger. Their exact persistence names below are proposed owner-controlled surfaces, NOT existing repository APIs. The Product-level J1/J2 semantic split is locked; an equivalent existing owner-owned representation may replace the table names **only after a witnessed one-to-one semantic mapping and operator signoff before implementation**.

**Irreducibility witness:** Two separate real supplier feeder movements are consolidated into one ISO shipping container with one seal and one ocean booking slot; a FAS supplier may deliver a sealed container without any company-issued `plasticos.load` or native owned-stock movement. `plasticos.load` cannot alone express both cases without inventing dispatch or collapsing source movement history; transaction-line `container_no` also denotes packaging, not proven unique physical ISO equipment. A Logistics-owned physical journey identity plus typed source associations is the smallest distinct required meaning. Do not construct J1 from booking slot count, `purchase.order` count or guessed worksheet name.

### 1.2 Fulfillment source rules (no duplicate ledger)

- **Native-stock route:** native Stock owns physical quantities, moves, receipts, reservations and custody; approved commercial owners own prices, commitments and invoice weights. E4 can reference a real source line and read actual move-line quantity with precision/UoM. E4 never writes a Stock move or claims fulfillment merely because space was reserved.
- **Verified non-stock route (supplier-delivered FAS/dropship/third-party):** the actual supplier/terminal or other responsible party supplies attributable evidence of physical activity. J2 binds that native original/actual physical source and Logistics' authenticated operator acceptance, source party, company and scope. Absence of native Stock is **not an error**, but neither PO approval nor an email claiming `complete` proves truck arrival, terminal gate-in, sailing or completed quantities. Missing proof is `pending/review`, not `0`, not a fake picking, and not a fake truckload.
- **Buyerless route:** a real `company_id`, source PO or owned cargo authority and attributed movement can exist without SO/buyer. The commercial sale can be added later via native Sales without rewriting physical journey history or creating a second trade settlement writer.
- **Quantity/weight:** keep *planned* E4 quantity separate from actual native/accepted physical measured quantity, independently authorized supplier AP weight, buyer AR weight, scale gross/tare/net and VGM. No universal `transaction.final_weight` can become all four. An order-level weight cannot be allocated to multiple containers by division unless its real source warrants it.
- **Terminal/vessel events:** do not infer gate-in from arrival at facility or sailing from carrier booking. Phase 1 exposes only externally/owner-attested actual milestones, with evidence and a distinct local/UTC time precision; absent milestone remains unknown. J1 is not a custom event telemetry engine.
- **Consolidation:** two feeder movements -> one J1 -> one current E3; multiple source lines in E4 consume **one** capacity slot. Five containers from four POs remain five actual J1s (when observed), five E3 capacity units and four distinct POs, never twenty containers.
- **Change:** correcting a sourced physical fact does not overwrite the old source event. A new accepted revision/association supersedes the mistaken one with reason and actor; actual performed freight and native stock remain historically intact. Cross-company source joins and first-by-SO guessing always fail closed.

### 1.3 Selected alternatives and their dispositions

| Option | Disposition | Why |
| --- | --- | --- |
| Treat one Export slot as one `plasticos.load` | REJECTED | Fails two-feeder-to-one-container and legitimate supplier-FAS/no-company-truck scenarios |
| Replace `transaction.load_id` with generic one-to-many | REJECTED | Many transactions may already share one SO/PO; changing transaction meaning is not needed for partial order fulfillment |
| Reuse native stock packages as global ocean container truth | REJECTED AS UNIVERSAL | Some shipments have no company-owned Stock operation; stock packaging and actual ISO journey are different meanings |
| Add Export-owned container/master/fulfillment ledger | REJECTED | Duplicate physical and stock writers; violates fixed owner boundary |
| J1 + J2 under Logistics; E3 references J1 | **SELECTED PRODUCT ARCHITECTURE** | Preserves source truth, supports arbitrary real feeder-to-container cardinality and buyerless delivery without fake load; owner-local schema and runtime acceptance still pending |

## 2. Technical schema freeze for Export; exact owner-local adoption candidates

**Freeze scope:** E1-E4 field names/types, cardinalities, SQL or owner-service guards, and transition rules below are **frozen as the v2.7 selected candidate**, not proof they are installed or fully compatible with Odoo 19 Enterprise. Owners must first adopt affected contracts and validate native ORM/ACL/concurrency on the installed fixture. No code is allowed to infer unknown facts by falling back to partner/name/most-recent. Prefer native Odoo primitives; no new storage service, generic event bus, or Universal Shipping Model.

### E1. Export `plasticos.export.booking` (one carrier reservation)

| Field / Odoo type | Required / writer | Constraint |
| --- | --- | --- |
| `company_id: Many2one(res.company)` | Required, set exactly once by authorized action | Immutable for accepted booking; checked against issuer, slots and all linked sources |
| `issuer_id: Many2one(res.partner)`, `carrier_id: Many2one(res.partner)` | Source-attributed; issuer required at acceptance; carrier may be unknown | Do not equate forwarder and carrier; current trading partner context does not choose either |
| `carrier_booking_no: Char` | Nullable for request candidate; required at acceptance | Not globally unique; same-number revisions remain within same reservation after exact proof |
| `source_occurrence_key: Char` | Required at acceptance; exact booking-cycle identity accepted from evidence | Unique **`(company_id, issuer_id, source_occurrence_key)`** only for fully identified bookings; never derive solely from booking number or guessed voyage |
| `current_revision_id: Many2one(plasticos.export.booking.revision)` | Nullable, read-only except authorized accept command | Exactly one effective accepted revision pointer; every referenced revision belongs to same booking/company |
| `slot_ids: One2many(plasticos.export.booking.slot)` | Derived by booking | Cannot auto-create confirmed capacity from requested or OCR-only counts |
| `display_state: computed Selection` | Never an independent state writer | `candidate/confirmed/held/cancelled`, projected from accepted revision and exception status; old versions retained |

Booking number, line, POL/POD, cargo cutoff and ERD are user-visible source-backed projections from the **current accepted E2**, never separately writable E1 facts. A source that ambiguously conflates carrier-issued and forwarder-issued references stays review-only. An import of old sales orders never creates bookings.

### E2. Export `plasticos.export.booking.revision` (immutable accepted snapshot)

| Field / Odoo type | Required / writer | Constraint |
| --- | --- | --- |
| `booking_id: Many2one(plasticos.export.booking)`, `company_id: related Many2one` | Required | Company matches E1 |
| `source_original_id: Many2one(documents.document)` and `source_message_id: Many2one(mail.message)` | At least one attributable native source; acceptance requires exact original/message and provenance | Neither is a new binary/version store; no OCR text is accepted without source authority |
| `source_revision_key: Char` | Required | Unique `(booking_id, source_revision_key)`; replay same source is no-op; same booking number does not collapse distinct revisions |
| `observed_at: Datetime`, `source_issued_at: Datetime` | Observed timestamp required, issued timestamp nullable | Never infer source-issued from filename or message received date |
| `decision: Selection(candidate, accepted, rejected)` | Controlled by authorized review | `candidate -> accepted|rejected`, no reversal; accepted row snapshot immutable even when no longer effective |
| `supersedes_revision_id: Many2one(self)`; `accepted_by: Many2one(res.users)`, `accepted_at: Datetime`, `acceptance_basis: Text` | Accepted requires actor/time/reason and approved predecessor relation | Previous accepted row remains accepted; E1 pointer changes atomically |
| `carrier_booking_no: Char`, `steamship_line_id: Many2one(res.partner)`, `pol_text: Char`, `pod_text: Char` | Field-level sourced values, unknown stays NULL | No terminal/address is silently promoted to a port or discharge port |
| `cargo_cutoff_local: Char`, `cargo_cutoff_tz: Char`, `cargo_cutoff_utc: Datetime`, `cargo_cutoff_precision: Selection(date,datetime,unknown)` | Source-local text required when supplied; normalized UTC optional | UTC only if source zone/precision disambiguated, including DST; unknown never guessed |
| `erd_local: Char`, `erd_tz: Char`, `erd_utc: Datetime`, `erd_precision: Selection(date,datetime,unknown)` | Independent from cargo cutoff | Preserve terminal-specific differing ERDs in structured source terms; ambiguous effective ERD stays NULL |
| `equipment_counts: Json`, `additional_terms: Json`, `affected_scope: Json` | Frozen bounded schemas below, subject to installed `fields.Json` proof | Confirmed/requested counts separated; no arbitrary field as status or source permission |

**Json contracts:** `equipment_counts` is keyed by actual allowed class (`20STD`, `40STD`, `40HC`, `45STD`, `45HC`) with `{requested: integer|null, confirmed: integer|null}`; NULL means unconfirmed, explicit `0` means source-confirmed zero. `additional_terms` holds typed raw and normalized location, terminal-specific ERD, document/VGM cutoff, vessel/voyage and ETD/ETA **with source original locator, precision and field-level status**; never a substitute for native accounting/stock. `affected_scope` is a bounded list of exact Export booking/slot identities or a required `review_scope_unknown` marker, never a global wildcard. All JSON is validated by Export owner on create/accept and immutable after acceptance. **Installed Odoo 19 Json support is a pre-code check**; if unavailable, choose an equivalent owner-approved relational representation before code freeze, not a dynamic fallback.

### E3. Export `plasticos.export.booking.slot` (one confirmed capacity unit)

| Field / Odoo type | Required / writer | Constraint |
| --- | --- | --- |
| `booking_id: Many2one(E1)`, `company_id: related Many2one` | Required | Company exact |
| `slot_key: Char` | Required, stable for lifetime, e.g. ordinal plus source capacity allocation identity | Unique `(booking_id, slot_key)`; after roll never renumber/delete consumed historical capacity |
| `equipment_class: Selection(20STD,40STD,40HC,45STD,45HC)` | Required for confirmed slot | A substitute needs explicit carrier/owner permission and source proof |
| `created_from_revision_id: Many2one(E2)` | Required | Never manufactured from unconfirmed requested quantity |
| **`journey_id: Many2one(plasticos.iso.journey)`** | Nullable; physical owner is Logistics J1 | At most one active journey per E3; one active E3 per J1 and current booking cycle; **no `load_id` field on E3** |
| `allocation_state: computed Selection(available,committed,held,historical)` | Derived from E4, current E2 and exceptions | Capacity/physical state are separate; `held` is not cancellation of performed shipment |
| `journey_binding_state: Selection(unbound,active,historical)` | Only owner-checked binding command mutates | Under active binding, DB-enforced **partial unique index on `journey_id` where `journey_binding_state='active'`** (or proven equivalent); historical bound slots retain source provenance, never count as active physical use |
| `hold_reason: Char`, `hold_revision_id: Many2one(E2)` | Only explicit scoped revision exception | Downsize below committed yields visible overcapacity, not deletion or auto-reallocation |

**Concurrency rule:** On any capacity-affecting mutation, lock the authoritative E1 booking row then affected E3 rows in stable ID order in the same Odoo DB transaction, re-read the accepted E2 and current allocations, and commit or reject atomically. ORM constraints alone are not sufficient. `confirmed_by_class` derives from accepted E2, **not** number of historical slot rows. For each class define `occupied = distinct current E3 slots with committed E4`, `held_only = distinct held E3 slots not already in occupied`, `capacity_used_or_held = occupied + held_only`; then `available = max(0, confirmed - capacity_used_or_held)` and `overcommitted = max(0, capacity_used_or_held - confirmed)`. A held-committed slot appears in occupied **once**, not again in held; counts are per distinct E3 and current revision, not E4 or PO. No slot exists as confirmed capacity before real carrier confirmation.

### E4. Export `plasticos.export.booking.cargo.link` (planned, exact-source allocation)

| Field / Odoo type | Required / writer | Constraint |
| --- | --- | --- |
| `slot_id: Many2one(E3)`, `company_id: related Many2one`, `allocation_key: Char` | Required | Unique `(company_id, allocation_key)` for exactly-once retry; immutable source cycle token |
| `purchase_line_id: Many2one(purchase.order.line)`, `sale_line_id: Many2one(sale.order.line)` | Optional but exact | One origin-supply portion and at most one associated actual sale destination; can be PO-only or buyerless |
| `stock_move_line_id: Many2one(stock.move.line)`, `source_load_id: Many2one(plasticos.load)` | Nullable, references only exact real records | Neither optional reference invents actual fulfillment; feeder load can appear in several physical journeys only with evidence |
| `physical_source_kind: Selection(native_stock,logistics_load,verified_nonstock,pending)` | Required, controlled origin classification | `pending` links reserve **no actual-shipped quantity**; nonstock requires exact provenance and owner acceptance |
| `physical_source_ref: Char`, `original_attachment_id: Many2one(ir.attachment)` | For nonstock actual-evidence path when accepted | Evidence/subject typed and scoped by J2 and Documents; no extra source file or verification writer |
| `planned_quantity_known: Boolean`, `planned_quantity: Float`, `uom_id: Many2one(uom.uom)` | Quantity/UoM required if known, otherwise known=false | Float zero is NOT used as unknown; native UoM/conversion policy is checked before commitment |
| `source_revision_key: Char`, `state: Selection(proposed,committed,held,released)`, `replaces_link_id: Many2one(self)` | Revision + controlled transition; prior link retained | One link is not economic settlement; source material change creates successor with actor/reason rather than silent replacement |

**Required source validation:** A `committed` E4 must name an eligible commercial or custody source and a deterministic owner-checked quantity basis; a physical actual cannot be asserted until a real native move or J2 verified source exists. Same original source quantity cannot be allocated across several active links beyond the eligible source-owner quantity at the same time. A stock reservation or sale line alone does not prove actual terminal acceptance. Multiple E4 links on one E3 occupy one booking slot. Never accept a blanket `res_model/res_id` string as an authorization grant; typed identity must be verified at source owner.

### J1/J2 proposed owner-local persistent representation under Logistics

**Owner-adoption gate remains hard.** Source code currently offers `plasticos.load`, its `sale_order_id`-derived company and optional seal, and `plasticos.transaction.line.container_no` whose packaging semantics are ambiguous. It does **not** establish a physical ISO journey owner. The nominated smallest new owner-local representation is:

| Model (PROPOSED, not installed) | Field shape / rule |
| --- | --- |
| `plasticos.iso.journey` (J1) | `company_id: Many2one(res.company)` required; `equipment_class: Char` sourced/validated; `iso_number: Char` nullable until actual proof; `seal_number: Char` nullable; `identity_evidence_attachment_id: Many2one(ir.attachment)` optional for candidate, but required for verified state unless an independently attributable operator physical-observation record exists; `identity_attested_by: Many2one(res.users)` and `identity_attested_at: Datetime` when operator-attested; `source_cycle_key: Char` non-empty for accepted physical journey and unique within company; `source_ids: One2many(J2)`; `identity_state: Selection(candidate,attributed,verified)` controlled by actual Logistics validation. Neither a booking number nor one unverified operator assertion alone proves ISO/seal or gate-in. ISO number alone is never unique across journeys. No `booking_id`, customer, sale, AP/AR, rate or document-verified status is owned here. |
| `plasticos.iso.journey.source` (J2) | `journey_id: Many2one(J1)` required; `source_kind: Selection(load,stock_move_line,nonstock_evidence)`; exactly one `load_id: Many2one(plasticos.load)` OR `stock_move_line_id: Many2one(stock.move.line)` OR `evidence_attachment_id: Many2one(ir.attachment)`; `source_party_id: Many2one(res.partner)` and `company_id` required/checked; `source_reference: Char` and `acceptance_basis: Text` where third-party; `state: Selection(candidate,accepted,rejected)`; accepted association immutable; duplicate `(journey,kind,subject,source_scope)` fails by owner-checked uniqueness. No independently writable shipped/received/billable quantity or business document `verified` flag. |

**Dependency-safe proof:** Logistics already depends on `stock`, `purchase`, `mail` and transaction; J1/J2 may safely reference **`stock.move.line`, `ir.attachment`, `res.partner` and `plasticos.load`**. They **cannot** import or add a direct FK to `plasticos.document`, `documents.document`, E1/E3 or Linda's downstream Export model: `plasticos_documents` depends on Logistics; `plasticos_documents_native` depends on Documents and Logistics. Documents can consume Logistics identity from its downstream addon. Native `ir.attachment` is a pointer to an original, NOT independent PlasticOS verification. Terminal and vessel actual events remain source-observed facts with attributable evidence; this v2.7 contract does not add a milestone/event store. If installed native Odoo provides a fully equivalent persistent J1/J2 structure, prove it before changing these nominated names and document the one-to-one mapping; do not create duplicate owners.

### 2.1 Hard validation requirements, irrespective of field layout

1. All `company_id` references and FK targets must agree, with actual Odoo access rules (`check_company` where supported) and independent explicit code/SQL protection; `sudo` cannot turn a cross-company link legal.
2. Revisions, accepted cargo links and J2 accepted physical associations are immutable except a bounded append/supersession operation. Any delete/cascade that loses accepted source evidence is forbidden.
3. Existing domestic Loads, Sales/Purchase/Stock, mail and Documents continue to function without an Export booking or Export addon installed.
4. At most one active slot per J1, while J2 supports multiple legitimate real feeder sources per J1. Historical booking reassignments retain their source/actor/time.
5. Effective date/time requires source precision/zone; a date-only ERD must never be normalized to an invented timestamp. Source-issued and observed timestamps remain distinct.
6. Odoo ACLs and record rules must protect form, search, counts, SQL-backed view, QWeb/CSV/XLSX and native linked documents without a `sudo` read leak.
7. Run genuine Odoo 19 Enterprise registry, schema, installed extension and concurrency probes before asserting these are runnable field definitions.

## 3. Frozen logical command signatures and state transitions

**Signatures are exact *target interface contracts*, NOT callable methods in the inspected Staging checkout.** They are intentionally small, Odoo-record oriented. The first arg `self` is the governing model/recordset; identity/permissions derive from the authenticated `env.user` and native ACL, never a caller-supplied actor ID. Every mutation enforces company scope, role, idempotency, expected revision and source provenance in the owner, not only in UI. The `operation_key` is an exact caller-generated retry identity scoped by company + subject + purpose; a successful replay returns the same resulting record, not a duplicate. Outcome domain is local to these commands: `applied`, `already_applied`, `stale`, `blocked`, `ambiguous`, `not_available` with an exact reason and existing record ID where applicable. These are **not** new global L9 outcome values.

### 3.1 Export-owned commands, selected signatures

```python
# This is a design-only interface declaration. None of these methods is asserted to exist.
# E1 booking recordset; creates/accepts sourced business facts, not Documents verification.
record_booking_revision_candidate(
    self, source_original_id: int | None, source_message_id: int | None,
    source_revision_key: str, extracted_terms: dict, operation_key: str,
) -> dict

action_accept_booking_revision(
    self, revision_id: int, expected_current_revision_id: int | None,
    operation_key: str, acceptance_reason: str,
) -> dict

# E3 slot recordset; never posts stock or economic effects.
action_commit_cargo(
    self, source_refs: dict, planned_quantity: float | None,
    uom_id: int | None, expected_booking_revision_id: int,
    operation_key: str,
) -> dict

action_release_cargo(
    self, cargo_link_id: int, expected_booking_revision_id: int,
    operation_key: str, reason: str,
) -> dict

action_bind_journey(
    self, journey_id: int, expected_booking_revision_id: int,
    operation_key: str, source_basis: str,
) -> dict

# E1 wrapper; releases an authorized request TO Linda, never sends via Export.
action_request_booking_notice(
    self, purpose: str, audience_partner_id: int,
    recipient_email: str, expected_current_revision_id: int,
    operation_key: str, audience_basis: str,
) -> dict
```

`source_refs` has **only** these permitted keys: `purchase_line_id?`, `sale_line_id?`, `stock_move_line_id?`, `source_load_id?`, `physical_source_kind`, `physical_source_ref?`, `original_attachment_id?`, `source_revision_key`. A valid commitment must be anchored to an eligible real native line, custody, or verified non-stock physical source; no passing random record IDs or company defaults. `extracted_terms` must be parsed into the E2 frozen typed snapshot and its sourced field-level metadata; it cannot contain unapproved actions/ACLs. `source_basis` records proof for a real J1 binding; it is not a business status writer.

**Atomic acceptance:** `action_accept_booking_revision` performs source identity/role check, expected-current compare-and-swap, immutable E2 acceptance, capacity reassessment, creation of additional stable slots if carrier confirms more, precise hold/overcommit for reductions, E1 effective-pointer advance, and invalidation of **only affected pending** owner obligations in one DB transaction. It NEVER auto-cancels fulfilled freight or sent mail. If full distributed change is impossible in one transaction, commit only locally valid E1/E2/E3 changes and set affected external obligations to owner-side revalidation before their next release. No external send occurs in the acceptance transaction.

### 3.2 Required source-owner command contracts, selected signatures for owner adoption

```python
# Logistics/Transaction owner. Must inspect source native and adopt before implementation.
action_bind_exact_transaction_load(
    self, transaction_id: int, load_id: int,
    movement_authorization: dict, operation_key: str,
) -> dict

# Logistics J1 owner; MUST establish real company/source evidence, not create from a slot.
action_register_iso_journey(
    self, company_id: int, source_cycle_key: str,
    equipment_class: str, identity_attachment_id: int | None,
    iso_number: str | None, seal_number: str | None,
    operation_key: str,
) -> dict

# Logistics J2 owner; source_kind is load, stock_move_line, or nonstock_evidence.
action_bind_journey_source(
    self, journey_id: int, source_kind: str,
    source_id: int, source_party_id: int,
    evidence_attachment_id: int | None,
    operation_key: str, acceptance_basis: str,
) -> dict

# Source-owner release gate. Called on ALL actual physical state/packet release paths.
assert_can_release_physical_operation(
    self, load_id: int, operation_kind: str,
    expected_context_token: str | None,
) -> dict

# Documents owner. Scoped verification query; not the existing invoice/close-only API.
get_scoped_evidence_verdict(
    self, company_id: int, subject_kind: str, subject_id: int,
    obligation_kind: str, source_revision_key: str,
) -> dict

# Linda owner. Export supplies authenticated booking-source key and accepted revision;
# a downstream Export extension must revalidate source/currentness at SEND boundary.
request_booking_correspondence(
    self, booking_id: int, accepted_revision_id: int,
    purpose: str, audience_partner_id: int, recipient_email: str,
    attachment_original_ids: list[int],
    source_payload_fingerprint: str, operation_key: str,
) -> dict
```

**Ownership of method implementation:** The exact method names are *proposed frozen signatures for owner review*, and must be either adopted verbatim by their source owner or rejected with an exact equivalent that preserves semantic shape and tests **before coding/consumer binding**. Do not claim they exist. `action_bind_exact_transaction_load` must NOT be called as an Export workaround for missing association. `assert_can_release_physical_operation` belongs to Logistics and must be applied at actual transition/packet/mail send seams; Export may provide current constraint evaluation through a downstream `_inherit` implementation only if audited and accepted. Logistics must not import `plasticos_export`, `plasticos_documents` or Enterprise native bridge. The source-specific validation of Linda's booking requests runs in the downstream Export addon at the owner-defined central Linda hook, while the actual queue/sender/audit remains Linda. No unguarded string-based model lookup or user-provided fingerprint can certify a booking current.

**Linda storage migration prerequisite:** the current `plasticos.logistics.request` has only `po_issue`, `so_issue`, `po_cancel`, `so_cancel` and a SQL `CHECK` requiring exactly one PO or SO. Logistics must first adopt and migrate a legal `export_booking` subject kind and `booking_issue/booking_amendment/booking_cancel` purpose while retaining existing PO/SO rows and their uniqueness. A `selection_add` in Export alone cannot satisfy the CHECK. A source-owned cycle/recipient/purpose/revision idempotency constraint must cover booking requests; the downstream Export extension must verify booking source, current E2, audience and attached originals on native send. Existing `off/shadow/live`, `unknown` and cancellation ordering are not relaxed. Supplier-arranged FAS without company drayage does not generate a carrier Work Order.

**Documents storage migration prerequisite:** `plasticos_documents` owns one current scoped business verification and exact typed original-to-obligation links. Native `plasticos_documents_native.action_verify` must delegate or cease being an independent writer; partner-recency `_auto_link_partner` cannot become accepted evidence. The current compliance service only has `invoice` and `close` purpose flags: `get_scoped_evidence_verdict` requires a separately owner-adopted export operation scope and verified Enterprise bridge. Export cannot call an imaginary `purpose='export'` on the old API. Logistics J1/J2 references `ir.attachment` only and does NOT cross-import Documents.

### 3.3 State transition / effect matrix

| Subject | Allowed changes | Actor/owner effect | Forbidden transition or inference |
| --- | --- | --- | --- |
| E1 booking | `candidate -> confirmed` only after E2 acceptance; `confirmed -> confirmed` on accepted amendment; `confirmed -> held` on unresolved material conflict; `confirmed -> cancelled` on proven source cancellation; `held -> confirmed` with attributed resolution | Export moves effective E2 pointer and scoped capacity/holds only | `candidate -> confirmed` from OCR alone; roll that deletes old evidence; `cancelled -> confirmed` without proven new authorized source cycle |
| E2 revision | `candidate -> accepted | rejected`; past `accepted` remains historically accepted, currentness changes via E1 pointer | Export operator authorized acceptance; immutable accepted snapshot | In-place rewrite of accepted fields; inferred source issue time; latest email auto-accept |
| E3 slot | `available -> committed`; `committed -> committed` when adding a second legitimate E4 line to the SAME occupied slot; `available/committed -> held` on precise source exception; `committed -> historical` upon authorized reallocation/completion; `held -> available/committed` only after current-source recheck | Export capacity commitment only; adding cargo to an already occupied slot does not consume another slot | Creating requested/unconfirmed slots, deletion on capacity cut, treating `historical` as physical cancellation |
| E4 cargo | `proposed -> committed|held`; `committed -> released` on authorized release, or `held` on stale authority; corrections create superseding E4 | Export planned quantities only | Inventory posting, duplicate source commitment, silently replacing line/quantity or treating E4 as shipped |
| J1 physical identity | `candidate -> attributed -> verified` only with actual identity and source-backed owner acceptance; later correction is source-attributed successor | Logistics owns identity and exact ISO/seal; actual milestones read from real evidence separately | Equating J1 existence with physical gate-in, sailing, stock receipt or buyer settlement |
| J2 provenance | `candidate -> accepted|rejected`; accepted source association immutable; supersession separately attributed | Logistics validates real source, company and actual physical evidence | Commercial PO alone accepted as proof of physical delivery; arbitrary same-partner matching |
| Native SO/PO/Stock | Existing source-owned transitions only | Native Odoo source owner | Export direct confirm/reserve/validate/invoice/post |
| Documents | Candidate intake -> source-owner verified obligation or explicitly pending/rejected/revoked | Documents verifier, native original untouched | Native and PlasticOS independently verifying same obligation; file upload = compliance |
| Logistics load | Only existing approved freight/dispatch transitions, subject to applicable current Export guard if linked | Logistics owns dispatch/physical state and packet | Export direct `_transition`, fabricated load for supplier delivery, domestic load blocked for lacking booking |
| Linda intent | `blocked/shadow/queued/sent/exception/unknown/canceled` per owner current lifecycle | Linda/native Mail only; exact per-party source cycle | queued = sent; resend unknown automatically; Export mail or duplicate PO issue |

**Effect frontier:** E1/E2/E3/E4 DB mutations do not automatically create physical movement, email, native stock, invoices, customs filings or terminal milestone. A booking roll only marks a relevant Logistics/Linda operation stale/held until its owner reevaluates; an already sent email or recorded physical event remains as history. No cross-addon distributed rollback assumption is permitted.

## 4. Source-owner adoption, addon DAG and dependency matrix

The table below is **review/adoption work**, not a claim that source owners accepted the proposed storage or method names. The freeze protects Export product meanings while preserving owner authority. A source owner adopts a contract only through its effective BRS/ADR, exact code/manifest shape and current revision-bound positive + negative proofs. An operator's approval of this working-pack design is not a Git merge, Odoo migration or independent Enterprise confirmation.

| Contract / gate | Source owner and concrete current place | Required decision to adopt | Dependencies / implementation seam | Evidence to close; status |
| --- | --- | --- | --- | --- |
| `EXP-IC-01` / `GAP-01` | Native Purchase/Sales/Stock; Transaction `models/transaction.py` | Stable exact PO/SO line, actual native move/quantity ownership, legitimate no-stock physical evidence path; no double-fulfillment | J2 and E4 consume real source identity; no native order/stock write by Export | Two partial PO/SO and PO-only/owned-cargo negative; **NOT_ADOPTED / NOT_RUN** |
| `EXP-IC-02` / `GAP-01/02` | Logistics `models/load.py`, `models/transaction_inherit.py`, actual Stock where used | Explicit stored authorized company on real load; remove `tx_by_sale.setdefault(first)` association; retain valid `transaction.load_id` one-to-one; buyerless movement-specific eligibility; accept J1/J2 as physical ISO journey + source | No direct Logistics dependency on Export/Documents; uses existing native dependencies; deterministic migration | Two feeders->one ISO, supplier-FAS no fake load, ISO reuse, old links preserved; **NOT_ADOPTED / NOT_RUN** |
| `EXP-IC-03` / `GAP-05` | `plasticos_export` candidate E1-E4 | Accept selected E1-E4 fields, E3 `journey_id`, source-line capacity CAS, immutable revision and allocation identities | Depends Logistics J1/J2, exact source lines, Documents native source as applicable | Concurrent final slot, mixed source UoM, 5 slots/4 POs, capacity 5->4; **PRODUCT SELECTED / NOT IMPLEMENTED** |
| `EXP-IC-04` / `GAP-03` | `plasticos_documents/models/document.py`, `models/compliance_service.py`; `plasticos_documents_native/models/document_native.py` | One authoritative `plasticos.document` scoped verifier, typed many-evidence links, exact original; native bridge only delegates; no partner-recency accepted auto-link; export-purpose verdict under Documents | Existing native Enterprise `documents` + `documents_account`; downstream of Logistics; J1/J2 **cannot** depend on these | One original/two obligations, 4-week same-partner conflict, expired/revoked/unauthorized; **NOT_ADOPTED / NOT_RUN** |
| `EXP-IC-05` / `GAP-01/02/04` | Logistics `models/load.py`, freight context, packet/transition methods | One mandatory source-owned `assert_can_release_physical_operation` check, installed downstream Export extension covering all applicable dispatch/packet/state paths; no domestic regression | `Logistics -> Transaction`, never reverse import of Export; verify actual Odoo `_inherit` path and central checks | Same-booking roll with one stale carrier packet, direct/cron/wizard routes, domestic/FAS unaffected; **NOT_ADOPTED / NOT_RUN** |
| `EXP-IC-06` / `GAP-04` | Logistics Linda `models/linda_request.py`, `models/linda_response.py`, native Mail | Source-kind/SQL migration for booking issue/amend/cancel, exact revision and audience idempotency; downstream Export binding validation at send boundary; one queue | Existing Linda has PO/SO-only purposes and CHECK; no fake PO/SO or Export sender; native Mail owns transport | PO issued before booking, unknown send, queued stale revision, carrier redaction; **NOT_ADOPTED / NOT_RUN** |
| `EXP-IC-07` / `GAP-05/06` | Export views/reports; native Odoo reporting and actual owner ACL | Six distinct grains, permission-safe same-filter drilldowns, exact source as-of/current revision, unknown vs zero | No new reporting engine; verify QWeb, list/pivot/spreadsheet/CSV/XLSX on installed edition | 5 containers x 4 POs count 5, restricted multi-company report blocked, six drilldowns; **NOT_ADOPTED / NOT_RUN** |
| `GAP-07` (parallel governance) | Odoo repo constitutional/invariant owner | Explicit eventual v3.3 DRAFT admission/supersession only if approved | Working draft can constrain proposals when nonconflicting; v2.2.0 remains active | SHA-bound constitutional adoption record; **DRAFT / NOT_ADMITTED** |

**Candidate addon dependency graph, to be verified against the exact installed manifests:**

```text
plasticos_export
  -> plasticos_documents_native -> plasticos_documents
                                   -> plasticos_logistics -> plasticos_transaction
  -> plasticos_logistics (J1/J2, Linda owner-provided and load release seams)
  -> native sale_management / purchase / stock / mail / documents / documents_account

plasticos_transaction : must NOT depend on plasticos_export
plasticos_logistics   : must NOT depend on plasticos_export or plasticos_documents
plasticos_documents   : already downstream of plasticos_logistics; must NOT depend on plasticos_export
plasticos_documents_native : downstream bridge; must NOT become an independent verifier
```

The actual `depends` list must contain only actually imported or referenced addon models; transitive declarations must be verified in registry and with the repo DAG checker at the pinned target. New J1/J2 models live **inside Logistics**, not a new physical app. The source-kind support in Linda lives **inside Logistics**; the downstream Export extension supplies booking currentness validation and may add Export FKs to its subclass, but must not become an outbound writer. Both changes are subject to the current source-owner accepted architecture. Native `ir.attachment` and `mail.message` are available to Logistics by its existing base/mail dependencies, but installed method behavior is still unproven.

**Adoption evidence contract (each owner):** Owner-effective BRS/ADR exact ID and SHA; approved interface shape/migrations; exposed source method or documented equivalent; Odoo 19 Enterprise fixture details and exact module versions; positive **and** negative cases; cross-company ACL; replay/concurrency where material; no incompatible source-owner dependency; recorded `ADOPTED` only when the owner actually merges/accepts. Until then, keep `NOT_ADOPTED` instead of inventing authority.

## 5. Migration, upgrade, replay, rollback, Enterprise proof

### 5.1 Owner-scoped migration plan; **NOT_RUN**

| Order | Owner / migration concern | Deterministic transform | Exception/rollback proof |
| --- | --- | --- | --- |
| M0 | Release operator / exact target baseline | Independently capture immutable current Staging SHA, installed Odoo 19 CE+EE addon list/version, migration-free DB snapshot, required ACL/user profiles and quarantined sanitized source fixture IDs. Freeze pre-upgrade row counts and referenced IDs. | Restore tested copy; do not touch production or send mail. A source SHA mismatch stops migration design reuse. |
| M1 | Logistics company ownership | Backfill existing `plasticos.load.company_id` from a uniquely attributable current native SO or other authorized exact PO/stock/movement source; make company a stable stored validated reference, not a solely SO-related field. | A load with conflicting company sources, no source, or historical buyerless ambiguity is an exception record, not silently assigned `env.company` or deleted. All old ID/counts preserved. |
| M2 | Logistics/Transaction exact load links | Preserve existing `transaction.load_id`/`load.id` when unique and valid; disable first-by-SO auto-bind; reject a competing transaction to same load; reconcile old mismatched links to a recorded exception queue. | Deterministic link inventory before/after; no new fake transaction; no first-by-SO rebinding; load one-to-one still holds for the paired cases. |
| M3 | Logistics J1/J2 physical | Create J1 **only from uniquely attributable actual ISO/evidence**; create J2 only for proven physical sources, allow two feeders or non-stock FAS; preserve old packaging `transaction.line.container_no` and load/trailer numbers unchanged. | Legacy `container_no` is NOT auto-imported as ISO; ambiguous seal/container/route is review; repeated ISO across voyages does not merge journeys. No capacity-driven J1. |
| M4 | Documents / native bridge | Establish original-to-obligation exact typed association and one PlasticOS verified writer; map native bridge legacy flags only where current same-scope verified provenance can be proven, otherwise mark review. | No binary copy, no lost original/alias/access rights; no newest-partner linking; a single verified original does not implicitly verify all obligations. |
| M5 | Linda mail obligation | Preserve existing PO/SO request identities, statuses and `mail_id`, map source kind in place with new valid SQL constraints/indexes; add source-specific booking cycle support with rollout default `off`. | Old queued/unknown mail remains not sent/retried; database CHECK accepts legitimate old rows; no orphaned request or duplicate issue on replay. |
| M6 | Export clean install/backfill | Install E1-E4 with no inferred booking/slot/link. Import booking originals as review candidates, exact source-key match, authorized E2 acceptance, confirmed-only slot creation and no external effects. | Replay old PDF and same-number amendment creates no duplicate; requests without proven source identity remain held; transaction unchanged. |
| M7 | Cross-owner recalculation and recovery | Recompute only affected E1/E3/E4 projections, Logistics export gate, Documents verdict and Linda queued status when a source revision changes. Preserve old accepted snapshots and any physically performed event. | Source rewind/rollback: clean DB restore in isolated fixture before effects; after irreversible native/mail physical effects use forward correction and explicit exception, never retroactive deletion. |

**Safeguards:** Migration scripts must be idempotent, trace old ID -> retained/new ID with reversible decisions, and report all *ambiguous, orphan, cross-company, reused-ISO, duplicate-source and legacy-document* exceptions by exact source. No default conversion of unknown to zero. No auto send, stock validation, financial posting, document verification, historical container invention, carrier API or government filing is allowed. Run in a disposable snapshot with manually verified quarantine of private original files. Owner module handles its own migration, never Export bulk-updates upstream data.

### 5.2 Enterprise reality checklist; all **NOT_RUN**

| Proof | Installed source / expected observations | Negative required |
| --- | --- | --- |
| EE-01 registry | Clean Odoo 19 Enterprise with `documents`, `documents_account`, source owner addons and final acyclic Export manifest; reflect real field/model registry, XML IDs and `fields.Json` on that exact build. | Missing addon/field/version cannot be represented as green Community-only smoke. |
| EE-02 upgrade | Existing-data snapshot upgrades in M1-M7 order, preserves native SO/PO/Stock/Load/Transaction/Mail/Attachments and all previously valid ID/ACL references. | Ambiguous links stop affected operation, not reassigned or lost. Dry-run reversal/recovery evidence exists. |
| EE-03 concurrency | Two real DB transactions race to commit the last confirmed E3; CAS and row lock protect E1/E3 and physical binding. | Both cannot commit; stale accepted-revision token cannot change capacity. |
| EE-04 physical | Two feeder movements -> one J1 and E3; same source leg -> two J1 only with real evidence; FAS with no company truck or native owned-stock move; reuse same ISO number for a later journey. | No 2-for-1 capacity, fake load, fake picking or conflation of packaging `container_no`. |
| EE-05 documents | Native original bytes/version, same original in two typed verified obligations, scoped expiry/override/supersession and rights. | Native independent verify and partner-recency linking cannot satisfy a business gate; OCR cannot verify. |
| EE-06 logistics | `action_dispatch`, internal `_transition`, carrier packet and direct/cron/wizard paths use owner-approved current-constraint check; repeated booking roll affects only linked pending movements. | Unlinked domestic load not blocked; third-party supplier-delivered FAS no fictitious drayage/packet; old confirmed rate not silently re-awarded. |
| EE-07 Linda | PO/SO issued under existing rules and retained SQL; booking notice amendment/cancel by purpose + current E2 + audience; QWeb/attachments and native Mail are version-safe. | Unknown provider outcome is not resent, queued stale mail does not escape, carrier recipient sees no supplier price, installer sends none. |
| EE-08 reporting | Six native-backed populations, same-filter drilldown and print/export from same authorized source scope; current/as-of explicit. | 5 J1, 4 POs, 5 slots counts do not fan out; cross-company/partner visible data never leaks in summary, CSV/XLSX/PDF. |
| EE-09 operational | Manual evidence path works without scanner/mobile/AI/FindTEU/AESDirect; normal domestic MVP remains operational with Export absent/inactive. | No hidden activation, no speculative terminal events, no external provider calls. |

**Evidence fields required in each runtime witness:** exact Odoo build/edition; installed module/version graph; DB fixture identity/digest without private user content; source target SHA and PR head, owner BRS/ADR coordinates; named positive and negative assertions with observed results; independent review/QA provenance; statuses `PASS`, `FAIL`, `NOT_RUN`, or `BLOCKED`, not fabricated all-green. An install test is not proof of correct physical semantics, and archive checksums are not test execution.

### 5.3 Minimum falsification set before source schema lock

1. **Two sources, one ocean container:** A and B are real separately documented feeder movements, same company and one physically identified sealed ISO container. One J1 / one E3 / two accepted J2 (plus distinct E4 cargo), no double capacity, physical quantity read from real owner. **Fails** `E3.load_id` single FK.
2. **Non-stock supplier-FAS:** Actual supplier delivers to terminal with a real PO and documentary evidence but no company truck, company-owned Stock move or buyer. J1 may be identified from actual evidence; J2 can represent nonstock proof; no fictitious load/stock/SO, no terminal acceptance without terminal-owned confirmation. **Fails** a universal `plasticos.load` or `stock.move` prerequisite.
3. **Same-number 5 -> 4:** An effective booking revision reduces five 40HC confirmed slots to four while five are already committed; one packet sent, one queued, one drayage load dispatched. Preserve original sources, past E2, J1/J2, sent evidence, dispatched history. Show one precise overcommit, block only relevant pending sending/release, and require owner reevaluation. **Fails** slot deletion, blanket cancel and duplicate send.
4. **No buyer SO and source mismatch:** Buyerless owned/PO cargo is permitted when exact company is known; same-named PO from another company cannot bind. **Fails** company derived only from sale or `env.company` fallback.
5. **Repeat physical ISO number:** The same actual container number is used on a later different source cycle. Two J1 identities must persist; a one-number global SQL UNIQUE or merging by string fails.
6. **Two simultaneous last-slot allocations:** Both users see one remaining slot; at most one commits; winner and loser records remain source-attributable; no half-committed mail or shipment.
7. **Conflicting same-partner documents:** Multiple booking originals and two weeks of source delivery for same supplier; recipient/partner recency cannot choose verified links; ambiguous stays review.

**Bounded design challenge disposition:** Each of the seven counterexamples is representable under the selected J1/J2/E1-E4 semantics; this is a **modelled challenge**, not a passing executable test or independent specialist report. The still-material failure modes are *source-owner adoption and installed Odoo 19 Enterprise realizability*. These block claims of validated implementation readiness and remain explicit rather than forcing a new architecture expansion.

## 6. Small ordered implementation contract, no authority to execute

**Protected freeze:** The following are not negotiable as implementation conveniences: operator-frozen Phase 1 BRS meanings and all 120 stable rule/acceptance texts; one owner per commercial/stock/physical/document/mail fact; J1/J2 under Logistics and E1-E4 under Export; E3 references J1, not a single feeder load; authorized supplier-FAS/PO-only/buyerless flow; independent weight/quantity authority; revision-bound scoped invalidation; no false terminal events; no scanner mandate; no Phase 2 provider dependency; no direct external send or economic posting from Export; no duplicate original bytes, no private source fixtures in public git. Any material conflict returns to the operator before affected code is written.

| Unit | Bounded implementation target (ONLY after separate code grant) | Predecessor acceptance | Minimum demonstrable completion / no-go |
| --- | --- | --- | --- |
| **P0: owner contract proof** | Read exact current owner BRS/ADRs and installed Odoo 19 Enterprise registry; adopt/reject J1/J2 storage, Export E1-E4, named command surfaces, Linda source-kind and Documents verifier. Pin manifest DAG, runtime version and company policy. | None; read-only proof/spike is allowed only under explicitly permitted environment access | Accepted interface signature table or exact mismatch report; any unadopted core owner interface BLOCKS subsequent affected implementation |
| **P1: physical identity foundation** | In existing `plasticos_logistics` and Transaction only: source-backed load company, deterministic exact link, buyerless guard; J1/J2 physical source association, data migration/ACL; keep normal domestic behavior. | P0 + M0 snapshot | EE-02/04, IC-T01/T02/T07 and first-by-SO negative. No schema changes to Export until owner J1/J2 contract exists. |
| **P2: Documents / Linda owner seams** | In their existing respective modules: one scoped business verification and native bridge delegation; booking-origin Linda purpose, SQL upgrade and centralized send/unknown/recipient guards. Source owner only; no new queue/verification writer. | P0; P1 where exact J1 source required | EE-05/07; IC-T08/T09/T10/T13/T14. PO/SO emails and domestic document paths stay intact. |
| **P3: thin Export core** | Add E1-E4, accepted booking revisions, stable capacity, J1-bound slots, E4 precise planned cargo, minimal menus and current constraints; no freight/stock/mail/physical event writer. | P1 and affected P2 source interfaces accepted | EE-01/03/04, IC-T03..T06, IC-T11/T12/T15. Two concurrent commits and same-number carrier roll prove revision atomics. |
| **P4: reporting, integrated upgrade and stop** | Six native report populations with exact scopes, QWeb/layout, end-to-end migration/replay; independently verify hard negative scenarios. | P1-P3 accepted exact revisions | EE-01..09 + IC-T01..17 and applicable original AC cases; no real sender activated. Return exact revision-bound proof, residuals and release recommendation; **no automatic merge/deploy/cutover**. |

**Implementation boundaries:** Prefer smallest in-scope owner corrections. No `plasticos_export` plugin mutates source-owner schemas opportunistically; no new model/file outside the above irreducibility or source contract. A future coding delegation must pin current SHA/branch, all allowed repositories, exact mutation file scope, source-valid commands, independent CI/Enterprise acceptance and the governed publication path. This technical pack is NOT a compiled coding agent contract and does not grant `make pr` or any other execution permission. The user has elsewhere prioritized Staging-to-production **domestic Odoo MVP**, and that priority is not superseded merely by completing Export design.

## 7. Closure, exclusions and explicit stop conditions

**Closure obtained inside this working pack:** selected physical J1/J2 model; selected Export E1-E4 field/relational target and no-E3-load-FK decision; state/effect matrix; explicit source-owner logical signatures; seven-owner adoption matrix; migration/Enterprise proof plan; five small ordered execution units; falsifying scenarios. These are protected from silent revision within this design handoff.

**Not obtained and never represented as completed:** actual source-owner admission of J1/J2 or named methods; exact installed Enterprise registry/Json proof; output of `l9.authority.resolve`, current validated GAR observer projection, formal Semantic Integrity Audit, independent Break Tester receipt, producer-validated GARReceipt v2 or independent runtime assessment; any Odoo changes, PR, test run, mail, migration, promotion, export release or deployment. `CONVERGED` as canonical GAR admission and `READY_TO_EXECUTE` remain **WITHHELD**.

**Stop only the affected work** for: (i) an existing native/owner model proven semantically equivalent to J1/J2 (avoid duplication, require pre-code substitution decision); (ii) a real owner/constitutional contract forbidding the selected relation or field type; (iii) a prospective cross-company link, fabricated movement, unknown source data presented as confirmed, or cycle in manifests; (iv) installed Enterprise divergence that changes method/field shape; (v) a conflict in frozen BRS and material candidate behavior. Do not remediate by narrowing acceptance, making global law in Export, changing historical physical facts, or inventing an upstream API. Record exact code/owner/line and route the minimum correction/decision.

### Primary source anchors

- [Current Logistics load company/first-by-SO heuristic](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/load.py#L37-L46) and [auto-link at create](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/load.py#L257-L299).
- [Transaction 1:1 and buyer-required constraint](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/transaction_inherit.py#L8-L62); [transaction order references](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_transaction/models/transaction.py#L30-L65).
- [Physical load seal/trailer fields](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/load.py#L225-L239), [legacy line container/packaging fields](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_transaction/models/transaction_line.py#L95-L125).
- [Current Documents verifier](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/models/document.py#L166-L185), [native bridge independent verifier and partner recency](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents_native/models/document_native.py#L118-L175), [invoice/close-only compliance API](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/models/compliance_service.py#L12-L64).
- [Linda purposes, PO/SO SQL CHECK](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/linda_request.py#L153-L279); [native mail outcome guard](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/linda_request.py#L839-L927); [Logistics owner supersession](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/business_rules/SUPERSESSION.md).
- [Document ownership and native interop](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/business_rules/NATIVE_DOCUMENTS_INTEROP.md); [Documents local owner law](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md).

**Next single safe action:** exact revision-bound Logistics/Transaction owner adoption and Enterprise proof of J1/J2 + buyerless company/source identity, with a read-only source-target review first. If it fails, correct the owner boundary before Export schema changes. No broad feature scope is opened.

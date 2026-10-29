# PlasticOS Export Phase 1 | Implementation Readiness Contract v2.5

**Classification:** BOUNDED TECHNICAL REALIZATION CANDIDATE / OWNER ADOPTION REQUIRED.  
**Target:** `cryptoxdog/IB-Odoo_19`, verified `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112` on 2026-10-28.  
**Global source:** `Quantum-L9/.github`, inspected `main@3dcdeaae355b6de08562993f705084d7a3714bfd`; the source registry and GAR observer profile exist, but a producer-validated projection receipt and formal GAR convergence have NOT been produced.  
**Business design:** Operator-frozen 2026-10-28 Phase 1. This contract is a proposed realization **inside** the freeze, not a supersession, code authorization, or claim of installability.  
**Current repository law:** `INVARIANTS.md` v2.2.0. **Working candidate only:** `GOVERNANCE/ODOO_INVARIANTS_v3.3.0_DRAFT_r1.md`, with POS-INV-01..25 and BAN001. No draft clause displaces admitted repository law.  
**Runtime, migration, integration, test, external sending, publication:** NOT_RUN / NOT_AUTHORIZED.  
**Source examples:** private material under `EXPORT_BRS/SOURCES/` is INTERNAL ONLY and MUST NOT be committed or copied into public fixtures.
**v2.6 interop addition:** `../INTEROP/CROSS_MODULE_INTEGRATION_CONTRACTS.md` owns the seven proposed cross-owner interface semantics; this v2.5 model-readiness document still owns its candidate Export model shapes and gates. The new interop proposal does not freeze fields or confer upstream ownership/authorization.

## 1. The one authoritative reading path

Read in this order: (1) `CONVERGENCE/OPERATOR_DESIGN_FREEZE.md`, (2) `MODULE_DESIGN/plasticos_export/README.md`, (3) this contract, (3a) `../INTEROP/CROSS_MODULE_INTEGRATION_CONTRACTS.md` (v2.6 source-owner interface proposals and mandatory owner proofs), (4) `RULES/BRS-EXP-01.md` through `BRS-EXP-14.md` and `REGISTRY/rules.json` (sole stable Export rule statements), (5) `ACCEPTANCE/cases.json` and this directory's `RULE_REALIZATION_MATRIX.csv`, (6) `CONVERGENCE/ARCHITECTURE_DECISION_CANDIDATE.md` and `CONVERGENCE/TARGET_OWNER_HANDOFF.md`, (7) current source-owner Logistics, Documents, Purchase, Stock and accepted ADR/BRS at the revision being implemented, (8) the v2.2.0 repository constitution and the separately held draft v3.3.0. Earlier numbered addenda, supersession records and historical decision frontiers remain provenance, not a second live implementation instruction.

**Precedence:** Explicit frozen user choices > non-superseded applicable owner BRS and accepted ADRs (subject to actual owner authority) > derived implementation recommendation. On an actual conflict, preserve the exact conflicting IDs as an unresolved owner decision; do not silently overwrite BRS text or substitute this contract. `LOCKED` and `DESIGN` are source registry statuses, not proof of repository adoption. The 120 rule statements and 120 acceptance case texts are unchanged in this release.

## 2. Scope and non-goals

**Ship in Phase 1 after owner adoption and tested runtime proof:** confirmed carrier booking identity and accepted carrier revisions; independent local-time-aware ERD/cutoff fields; equipment-specific confirmed booking slots; explicit allocations to source order lines/custody and a unique actual shipment when known; booking list/form/overview; six native-backed report populations with direct permission-preserving drilldown; source-attributed and revision-safe exposure to Logistics, Linda and Documents. Buyer-unassigned material and supplier-arranged FAS delivery are valid, not exceptional, when their real authorization/evidence exists. Native/manual non-scanning capture is supported under POS-INV-25 proposal without relaxing actual requirements.

**Do not build in Phase 1:** second order, freight, stock, physical container, e-mail, original document, verification, accounting or reporting authority; custom OWL portal, graph service, independent warehouse or shop-floor workflow, warehouse scanning mandate, FindTEU, AESDirect, autonomous customs filing, speculative ocean movement event engine, or private fixtures in git. Native Odoo reporting and QWeb suffice unless a witnessed runtime gap proves otherwise. Phase 2 rules remain in the registry but are `DEFERRED_P2` in the implementation matrix.

## 3. Source-observed current boundaries, not hypothetical module APIs

| Current owner | Observed source at pinned Staging | Consequence for realization |
| --- | --- | --- |
| Transaction | `plasticos_transaction/models/transaction.py` has `sale_order_id` (Many2one), `purchase_order_ids` (Many2many), `supplier_id`, `buyer_id`, `line_ids`. | Many shipment transactions can refer to one actual order; order references alone are NOT fulfillment-line proof. |
| Logistics | `plasticos_logistics/models/transaction_inherit.py` defines unique `transaction.load_id` and a universal supplier-and-buyer load-link constraint (54-62). | Preserve per-physical-shipment 1:1 link, but narrow buyer eligibility at Logistics owner; DO NOT replace it with a universal 1:many transaction-to-load relation. |
| Logistics | `plasticos_logistics/models/load.py` sets `company_id` related to `sale_order_id.company_id` (43-46) and selects a first transaction by SO in `create` (257-298). | Buyerless real movement and exact multi-shipment identity require a Logistics/Transaction owner correction BEFORE Export linkage. No fake SO/company/load. |
| Physical identity | `plasticos_logistics/models/load.py` has `trailer_number` and `seal_number` (226-227); `plasticos_transaction/models/transaction_line.py` has `container_no`, `seal_no`, and `units` with packaging-oriented `unit_type` (98-124). | ISO container identity/journey semantics are NOT proven. Existing similarly named fields may mean packaging or drayage equipment. Resolve exact physical identity at the owning model; Export must not create a rival physical container master. |
| Freight context | `plasticos_logistics/services/freight_context.py` currently emits `equipment_class: None` (77) and derives company through load/SO. | Logistics must bind actual road equipment and revision-bound export constraints before its own rate/dispatch. Export never confirms rates or dispatches. |
| Documents | `plasticos_documents_native/models/document_native.py` has its own `action_verify`, `action_override`, and newest-partner `_auto_link_partner` (118-175). `plasticos_documents/models/document.py` also has verification actions (166-185). | One verified business verdict and exact typed associations must be accepted at Documents owner. Export cannot call both writers or accept partner-recency links. |
| Linda | `plasticos_logistics/models/linda_request.py` currently encodes PO/SO issuance and cancellation purposes (153-191), not carrier-booking issuance. | Booking notice and optional drayage packets need a separate revision- and audience-bound Linda-owned obligation, not an Export mail queue or unguarded enum insertion. |
| Equipment master | `plasticos_facility_profile/models/equipment_type.py` is a facility equipment type catalog with `equipment`, `handling`, `quality` categories, not a proven ocean container-class owner. | Reuse its classes only if the owning semantics and data contract are shown compatible; otherwise use a narrowly scoped booking capacity class under Export, with the actual physical equipment class under Logistics. |
| Dashboard | `plasticos_logistics/models/load_dashboard.py` is a read-only SQL view over loads and joins transaction by `t.load_id`. | Reuse for authorized Logistics metrics where grain and scope fit; do not assume its current SQL view covers new buyerless movements or booking slots. |

**Existing owner business law:** `plasticos_logistics/business_rules/README.md`, `SUPERSESSION.md` (real PO-only, SO-only and buyerless operating paths), `NATIVE_DOCUMENTS_INTEROP.md` and `plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md`; exact status and installed behavior remain distinct. An accepted source-owner handoff is a prerequisite to implementation, not something this pack grants.

## 4. Candidate minimal Export-owned technical model (not yet admitted)

Model names are proposed stable external identifiers for the accepted Export business concepts. Types indicate Odoo field semantics, not pre-verified installed APIs. Do NOT copy these verbatim into code before owner contract adoption and exact Odoo Enterprise field/registry verification.

### E1. `plasticos.export.booking` (one real ocean reservation)

| Proposed field / relationship | Semantics and essential constraint |
| --- | --- |
| `company_id: Many2one(res.company)` required | Immutable issuer-company scope; checked with all source/line/load/document references. Company is not inferred from a buyer. |
| `carrier_booking_no: Char` nullable until source issued; `carrier_id: Many2one(res.partner)` nullable until known | Carrier-issued external number and actual issuer; not a substitute for stable internal ID. A number alone is NOT globally unique. Same-number amendment is not automatically a new booking. |
| `source_identity: Char` plus `source_document` typed reference | Stable binding to exact source authority for replay and distinguishing reused numbers; original file remains in native Documents. If identity is ambiguous, create a review candidate, not an authoritative confirmed booking. |
| `current_revision_id: Many2one(plasticos.export.booking.revision)` | Read-only pointer to ONE accepted effective business revision. May be absent for unconfirmed/candidate booking; do not infer it from latest uploaded file. |
| Effective six fields | Booking Number, Steamship Line, POL, POD, cargo cutoff, ERD are first-class current projection values from accepted revision; retain independent source attribution. No missing value becomes zero or substitute date. |
| Additional revision-backed projection | Terminal/rail/empty pickup/loaded return locations; requested versus confirmed equipment capacity; carrier/forwarder/vessel/voyage; doc/VGM cutoff; ETD/ETA; booking party and source-status; precision and provenance. Do not turn an estimated event into actual proof. |
| `slot_ids`, document links, audience-safe smart actions | Read-only aggregation and exact native links. Never calculate fulfilled stock/invoiced quantities from a slot count. |

**Identity constraint:** require company + attributable issuer + source-scoped booking identity and a real disambiguation rule; do not impose blind `unique(booking_no)` or invent a stable carrier identifier when it is unknown. A requested reservation and confirmed carrier space are distinct. The exact canonicalization key must be witnessed against real same-number revision and legitimate number-reuse fixtures before schema freeze.

### E2. `plasticos.export.booking.revision` (source-backed accepted facts)

| Proposed field / relationship | Semantics and essential constraint |
| --- | --- |
| `booking_id: Many2one` required; `source_original_id: Many2one(documents.document)` or accepted typed native original link; `source_message_id` optional | Original and message remain owned by Documents/Mail. No copied attachment bytes, verification flag, external mail state or file store. |
| `source_revision_identity`, `observed_at`, `source_issued_at`, original carrier reference | Idempotent source identity and multiple clocks preserved. Source revision may be same-number roll, cancellation, supplement, new booking or unresolved. |
| `candidate/accepted/rejected/superseded` evaluation disposition plus `accepted_by`, `accepted_at`, `acceptance_basis` | **Business acceptance**, not receipt/OCR classification; accepted snapshots and attribution are immutable. A correction creates a successor. |
| Typed sourced term snapshot | Equipment/count, locations, local zone and precision, ERD/cargo/doc/VGM deadlines, operational terms and source provenance. Store normalized UTC only when enough source precision and time zone exist. Preserve raw local text and unknowns; never guess a DST offset. |
| `supersedes_revision_id`, `affected_scope` / referenced obligations | Effective change only after deterministic company, carrier, booking and revision authorization; changed pending obligations become stale/reviewed by their owners; completed events stay intact. |

**Why a narrow revision record is justified:** native document file versions and mail chatter preserve originals/history but have not been shown to express an immutable, accepted, typed multi-field carrier schedule revision with exact affected-scope and replay identity. Confirm installed native capabilities first; if they *do* meet this obligation, remove this extra model before coding. No separate version file store or generic audit framework is authorized.

### E3. `plasticos.export.booking.slot` (one confirmed equipment-space unit)

| Proposed field / relationship | Semantics and essential constraint |
| --- | --- |
| `booking_id: Many2one` and `company_id` derived and checked | Slot belongs to exactly one actual booking. No cross-company allocation. |
| `slot_key: Char` and `equipment_class` (20STD/40STD/40HC/45STD/45HC as applicable) | Stable unit within booking (not ISO physical container number). Exact source class and configured allowed substitution retained. Unique `(booking_id, slot_key)`; source-confirmed count generates slots only after accepted confirmation. |
| `load_id: Many2one(plasticos.load)` optional; `transaction_id` via exact authoritative movement association only | Do not attach to a guessed first transaction. One active physical shipment cannot occupy two distinct current booking slots without an explicit separately authorized multi-leg arrangement. Actual container/seal belongs to Logistics/Stock owner. |
| `cargo_line_ids`, state/projection and current revision | A slot can contain several real cargo-source lines but counts as **one** slot. Assigned capacity is not actual loaded/stock quantity. |

**Capacity invariant:** `confirmed_count_by_class = occupied + available + explicitly unusable/held` at one booking revision and company; requested but unconfirmed units are not available; supplier PO count and cargo link count never multiply slots. If an accepted amendment reduces capacity below occupied allocations, create an exception/hold for exact affected slots; never delete loaded slots or silently reassign physical containers. Under concurrent allocations, lock authoritative booking/slot capacity within a committed transaction and recheck against the current revision. An ORM `@api.constrains` check alone is not adequate concurrency proof.

### E4. `plasticos.export.booking.cargo.link` (planned cargo distribution, never a fulfillment ledger)

| Proposed field / relationship | Semantics and essential constraint |
| --- | --- |
| `slot_id: Many2one` required; `company_id` checked | One planned source line can participate in one slot; many line links may belong to one slot; link count must not become container count. |
| Real `purchase_order_line_id`, `sale_order_line_id`, native `stock_move_id` where applicable, or exact owned-custody source, plus optional exact `transaction_id` | At least one eligible attributable real source, never a guessed shared PO/SO or fabricated buyer. References are restricted by the actual source owner and company; no implicit matching based on partner. |
| `planned_quantity`, real `uom_id`, source/rule reason and revision | Only prospective capacity allocation, NOT stock on hand, delivered quantity, accepted supplier/buyer weight, invoice quantity or financial effect. `NULL` means unknown, not zero. Conversion and over-allocation validation follow native UoM/product/line ownership. |
| Source/approval/revision and active disposition | Replay-safe allocations with authorized change history. Actual shipped/received amounts are queried from native fulfillment owner and displayed separately, with reconciliation exceptions. |

**Placement contraction:** Candidate E2 goes in existing proposed `models/booking_revision.py` only after irreducibility proof; E3 and E4 belong together in proposed `models/booking_allocation.py`, not a new universal line ledger. E1 belongs in proposed `models/booking.py`. The cross-owner shipment reference is projected via `models/load_extension.py` ONLY if owner-approved source links are established and a dependency cycle is avoided. The exact 4-model proposal is a reasoning candidate; *field and contract shape are not yet admitted or frozen for code*.

## 5. Authoritative commands and state/effect boundaries

| Logical operation (names illustrative, NOT executable method names) | Allowed owner/result | Hard negative |
| --- | --- | --- |
| `record_booking_notice` | Native Documents receives original; Export logs a source-attributed **candidate** booking revision only after exact source association. | OCR, filename, sender email or same partner never independently confirm or bind a load. |
| `accept_booking_revision` | Authorized Export action checks company, issuer, exact booking and current source revision, handles conflict/roll and promotes one immutable accepted snapshot; replay is no-op. | A same-number change cannot silently change deadlines, equipment, physical events or past send evidence. |
| `reserve_or_move_slot` | Export acts only on confirmed, current capacity under concurrency-safe transaction, exact compatible source lines, company and authorization; re-evaluates stale obligations. | No double slot, no paid stock posting, no invented buyer, no arbitrary first-SO transaction. |
| `bind_physical_shipment` | Owner-approved exact Logistics/Transaction identity is accepted into a slot; actual container/seal/movement stays at physical owner. | No automatic load creation merely because booking has 5 slots. |
| `publish_logistics_requirements` | Export supplies current, source-backed route/equipment/deadline requirements; Logistics independently decides feasible pickup, tender, carrier, rate, packet, dispatch. | No Export freight writer or auto-changing an approved rate after roll. |
| `request_booking_issuance` | Linda (not Export) owns revision + party + audience-scoped native Mail intent, sent/unknown/acknowledged outcomes and cancellation ordering. Existing PO issue remains separate. | An Export button cannot send via its own mail queue or retry uncertain deliveries automatically. |
| `evaluate_export_document_readiness` | Documents returns exactly attributed applicable current verification/override per obligation; Export shows read-only results. | No duplicated `verified` flag, expiry mutation, or latest-partner match. |
| `display_export_reports` | Source-owned model queries, Odoo search/pivot and optional native dashboard; precise filters and ACLs survive drilldown. | No duplicate count from join, stale status labeled live, summary with unfiltered click-through. |

**Activation:** All external communication, AI provider calls, scheduler/live actions, Stock/Accounting writes, imports and migrations remain disabled or in an operator-approved isolated test until separately authorized. A successful installation is not live activation permission.

## 6. Owner handoff: precise blockers, owners and required proof

| ID / priority | Owner + exact surface | Required owner-consistent contract change | Evidence that closes it |
| --- | --- | --- | --- |
| `EXP-GAP-01` P0 | Logistics + Transaction; `load.py`, `transaction_inherit.py` | Stable load company from authorized movement source; deterministic exact 1:1 physical shipment/transaction association without first-by-SO guess; buyerless eligibility for valid procurement/owned cargo with native Sales guards unchanged. Migrate/reconcile old links, hold ambiguous. | Real 30-SO/4-PO partial fixture, buyerless path, duplicate SO candidates, cross-company mismatch, existing domestic invariants pass on Enterprise. Owner BRS/ADR adopted. |
| `EXP-GAP-02` P0 | Logistics/Transaction physical identity | Choose one owner for actual ISO container + seal + journey assignment. Evaluate `load.trailer_number`, `load.seal_number`, `transaction.line.container_no`, native Stock packaging; prove exact distinct container-grain, migration and package/ISO separation. | Five actual ISO containers, repeated packaging/partial rows, one per journey report without double counts, cross-company security. If no existing sufficient owner field, an owner-approved minimal extension only. |
| `EXP-GAP-03` P0 | PlasticOS Documents + Native bridge | One authoritative verification per exact document-obligation revision; native original/versions; typed multi-associations; no recency-based `auto_link`; candidate AI cannot accept/verify. | One original shared across two loads, same-partner four-week ambiguity, revoked/superseded evidence, restricted reader, exact Enterprise Documents test. Owner BRS/ADR adopted. |
| `EXP-GAP-04` P0 | Logistics / Linda | Separately addressed booking issuance/updated booking/cancel intent with exact booking source revision and recipient; PO issue independent; drayage conditional, freight fingerprint equipment-aware and current. | PO sent before booking; roll invalidates only pending same-party obligation; unknown send is not resent; supplier-FAS without invented carrier. Installed Mail and actual commands verified. |
| `EXP-GAP-05` P0 | Export + installed native Odoo | Freeze valid booking source identity, accepted revision representation, slot/cargo model and company isolation only after explicit native model and dependency check. | Same-number roll, distinct issuer reuse, concurrent allocation, 5 slots from 4 POs, requested-unconfirmed space, upgrade-safe backfill; no new authority copied. |
| `EXP-GAP-06` P0 | Odoo Enterprise platform + Export | Verify exact installed technical module names for Documents, dashboard/spreadsheet, view expressions, QWeb export and ACL behavior before manifest and data declarations. | Clean Enterprise install and upgrade, six report drilldowns, scoped CSV/XLSX/PDF, named addons exist and DAG acyclic. |
| `EXP-GAP-07` P1 | Product authority / governance (parallel, never silently assumed) | Reconcile draft POS-INV-25 and v2.2.0-to-v3.x mapping for eventual admission. Preserve v2.2.0 law until explicit decision. | Explicit approved version/mapping and source-owned semantics if/when admission is requested. Does not by itself block designing under both non-conflicting constraints. |

**Stop rule:** No agent may implement an Export workaround for an unresolved P0 owner defect or mark a proposed interface authoritative. P0 is a design/handoff gate, not a request for broad refactoring. An owner-accepted equivalent using a different minimal field layout is valid if it preserves exact required behavior and pass/fail proofs, but changes to frozen meanings must return for operator decision.

## 7. Dependency and migration boundary

`plasticos_export` is downstream of `plasticos_logistics` and of the appropriately tested Documents bridge and their declared prerequisites; the actual manifest must reflect only imports/models read at runtime. `plasticos_logistics`, `plasticos_transaction`, `plasticos_documents` and `plasticos_documents_native` MUST NOT depend on Export. A public consumer callback or owner-owned hook may read a typed Export context without reversing the addon dependency; validate the exact mechanism and install graph first, not via unverified dynamic model lookup. Keep Odoo XML IDs stable, explicit security and full backend ACL coverage. The frozen proposed filetree is an upper-bound design hypothesis; eliminate unjustified files, not needed protections.

Upgrade/migration design: install creates no speculative booking or slot from old SO/PO. Existing load/company/link backfill is owned by Logistics/Transaction migration with deterministic source and exception population, preserving identities. Original documents are never copied. An imported booking uses attributable carrier/source identity, records its raw source, and gets a reviewed accepted revision before available capacity appears. Re-import/replay must not duplicate booking, slot, link, document or outbound intent; unmatchable records are explicit review, not silently lost. An installed feature flag never activates external effects.

## 8. Phase 1 acceptance proof contract

| Test witness | Must demonstrate | Must reject |
| --- | --- | --- |
| W01 shared orders | SO=30 expected, PO=4 real, four independently sourced shipment executions over weeks; no fake orders; native actual fulfillment only. | One SO auto-selects first transaction, whole order completes after one load. |
| W02 mixed booking | Carrier booking with five 40HC confirmed slots from four supplier POs; multiple cargo lines in one slot. | 5 x 4 = 20 container count, reused one source-line quantity across shipments. |
| W03 revision | Same-number roll, new-number replacement and cancellation preserving source bytes, earlier revision, local zone/precision, affected commitments. | Silent overwrite, forced rebooking, unrelated transport hold, sent-mail erasure. |
| W04 buyerless/FAS | Source-authorized owned or supplier-delivered cargo reaches actual terminal through correct owner, no fake buyer/SO/drayage. | Mandatory buyer or assigned Stock treated as terminal acceptance. |
| W05 documents/AI | Same partner sends two booking revisions and four load evidences; exact association; AI candidate only; one effective verified business verdict. | Newest-partner guess, native verify bypass, attachment upload alone satisfies gate. |
| W06 Linda | Approved PO issued once before carrier booking; booking separately issued; amended document party-scoped; actual email state uncertainty preserved. | Duplicate PO, double-sent booking on timeout, carrier economics leakage. |
| W07 concurrent capacity | Two simultaneous legitimate attempts competing for last confirmed slot; one commits and other clearly fails/retries; no lost accepted revision. | Both succeed or counts exceed confirmed capacity. |
| W08 stock and financial | Actual native move/receipt/invoice references and independent weight sources; zero postings from Export. | `transaction.final_weight` treated as universal billing or carrier scale as verified VGM; duplicate economic effect. |
| W09 reporting and security | Six distinct report grains with direct same-filter drilldowns; unknown vs zero; exact per-company/party role; native list/pivot/CSV/XLSX/QWeb. | N x M source join count, unfiltered navigation, cross-company counts or attachments, historic data disguised as current. |
| W10 manual/optional | Without scanner, mobile app, AI extraction or external tracking, authorized paperwork/manual path works with attribution and verification. | Fake package genealogy, silent absent-evidence success, device required for a lawful workflow. |
| W11 upgrade/install | Odoo 19 Enterprise fresh installation and upgrade, acyclic manifests, XML/ACL/QWeb IDs, migration/replay, all automation disabled by default. | Community-only green claimed Enterprise readiness; forced mail/deploy/cutover. |

**Test binding:** The 120 stable `AC-EXP-xx-xxx` acceptance IDs retain their unchanged positive and negative text and all remain `NOT_RUN`. `RULE_REALIZATION_MATRIX.csv` maps each BRS/AC to source owner, suggested surface and blocking gate. W01-W11 are additional integration witnesses that group existing rules; they do NOT replace, retype, weaken or add normative BRS rules. Unit tests, Odoo Enterprise integration tests, concurrency and permission tests are mandatory before delivery; schema/index/static checks alone are insufficient. Preserve negative witnesses and do not weaken assertions to make CI green.

## 9. Developer delivery and explicit completion boundary

Implementation is **NOT authorized by this pack**. After owner-adopted contracts and a separately authorized code campaign, implement only the smallest justified functionality in the actual current source owners, then Export; no private source fixture in tracked repo. For every affected BRS, deliver source path/commit, implementation owner, positive+negative test outcome, exact Odoo Enterprise SHA/edition, migration result, data privacy proof, and unresolved blockers. Use the repository's actual required checks only after independently verifying commands at their owners. No guessed `make` targets, raw push, release/deploy, live provider, live email or accounting cutover.

**Current readiness disposition:** User-frozen business architecture and candidate technical realization are documented. Seven gates remain (six P0 implementation gates plus an independent governance admission track); Enterprise tests and formal L9 projection/receipt validation are NOT_RUN/UNKNOWN. This package is **suitable for bounded source-owner contract review and implementation planning**, not for an unsupervised full-addon implementation instruction. The single next handoff is `EXP-GAP-01` plus the coupled `EXP-GAP-02` exact physical identity proof at Logistics/Transaction; they unblock correct slot links without inventing another shipment authority.

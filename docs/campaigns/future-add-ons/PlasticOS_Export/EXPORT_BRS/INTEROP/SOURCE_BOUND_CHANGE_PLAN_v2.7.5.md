# PlasticOS Export v2.7.5 | Source-bound blast-radius completion

**Result:** the repository-side change plan is reconciled for the declared scope. Every retained finding and identified effect has a selected change, justified nonchange, explicit no-add, or a named target-evidence block. **The full installed-target pre-code gate is NOT cleared.** One consolidated read-only target inspection remains unavailable in this session; coding authorization is also separate.

This is planning work, not implementation. No target repository file, Odoo database, PR, mail, migration, deployment, or production setting was changed. Source-owner denotes the authoritative module/code surface, not a person required to sign. Previously frozen business decisions remain in force.

## Binding and effective reading path

- Target: `cryptoxdog/IB-Odoo_19`, integration branch `Staging`, immutable revision `677d734fd88615d673501d91de88734b7150ff50`.
- Predecessor: `PlasticOS_Export_Source_Owner_Boundary_Corrected_v2.7.4.zip`, SHA-256 `6c3311cffae8a696b9bc5ed5a09b0bd86f5c84dccfd3fe238dfee29236d3005a`.
- Governing operator requirement: POS-INV-26 in `GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md`, preserved byte-for-byte. Repository constitutional `INVARIANTS.md` is not replaced.
- Protected product interfaces: `EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md` and `TECHNICAL_CONTRACT_v2.7.json`, unchanged. Six model shapes and twelve public command signatures are not widened.
- Active machine plan: `SOURCE_BOUND_CHANGE_LEDGER_v2.7.5.json`. Its effect IDs are stable. The file index below is a projection, not another decision source.
- Active technical decisions and proof criteria: this file C01-C09. Where an older plan calls a file conditional, untouched, or awaiting human source-owner signatures, this successor's exact disposition controls planning. Historical rule text, physical evidence, and accepted business meaning are not overwritten.
- Historical source delta: the earlier `04bd0594...` baseline was followed by three commits changing seven CRM/material files. They are individually accounted for in RP-07. The technical models do not derive physical identity from those material phrases.

**What completion means here:** no identified repository effect is left as an optional edit or an unsigned-owner question. The two explicit external-runtime rows account for the remaining installed-target inspection, rather than disguising it as verified no-change. The plan's concrete content is completed; the stronger claim that every live/configured consumer is proven covered is withheld until S1-TARGET.

## Current-source rebind during completion

The source moved from `78476ddb74861d900992f7f5ec3ec2cc2a63e8bf` to **`677d734fd88615d673501d91de88734b7150ff50`** during the final check. GitHub compare reports ten commits and 24 changed paths, confined to Documents, Native Documents and Transaction. Unchanged owner observations remain reusable by that exact compare; changed owner semantics were reread. The resulting plan preserves the merged one-writer/exact-association work, narrows its residual changes, retires redundant proposed files, and updates migration/version coordinates. This is not an audit to reopen the already-merged repair.

Current Documents is 19.0.2.1.6, Native Documents 19.0.1.2.10, Transaction 19.0.2.3.43. The planned successors are Documents 19.0.2.1.7 and Native Documents 19.0.1.2.11. Transaction stays unchanged. The old proposed lower-version migration paths remain in the ledger as NO_ADD; none disappears without a disposition.

<a id="c01"></a>

## C01 | Company, commercial identity and manual freight

### Source-to-consumer paths

`source PO/SO/custody -> Logistics load.company_id -> freight context/event/history/RFQ -> report templates and global company rules -> SQL Load dashboard -> native downloads and operations`.

`one real transaction.load_id -> reverse load.transaction_id -> Claims, Commission, CRM material statistics, admin navigation`. This relation remains one-to-one when applicable. J1/J2 adds physical provenance without turning a transaction into a transport-leg collection.

### Selected behavior

A real source-company is mandatory for a new operational load. It is resolved from the exact authorized source, never from `env.company`, a same-named party, a booking count, or the first matching SO transaction. Source PO, SO, custody and existing load references must agree. A supplied company is checked against those sources and the actor's company access; it is not its own authority.

For legacy SO-based form entry, `action_create_load` continues to provide `default_sale_order_id`; changed `load.create` owns the new check. If one eligible unlinked transaction matches the exact SO and source-company, preserve deterministic auto-linking. With zero or several eligible records, create/retain the actual load only when its own authority is sufficient, leave its commercial link unresolved, and show one internal review activity. Do not pick a winner, invent a buyer, or duplicate a transaction. A requested explicit pair that is contradictory fails atomically.

The existing `UNIQUE(transaction.load_id)` stays. A legitimate PO-only load can lack a buyer; owned-stock supply can lack a fictitious supplier PO. A sale-specific action still requires the actual sale party and source authorization. The new Export/J1/J2 commands never confirm native commercial orders, stamp supplier confirmation, or enqueue existing transaction cron populations.

### Manual context versus repeat-rate context

The current rate confirmation path uses an intake-dependent freight context even for manual rates. This must be corrected at Logistics, not hidden by an Export override.

Keep the existing `freight_context_v3` serialization and qualification for unchanged legacy intake-backed contexts. Add a distinct versioned manual/buyerless context for exact company, origin/destination snapshots, positive reference weight, sourced equipment identity or explicit unknown, and no intake repeat-stream. The absence of that stream can make SAL **ineligible** while leaving manual freight confirmation legitimate. SAL must explicitly abstain before a no-intake lookup; a null stream must never match every null-stream history record.

Do not overwrite accepted v3 fingerprints during migration. A confirmed historical load uses its recorded context-version validator. A material change of lane, equipment, carrier, or source authority withholds new scheduling/release until reauthorized. New manual contexts cannot be misrepresented as v3 SAL evidence. Existing quote/RFQ eligibility continues requiring its actual transaction and qualified context; this campaign does not add a universal buyerless tender product. No price engine or speculative fallback is introduced.

### Exclusion detail

The existing freight history and legacy rate reconciliation readers already prefer load-company; retaining their SO fallback for valid legacy rows does not create a company for new rows. Their inputs, stored history grain and signatures remain unchanged. RFQ still abstains when its declared prerequisites are absent. The transaction spine, original line `container_no`/`seal_no`, and intake bridge are not repurposed as J1 identity.

CRM material statistics still traverse transaction -> load -> pickup_datetime and revenue. The planned change preserves that relation and existing schedule fields. J1-only activity adds neither transactions nor CRM revenue; changing the historical meaning of the CRM display is outside this work. The admin transaction KPI population likewise remains commercial, not container/slot counts.

<a id="c02"></a>

## C02 | Physical source, allocation and concurrency

J1 (`plasticos.iso.journey`) and J2 (`plasticos.iso.journey.source`) are implemented together in `plasticos_logistics/models/iso_journey.py`. J1 is a sourced physical container-cycle identity; the same ISO number can recur in a different cycle. J2 is an exact provenance association to a real load, stock move-line or non-stock evidence. Neither model is a stock, weight, finance or milestone ledger.

The native-Stock path reads actual Stock execution. Supplier-delivered FAS/third-party activity may have no company-dispatched load or owned-stock movement; it requires attributable original evidence and the exact source party/cycle. A PO alone is not a physical event. Never create a picking, truck, buyer, sale or transaction to make a field non-null.

E3 binds a J1, not one feeder load. Multiple J2 sources may feed one J1, and a source may feed several J1s only where actual source scope supports it. E4 carries planned cargo participation. Evidence coverage quantity does not become native fulfillment, AP, AR, VGM, gross, tare or net weight. Unknown quantity remains explicitly unknown, not zero or an even division across containers.

### Exact constraints and effect ordering

- Retain the v2.7 partial uniqueness for one active E3 binding per J1. Historical bindings remain; no container-number global uniqueness.
- J2 uniqueness is the normalized exact journey, typed subject and source scope. SQL constraints must prevent null-subject loopholes as well as Python validations. Wrong-company subject or attachment fails before any accepted relation.
- Quantity commitment checks all current E4 allocations using the same source line/custody basis across **all bookings**, not merely the current booking. A held commitment retains its source allocation until an explicit release; it is not counted twice.
- For a command, derive candidate source/booking/slot sets without writing. Lock shared native source rows by model and ID, then E1 booking rows by ID, E3 slots by ID, J1/J2/load subjects by model and ID, scoped evidence rows, then Linda request rows. Re-read the sets and revisions after locking; a changed set is a retry/refusal, not an out-of-order new lock. This retains the frozen booking-before-slot rule and serializes two bookings competing for one source quantity.
- Row locks and SQL uniqueness are both required. An ORM-only check or cached count is insufficient. Command failures leave no half-created allocation, queued mail or mutation of native source records.
- Use the existing declared natural identities for replay: E2 source revision key; E4 allocation key; J1 company/source-cycle key; J2 exact typed source tuple; already-effective accept/release/bind returns the existing record. Validate a replay against the persisted immutable source facts. Changed source facts are a new candidate/successor, never a successful duplicate replay or an in-place accepted-history rewrite. Do not create a generic operation bus/ledger.

A five-to-four capacity amendment never deletes the fifth historical slot, discards a sent notice or rewinds an already-dispatched movement. Confirmed capacity, committed distinct slots and overcommitment are separate counts. Unknown affected scope blocks new dependent operations conservatively while the accepted source is retained. It never authorizes blanket cancellation or invents a particular affected container.

<a id="c03"></a>

## C03 | Physical guards and truthful event recording

The Logistics common guard is authoritative for issuing a new instruction. Every route must reach it: load actions, `_transition`, standalone dispatch, bulk wizard, composer handoff, direct dispatch, queue claim and due notice generation. The bulk wizard keeps its existing `_transition` call; duplicating policy in the wizard would create drift. Standalone dispatch must not directly bypass the owner guard through `create`, `write`, or `action_transition`.

The downstream Documents bridge supplies evidence-policy checks through ordinary Odoo inheritance. The downstream Export integration supplies current booking/slot constraints. No base Logistics import/FK depends on Documents, Native Documents, Security Base or Export. A declared operation requiring an unavailable provider is `not_available`, never an unguarded success. An ordinary domestic operation without an Export obligation is evaluated by its existing owners, not blocked by the absence of an unrelated optional addon.

**New release and observation are different.** A carrier roll can withhold new scheduling/dispatch/packets. It cannot prohibit the operator from retaining trustworthy evidence that a truck already moved. Record the observation and the scoped exception without undoing the physical fact or silently granting another release. Do not add new load states just to encode booking amendments.

### Actual-event clock fields

In the existing load model, add guarded `actual_pickup_at` and `actual_delivery_at`, each tied to its exact source attachment/reference. Their source reference and any correction reason/actor/time are preserved in the existing immutable freight-event facts. Add `pickup_evidence_attachment_id` and `delivery_evidence_attachment_id` as `ir.attachment` pointers when the source is documentary; an attributable existing observation record is an explicit alternative, never merely a copied schedule time.

Existing `dispatched_at`, `delivered_at`, pickup/delivery schedule fields and their historical reporting meanings remain intact. A state transition or database import does not fill actual timestamps. Event recording validates exact load/company/actor/party, source time precision and original access; corrections append evidence, never erase the former event. A missing actual event leaves the dependent timer unknown and produces one internal exception. These fields do not alter J1/J2 or add a second event store.

The Load form exposes paperwork-based entry and governed actions. No scanner, new warehouse process, external portal or mobile app is a prerequisite. Existing documentation links and native attachments remain the capture substrate.

<a id="c04"></a>

## C04 | One Linda sender, source adapters, replies and races

### Request storage and native source resolution

Extend `plasticos.logistics.request` and the existing response owner, not a new queue. Add typed source metadata on the existing request: `source_kind`, `source_res_id`, `source_revision_key`, `operation_key`, `source_payload_snapshot` and `source_payload_fingerprint`. These are internal implementation fields on the existing Linda owner, not new fields on the frozen E1-E4/J1-J2 interfaces. Company, source-kind/id, purpose, accepted source revision and intended audience are validated together.

Preserve existing PO/SO fields and their legal branch CHECKs. Booking rows must have no fabricated PO/SO. Database uniqueness covers the normalized logical obligation, including company, source, purpose, source revision and audience; operation-key retry additionally compares immutable payload. A new email payload hash by itself is not permission to send again. `NULL` must not create uniqueness gaps.

The frozen `request_booking_correspondence` method remains on Linda. Its Export model resolution is supplied by normal downstream `_inherit` in `plasticos_export/models/logistics_integration.py`; no base dependency or FK to Export. Without the registered target provider, the booking request is unavailable. Sender identity is taken from authorized source company, and recipient/role/permission are checked, not trusted because supplied in arguments.

The internal snapshot contains only the already-approved, audience-safe subject/body facts and exact original attachment identifiers for that obligation. It cannot modify orders, verification or physical truth. Rendered content is immutable after claim. Template identity and rendered payload hash are retained with the request evidence. Changing the carrier/recipient/revision requires owner reevaluation, not editing a queued artifact to a different business meaning.

### XML and dependency placement

`plasticos_logistics/data/linda_booking_mail_template.xml` targets `plasticos.logistics.request`. It never references the downstream booking model. ACK and missing-document templates target the same request owner with their exact purpose-specific snapshots.

Keep the upstream `linda_inbound_ai.xml` PO/SO filter unchanged. The new `plasticos_export/data/linda_booking_inbound.xml` is the sole booking-only trigger and calls the same Linda response owner. The target filters are disjoint. Native original retention, message ancestry and the existing message-identity dedupe must still apply. A matching From address or a reply on the newest thread is not authenticated business acceptance. Missing original, stale ancestry, forward, wrong company, unbound party or ambiguous source produces a candidate/review outcome, never a booking revision accepted by the email text.

Base Logistics tests must not import Export. They test the narrow source-resolver contract and unavailability with a test-only provider. Real booking-native threading and guard composition are tested in Export after its dependencies are installed.

### Final-claim ordering and outcomes

The existing `mail_mail_inherit.py` remains the only native interposer. Its current claim locks a queued request and checks attempts, but does not recheck source currentness there. Correct this exact seam.

A claimant acquires the same source-to-request lock order used by revision acceptance, re-reads current revision, recipient, source validity and immutable packet, and then durably records the send claim. That is the operation's logical authorization point. If a revision wins first, the old unclaimed mail is withheld/canceled before SMTP. If the send claim wins first, a later revision retains the old in-flight/historical request and records a scoped follow-up/hold; it cannot unsend bytes or relabel an unknown attempt as never sent.

Native SMTP is not transactionally atomic with PostgreSQL. Preserve a durable attempt marker before transport; a crash/ambiguous outcome is `unknown`, not an automatic retry. An explicit authenticated reconciliation or authorized human retry is separate. Do not promise exactly-once delivery, rollback a sent message, or recreate the same packet to evade dedupe. Ordinary unrelated Odoo mail remains outside Linda's claim machinery.

Composer, manual/direct send and cron routes create the same governed obligation and use the same final claim. A UI check is not the authorization boundary. Queueing does not stamp `dispatch_sent`; only the native confirmed outcome does. Reminder messages do not reuse the full original packet.

<a id="c05"></a>

## C05 | Reuse the now-present evidence owner; add only operation scope

**Source rebind:** the final Staging check found a merged Documents repair at `677d734fd`. It already implements the single business verifier, immutable decision provenance, exact per-subject association, multiple business rows sharing one original, live currentness checks, and native delegation. These completed owner repairs are not reopened. The earlier proposed `document_evidence_link.py` is now **NO_ADD**. The existing `plasticos.document` record is already the authoritative evidence-association row.

This contracts implementation to an existing owner without changing the protected E1-E4/J1-J2 model shapes or twelve public signatures. A historical proposed-file entry is not authority to create a duplicate model after reality changes. The current-source compare and every affected path are retained in the ledger.

### Exact residual scope fields and identity

Reuse existing `attachment_id`, `source_revision` (the original attachment checksum), `res_model/res_id`, `subject_company_id`, `source_reference`, `covered_quantity`, `association_state`, actor/time, verification/override, `is_current` and `superseded_by`. Do **not** repurpose `source_revision` as the carrier booking revision or duplicate subject/company fields under new names.

Add only these dimensions to this same row: `obligation_kind` (required, legacy default), `operation_revision_key` (explicit business operation revision, required for a non-legacy obligation), `coverage_key` (normalized documentary coverage identity), `quantity_known` (explicit Boolean, false by default), and `evidence_uom_id` (`uom.uom`, required when an operation quantity is known). `covered_quantity` remains evidence coverage, not a stock or settlement fact. Existing legacy quantity behavior is preserved; unknown operation quantity is not inferred from a historical nonzero number or an assumed unit.

The operation-scope key contains original/version, exact subject/company, obligation, operation revision and coverage. Legacy `action_associate(res_model, res_id, source_reference, covered_quantity=0.0)` retains its signature, default legacy meaning and idempotence. Its existing original/association locks remain and integrate with the C02 order. A private owner helper `_associate_scope(res_model, res_id, source_reference, *, obligation_kind, operation_revision_key, coverage_key, quantity_known, covered_quantity, evidence_uom_id)` supplies the explicit new dimensions; this is an internal implementation seam, not a thirteenth frozen public contract. It validates the acting user independently and cannot be authorized by a caller-supplied context flag.

The existing form command may submit the new draft scope fields through that helper. Accepted scope fields join the existing protected-association field set. Each resulting row is verified or overridden only through the existing business commands. An operation row has its own decision; it never writes a different legacy row's Boolean. SQL uniqueness must distinguish legitimate scopes and prevent NULL-key replay gaps. Distinct source claims are not silently collapsed, and contradictory payload on the same exact scope is refused.

The current closed subject allowlist must be exposed as an owner-owned extension hook: core Documents supports the declared native subjects and Logistics J1; Export supplies its downstream kinds by ordinary `_inherit`. A model string is not an authority grant. Enforce target, original and company access, source party, allowed operation and current revision. No core Documents dependency on Native Documents or Export is added.

### Verdict and consumer behavior

Keep the frozen public receiver/signature `plasticos.document.get_scoped_evidence_verdict(...)`; it delegates to the existing compliance service. Reuse `_currently_eligible` for the original/version and historical decision. The new query additionally matches exact company, subject, obligation and operation revision. Unknown obligations/provider availability fail closed, never vacuous compliance from zero rules.

Legacy invoice/close and transaction display paths explicitly select `obligation_kind='legacy'`. Preserve the current RECEIVING rule: **one row must cover the subject; partial rows are not aggregated**. New operation coverage never posts Accounting, updates Stock, approves an invoice, or changes the receiving policy. `plasticos.transaction._compute_compliance` is now observational in the merged source and remains unchanged; its new no-post regression is preserved.

Maintain the existing live-expiry/search refresh and add only the remaining scope/old-new-subject invalidation. Exact currentness must respond to attachment replacement, expiry, revocation, supersession and association changes. Preserve source decision actor/time rather than erasing historical verification. The global native projection is not the source of a transaction checklist.

### Native bridge and downstream consequences

The current Native bridge already refuses direct decision writes and partner-recency association; sync creates a pending original shell without changing verification. Leave `document_sync.py` and `document_native_views.xml` unchanged. Narrow only `document_native.py` exact projection and search predicates so a sole **operation-only** row cannot project as legacy/global verified. An original with multiple rows remains ambiguous at the native Boolean, while the exact business rows remain inspectable and independently actionable in Documents.

Extend the existing `test_verification_delegation.py` and `test_native_search_parity.py`; no new Native test module or test-loader edit is necessary. Preserve the already-merged Native 19.0.1.2.6 historical-snapshot migration byte-for-byte. The residual Native change has no persisted schema transformation and needs no new migration.

Claims create hooks must ignore non-legacy operation evidence rows before claim/notification creation. Valid exact legacy claim initiation remains unchanged. Commission's checklist reads current **legacy business rows**, not an ambiguous per-original native flag; its transaction SQL grain, payouts and rates stay unchanged. This prevents a second scope from either falsely clearing a trade obligation or hiding a still-valid exact legacy row. Admin/CRM commercial populations remain unchanged. The Documents load bridge provides exact buyerless navigation and its normal downstream physical-guard specialization.

<a id="c06"></a>

## C06 | Access and reporting closure

Backfill/validate company first; tighten ACL and record rules only afterward. J1/J2 have required company and no company-null exception. Global company rules bind every role; additive group permissions do not override them.

Existing business groups are `plasticos_security_base.group_logistics` and `group_operations_manager` (which implies operational groups). Their J1/J2 grants belong in **Security Base**, not an upstream Logistics XML reference to a downstream group. No new human role or automatic group enrollment is required. Accepted evidence/history remains immutable even where an administrator has general model write rights.

`plasticos.load.dashboard` is a distinct SQL-backed model. Add `company_id` to its field declaration and both SELECT branches; apply an independent global rule. A Load rule alone does not protect dashboard SQL rows. Preserve one row per load, and preserve the existing transaction join. A new column need not become a displayed list column to be filterable by a rule.

Remove or narrow the existing broad Documents base.group_user mutation grants where they defeat the scoped owner policy. Also guard sensitive fields at model/action boundaries, because ACL changes alone do not stop all authorized-user bypasses. Test form, search, read_group, direct RPC/import, QWeb, native original/download and two simultaneous allowed-company contexts. Shared contacts/attachments are never evidence that business operations belong to every company.

All six Export report populations retain their frozen grains. Count distinct slots, journeys, source POs and cargo links separately; never multiply a booking count by joining its many sources. Preserve exact record drilldown and current source revision. Missing actual quantity/time remains unknown. Native reports/spreadsheets are consumers, not a new dashboard engine or permission bypass.

<a id="c07"></a>

## C07 | Clocks, data transitions and recovery

### Current obligations

ACK: actual successful packet send -> T+2h reminder -> T+4h escalation, with five-minute due polling and observable backlog/lag. At most one logical notice per source/purpose/party/revision/touch. No full-packet resend. Routine quiet-hour constraints remain per existing BRS; urgent internal exceptions are not silenced. No new holiday/business-calendar policy is invented.

Document chase: supplier +1/+5 business days after actual pickup; carrier +2/+6; buyer +1/+5 after actual delivery. Use existing Monday-Friday owner convention and source-local precision. Missing/ambiguous event or time zone cannot become a guessed midnight or dispatch-based timestamp. One current internal exception replaces repeated activities. Source evidence cleared/superseded/canceled before claim cancels the queued chase.

### Exact version targets

| Module | Inspected version | Planned successor | Migration surface |
| --- | --- | --- | --- |
| Logistics | 19.0.1.14.5 | 19.0.1.14.6 | pre + post |
| Documents | 19.0.2.1.6 | 19.0.2.1.7 | pre + post; reuse current exact-association owner |
| Native Documents | 19.0.1.2.10 | 19.0.1.2.11 | code/search guard and tests only; no new migration |
| Security Base | 19.0.1.2.21 | 19.0.1.2.22 | pre; no added post script |
| Automation | 19.0.2.1.6 | 19.0.2.1.7 | template/XML upgrade, prior activation preserved |
| Claims | 19.0.1.1.2 | 19.0.1.1.3 | guarded trigger update; no financial rewrite |
| Commission | 19.0.1.4.3 | 19.0.1.4.4 | checklist/consumer change; no payout rewrite |
| Export | absent | 19.0.1.0.0 | new install, no fabricated historical backfill |

Source versions are not installed-tenant versions. S1 compares them. A tenant already at/past the proposed successor or with an incompatible custom schema forces exact rebinding, not a guessed version bump. In particular, the existing Documents `migrations/19.0.2.2.0/pre-migrate.py` is **not traversed** by target 19.0.2.1.7. Its eight legacy-column renames are not silently adopted into this campaign.

### Migration decision table

| Data class | Deterministic action | Must refuse / preserve |
| --- | --- | --- |
| Existing load with one agreeing source company | Preserve ID, company and valid exact transaction relation; prefill only when derived from exact retained source | Conflicting SO/PO/custody companies never choose a winner |
| NULL company with exactly one authoritative source | Repair existing stored column in Logistics pre-phase before required-field/SQL rule enforcement; record old/new/source ID | No source, conflicting sources, or inaccessible source stops upgrade; no env.company/default |
| Multiple transactions for one SO | Retain each already-proven 1:1 link; leave unproven link unresolved | No first-by-SO reassociation; uniqueness conflicts stop |
| Legacy ISO/seal/container strings | Preserve legacy fields unchanged; J1/J2 start empty unless exact approved provenance mapping exists | No J1 inferred from packaging, PO count, identical string or filename |
| Missing actual pickup/delivery time | Leave actual time unknown; do not start its reminder clock | No schedule/dispatch/create_date substitute |
| Legacy business/native verification mismatch | Record row-level discrepancy and original/version identity; reconcile before changing established eligibility | No native-wins/business-wins blanket rule, no silent de-verification or auto-acceptance |
| One original, multiple explicit legitimate scopes | Create separate exact link rows to retained version, each with its own acceptance/coverage | No duplicated binary, no proportional quantity inference |
| Existing Linda PO/SO request | Deterministically backfill typed metadata from the exact original source, retain purpose/revision/recipient/mail/attempt | Preserve old branch constraints, no relabeling as booking |
| Queued unclaimed request, stale source | Withhold/cancel that pending obligation, retain lineage | Never replay old revision |
| Claimed, sent, or unknown-outcome request | Preserve historical attempt and outcome exactly; require explicit reconciliation for unknown | Never erase attempt, mark unsent, or auto-retry after restore |
| Existing cron/automation/template customization | Record XMLID, active flag, source/config hash; compare to expected policy before upgrade | No previously inactive record silently enabled; unplanned active consumer blocks S1 |
| New required/unique/check constraint | Census and repair deterministic existing-column data before the relevant schema phase; create empty new tables normally | Do not defer a prerequisite required-field backfill to post-migration |
| Re-run of a completed migration | Assert same facts and perform no duplicate creation | A changed source/schema is a discrepancy, not retry permission |

### Upgrade and rollback order

Quiesce all workers, cron, inbound processing and outbound delivery on the authorized clone before touching schema. Capture exact code/config/community/Enterprise/module versions plus a consistent PostgreSQL and filestore backup. Snapshot cron/template/request metadata. Verify clone identity before any command; do not use the business database.

Logistics pre repairs deterministic existing company data and audits request constraints. Schema load creates J1/J2 and selected fields. Logistics post verifies invariants, applies exact request backfills and rebuilds views. Documents pre classifies legacy proof conflicts; post assigns legacy defaults to existing rows without changing their accepted decision and recomputes affected scopes; it does not fabricate new operation acceptance. The Native bridge retains its merged custody/decision snapshot behavior and receives only the operation-discriminator projection guard; no new conversion migration runs. Security pre refuses company or SQL-projection incompleteness before global rules tighten. Install/update the remaining owner and Export layers in dependency order, still neutralized.

Before exposure, compare row counts, IDs, key financial totals, accepted evidence outcomes, ACL denial sets and all preserved originals. No ambiguous financial or ownership discrepancy is tolerated. A failed statement/schema/migration restores the coherent pre-upgrade DB+filestore+code/config set on the test clone. Reverting Python alone is not recovery from changed schema/data. Rerun only after the cause is accounted for.

After any possibly delivered external message, blind database rollback cannot retract the real-world effect. Preserve send claims/outcomes and reconcile before a resumed system can send. An upgrade receipt must name the backup and exercised restoration; this session generated neither. Uninstalling a populated Export addon is not a supported rollback method and requires separately planned decommissioning.

<a id="c08"></a>

## C08 | Dependency, test reachability and ordered realization

### Declared module boundary

Eight inspected direct Logistics dependents are Admin Dashboard, Automation, Claims, Commission, CRM Bridge, Documents, Native Documents and Security Base. CRM Sync is downstream through CRM Bridge/Security. Manifest reachability alone does not require editing every module; the ledger gives the exact semantic consumer disposition.

Export depends on its owner interfaces, not the reverse. Logistics can reference native Stock/Attachment/Partner and its existing Transaction dependency. Documents specializes Logistics evidence policy. Native Documents binds Enterprise originals. Security Base references Logistics/Docs models and owns business group grants. Export's integration file specializes all downstream booking-dependent lookups. No additional integration addon, queue, original store or cross-module event bus is planned beyond the selected thin plasticos_export addon.

Fresh installation must work both with and without the optional Export addon. Export is `auto_install=False`. Legacy domestic business workflows do not acquire a booking requirement. Within the full dependency-installed integration fixture, planned external activity is disabled until separately authorized. Existing PO/SO owner modes are not changed by a booking test.

### Required architecture registration, not another approval ceremony

The pinned `docs/adr/README.md` requires an ADR for a cross-module contract or an expensive schema choice. The earlier blanket no-ADR exclusion is therefore withdrawn. Add exactly `docs/adr/ADR-129-export-physical-evidence-and-owner-contracts.md`, using the next unused number in the inspected tree. It records the existing six-model/twelve-command architecture and source ownership, not new business meaning. Add its required index entries in `docs/adr/README.md` and `ARCHITECTURE.md`, and the task-specific reading link in `AGENTS.md`. The new addon README points to these owner homes and its module-local requirements.

No human-signature gate, new global rule, duplicate BRS registry or separate integration framework is introduced. The record is planned, not already committed, admitted or runtime-proven. Original BRS source files and the protected technical contract remain unchanged. Only sanitized specifications are transplanted; the private ZIP and source originals stay outside the repository. If another change occupies ADR-129 before implementation, that is source drift requiring an exact index/path rebind, not permission to overwrite another ADR.

### Existing test-runner gap and selected repair

`config/odoo_module_order.yaml` supplies a domestic default roster and an Enterprise list. Its reader supports named sections. However, `scripts/test_env.sh:test_scope` explicitly rejects modules outside the default roster, and its test path upgrades only that roster. Merely adding an Export test file or YAML section would not run it.

Add the explicit `export_integration_modules` declaration and narrowly extend **the existing** `test_env.sh` owned-clone path to recognize that declared optional scope. The admitted base template remains unchanged. The extension is installed only on a separately owned, neutralized Export clone; the effective upgrade/test roster includes the chosen extras and is recorded by the existing evidence output. Undeclared extras, default domestic tests on an Export-populated clone, foreign/stale databases, source changes, zero tests and missing test summary all refuse. Preserve leases and template protection. A base-only clone proves the no-Export behavior; do not uninstall populated Export records to mimic that fixture.

Companion changes belong in `tests/test_test_env_safety.py`. Its stub harness proves its own refusal logic, not Enterprise feature correctness. The optional profile must not change the domestic default install list, automatically rebuild/replace the canonical fixture, or install Export on production. No second test infrastructure is necessary.

The path `scripts/run-odoo-tests.sh` is mentioned in comments/generated indexes but returned 404 at the pinned source. It is not an executable delegation surface. No command from that name or an uninspected Make target is emitted here. An executor validates the actual present entrypoint and local environment before running it.

Odoo 19 test modules are imported from `tests/__init__.py`, not the addon-root `__init__.py`. Keep the four inspected addon roots unchanged. Real registry collection and per-module counts prove later that no cases were silently skipped. New base-owner tests cannot import the downstream Export addon; the real cross-addon composition is tested from Export.

### Bounded realization units, only after S1 and separate grant

| Unit | Exact goal | Entry / exit |
| --- | --- | --- |
| S0 | This source plan, nonchange accounting, protected hashes and active index | Artifacts only; does not write product code |
| S1 | Read-only installed-target proof in C09 | Exact match or a source-bound refusal; no implementation prerequisite is presumed tested |
| S2 | Logistics physical company, manual context, J1/J2, actual clocks, guard foundations, company ACL/dashboard and migration | Source contracts unchanged; V01-V04/V11/V13 planned owner fixtures |
| S3 | Documents and Native evidence authority, precise invalidation, Claims/Commission consumer correction | Depends on relevant S2 model shape; no money/Stock writer |
| S4 | Linda typed source, final claim, native replies/notices and carrier documents | Depends on S2/S3; request-targeted templates avoid Export cycle |
| S5 | Export E1-E4, downstream inheritance/inbound trigger, native reports and explicit test-runner scope | Owner methods first realized; no mock-only claim of integration |
| S6 | Full Enterprise composition, negative/race tests, clone upgrade/retry and restore | Acceptance only for exact candidate bytes; no automatic merge/deploy/activation |

S2-S5 describe implementation dependencies, not a demand to merge a PR after every file. The full change set is planned before S2 begins. Actual branch topology and publication remain subject to the separately authorized coding contract and current governance owner; this pack issues no push, PR or deployment command.

<a id="c09"></a>

## C09 | Remaining exact-target proof and refusal semantics

There is one consolidated missing **read-only** input, S1-TARGET. The repository/source work does not provide it. The attempted Enterprise branch read returned 404; no exact installed registry or live database configuration was supplied. This is the real remaining pre-code boundary, not permission from imaginary module owners.

| Required evidence | Exact subject / acceptance | Failure behavior |
| --- | --- | --- |
| Target identity | Authorized clone/database identity; application, community and Enterprise code revisions/digests; module versions and addons path | Wrong/missing identity or production ambiguity: no inspection with effects and no code entry |
| Native/model availability | `documents.document`, `documents_account`, `ir.attachment`, `mail.message`, `mail.mail`, native PO/SO/Stock/UoM; field types and supported extension methods actually consumed | Missing/incompatible API: name the affected plan row, preserve frozen shape, stop before coding that campaign |
| Installed extension closure | Actual inherited model classes and method resolution for mail send/claim, Documents verification/custody, Stock quantity and accounting gates | Undiscovered override becomes a new effect requiring disposition; no default compatibility assumption |
| Native view/report IDs | Exact existing Document list/search IDs, report rendering/attachment behavior and existing XML IDs used by bridges | Unsupported XPath/API gets an exact owner correction plan, not guessed XML |
| Dynamic consumers | Active `base.automation`, `ir.actions.server`, `ir.cron`, aliases, custom views, ACL/rule and installed-addon consumers on affected models; IDs, source/code/config hashes and disabled status | Unplanned caller or unauthorized sender remains blocked; never turn it off live merely to obtain a green proof |
| Migration class compatibility | Installed version interval and actual column/constraint shapes; counts for NULL/conflicting company, ambiguous links, mismatched verification and unknown/claimed sends | Unsupported class or contradictory authority stops. Numeric population alone may be supplied at upgrade; each possible class already has a defined action |
| Original/access contract | One original/version, explicit subject and company access, authentic actor authority, no false native global verification | Any material cross-company/original-scope ambiguity is not treated as success |

**Read-only handoff scope:** inspect the exact repository and its authorized installed Odoo 19 Enterprise target. Do not install, update, run crons, process email, change ACLs, create native business records or execute project tests. Output exact observations and mismatch paths, not a universal PASS label. Do not copy secrets or private message bodies into the public repository.

A matching S1-TARGET observation lets the operator evaluate a separate bounded coding grant against this exact plan. If it finds a material mismatch, the invariant requires a narrowly revised plan before code. Authorization does not manufacture absent evidence. The remaining original runtime, migration and recovery witnesses then run at their actual later stages.

**Machine-enforcement limit:** this session checks the archive/ledger and negative incomplete-plan fixtures. It does not demonstrate a hosted agent sandbox or CI gate preventing every unplanned edit. At coding handoff, bind the complete planned file allowlist and exact baseline to the existing executor controls. Any diff outside the selected CREATE/EDIT paths, missing dependency, changed source, unresolved scope or new ripple is a stop. Do not bypass that rule by calling a new edit a small cleanup.

## Verification obligations and independent proof limits

The following are *expected witnesses*, not recorded test successes. Each requires its exact candidate, installed dependency versions, input fixture, expected result, observed result and source-bound report. A green exit code, collected test name, generated JSON or our plan validator does not alone prove implementation behavior. The original 120 cases and 17 integration witnesses remain unchanged and NOT_RUN.


| Proof | Concern / owner | Positive witness | Required negative witness | Status |
| --- | --- | --- | --- | --- |
| V01 | Company and exact load relation; Logistics + Security | One valid source company and one exact transaction/load pair succeeds, including legitimate buyerless movement. | Conflicting company, nonexistent source, fabricated counterpart, first-of-two SO transactions, direct import/copy bypass and cross-company assignment refuse. | NOT_RUN |
| V02 | J1/J2 physical identity; Logistics | Two feeder sources associate to one real ISO journey; same container number in a later proved cycle is distinct. | No global container-number uniqueness, no fake load/picking, no mismatched company/original or accepted-history deletion. | NOT_RUN |
| V03 | Manual freight versus repeat-rate reuse; Logistics | Legacy v3 context golden remains unchanged; source-proven no-intake manual context permits authorized manual rate. | SAL without its repeat stream abstains before history lookup; mismatched context version or changed lane/equipment withholds new release. | NOT_RUN |
| V04 | All physical release paths; Logistics + Documents + Export | Authorized action, wizard, direct/composer and final sender paths reach the same guard. | Raw transition/create/write/standalone-dispatch bypass denies. Recording an already-observed physical event remains possible with evidence despite a rolled booking. | NOT_RUN |
| V05 | Allocation and revision concurrency; Export + Logistics | Exact source quantity and slot/journey bindings commit atomically with stable natural replay identity. | Two concurrent bookings cannot oversubscribe one source; two slots cannot bind one active journey; stale revision or same-key changed payload refuses without partial work. | NOT_RUN |
| V06 | Final send claim and unknown outcome; Linda + native Mail | One valid claimant records immutable current source/payload before transport. | Revision-before-claim withholds; claim-before-revision preserves historical/in-flight status; duplicate worker and crash/unknown never auto-resend. | NOT_RUN |
| V07 | Native booking reply attribution; Linda + Export | One saved exact current message ancestry yields one candidate response through disjoint booking trigger. | Missing original, wrong party/company, stale/ambiguous ancestry, forwarded or injected content never accepts booking/READY/finance; PO/SO trigger unchanged. | NOT_RUN |
| V08 | Operation evidence isolation; Documents | Existing owner rows distinguish original, exact subject, obligation and operation revision while sharing one binary. | An operation row does not satisfy a legacy invoice/close or global native Boolean; wrong scope/currentness/company/unknown provider fails closed. | NOT_RUN |
| V09 | Legacy consumers and merged protections; Documents + Native + Claims + Commission | Current baseline one-writer, exact association, receiving coverage and no-post suites retain their assertions. | Do not aggregate partial RECEIVING or infer UoM; no claim/notification/financial side effect from operation-row creation; search and projection parity preserved. | NOT_RUN |
| V10 | Actual event clocks and reminders; Logistics + Documents + Linda | Attributable actual event anchors day-level chasers; actual sent anchors +2h notice/+4h escalation with five-minute polling. | No create_date/dispatch/schedule substitution, repeated same-touch notice, early send, full-packet reminder or guessed timezone. Expired obligation cancels before claim. | NOT_RUN |
| V11 | Company and role isolation; Security + owners | Correct Logistics/operator role sees its company and permitted exact originals; existing domestic role remains valid. | Bare internal user, multiple-role union, SQL read_group, report/download/RPC and another allowed-company context cannot bypass global company/subject checks. | NOT_RUN |
| V12 | Install, registration and test reachability; Integration | Tracked candidate imports/XML/DAG and named Export clone-only profile reach all selected owner/Export tests. | Base template/default domestic roster unchanged; undeclared extras, contaminated default clone, untracked scan, zero tests or missing registry blocks acceptance. | NOT_RUN |
| V13 | Upgrade census, version range and replay; Migration owners | Supported baseline upgrades with stable IDs/original hashes/legacy eligibility and idempotent rerun. | Unknown version/schema/data class, conflicting company or decision, stale lower-version script and unexpected future2.2.0 migration refuse before unsafe change. | NOT_RUN |
| V14 | Coherent restore and recovery; Integration | An isolated clone restores the exact code/config/database/filestore set and reproduces prior authoritative totals and attachments. | Code-only rollback, missing original, lost send claim, reinstall-as-rollback or automatic unknown-send replay fails. | NOT_RUN |
| V15 | Report population and drilldown; Export + dashboard owners | All six report populations preserve frozen grains, exact revision and accessible source drilldown. | Many-source joins do not multiply slot/journey/booking/transaction counts; missing quantities/times are not manufactured; SQL dashboard company filter is independent. | NOT_RUN |
| V16 | Unchanged CRM/material/import boundary; CRM + Transaction + Integration | Current CRM/material mappings and idempotent historical native-order import behavior remain unchanged. | No J1/Export inference from legacy container strings, new revenue from physical identities, buyer fabrication or import-triggered live correspondence. | NOT_RUN |
| V17 | Plan and executor boundary; Architecture + existing executor | Exact plan/hash/allowlist references and required owner reading path remain coherent. | Unplanned path, omitted effect, missing no-change reason, source drift or absent source command is a STOP. Artifact diagnostics alone do not prove host enforcement. | NOT_RUN |
| V18 | Non-stock physical proof and no finance; Logistics + Documents + Export | Supplier/third-party delivery with real source evidence can be represented without a company-dispatched truck or artificial picking. | A PO alone is not actual custody/quantity; no evidence recompute or booking action posts native finance, changes stock or creates a fake trade. | NOT_RUN |
| V19 | Neutralized installation and external-effect preservation; Integration + Linda | Clone test operations remain mail/cron neutralized; former inactive automation remains inactive across upgrade. | No production database selection, automatic outbound activation, new sender, historical packet replay or hidden database action escapes the configured-consumer census. | NOT_RUN |

## Complete source-file and consumer index

The following projection is generated from `SOURCE_BOUND_CHANGE_LEDGER_v2.7.5.json`. Multiple effects on one path form **one coherent delta**, not duplicate file implementations. An unchanged concern can coexist with a different planned edit to the same file. `CREATE` describes future repository bytes, not files created in this working ZIP. `NO_ADD` preserves a rejected/superseded proposed path. No delete operation is required by the selected plan.

Ledger byte SHA-256: `e1c8dbb143834388776983eaf1a31a40cd7843f4ead6406eff3cd0d021c78dd6`. 203 effects, retaining all 162 original effect IDs; 199 distinct paths/interfaces.

| File/interface | Disposition | Effects | Owner |
| --- | --- | --- | --- |
| `AGENTS.md` | EDIT | RP-07-E092 | Integration |
| `ARCHITECTURE.md` | EDIT | RP-07-E091 | Integration |
| `EXPORT_BRS/INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md` | REVIEW_ONLY | RP-07-E065 | Integration |
| `GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md` | REVIEW_ONLY | RP-07-E064 | Governance |
| `INVARIANTS.md` | NO_CHANGE | RP-07-E035 | Governance |
| `ci/check_circular_deps.py` | NO_CHANGE | RP-07-E034 | Integration |
| `config/odoo_module_order.yaml` | EDIT | RP-07-E072 | Integration |
| `docs/adr/ADR-129-export-physical-evidence-and-owner-contracts.md` | CREATE | RP-07-E090 | Integration |
| `docs/adr/README.md` | EDIT | RP-07-E036 | Integration |
| `native:documents.document,documents_account` | NO_CHANGE | RP-07-E031 | Native Odoo |
| `native:ir.attachment` | NO_CHANGE | RP-02-E011 | Native Odoo |
| `native:purchase.order.line` | NO_CHANGE | RP-02-E009 | Native Odoo |
| `native:sale.order.line` | NO_CHANGE | RP-02-E010 | Native Odoo |
| `native:spreadsheet_dashboard` | NO_CHANGE | RP-06-E009 | Native Odoo |
| `native:stock.move.line` | NO_CHANGE | RP-02-E008 | Native Odoo |
| `native:stock.picking,mail.mail` | NO_CHANGE | RP-07-E032 | Native Odoo |
| `plasticos_accounting/__manifest__.py` | INDEPENDENT | RP-07-E038 | Accounting |
| `plasticos_admin_dashboard/__manifest__.py` | NO_CHANGE | RP-07-E029 | Admin Dashboard |
| `plasticos_admin_dashboard/models/admin_dashboard.py` | NO_CHANGE | RP-06-E006 | Admin Dashboard |
| `plasticos_admin_dashboard/views/admin_dashboard_views.xml` | NO_CHANGE | RP-06-E007 | Admin Dashboard |
| `plasticos_automation/__manifest__.py` | EDIT | RP-03-E017 | Automation |
| `plasticos_automation/data/cron_trucker_followup.xml` | NO_CHANGE | RP-03-E013 | Automation |
| `plasticos_automation/data/email_templates.xml` | EDIT | RP-03-E010 | Automation |
| `plasticos_automation/data/workflow_automations.xml` | NO_CHANGE | RP-03-E011 | Automation |
| `plasticos_automation/models/stock_picking_automation.py` | NO_CHANGE | RP-03-E012 | Automation |
| `plasticos_automation/tests/__init__.py` | EDIT | RP-03-E018 | Automation |
| `plasticos_automation/tests/test_buyerless_carrier_templates.py` | CREATE | RP-03-E015 | Automation |
| `plasticos_automation/tests/test_carrier_reservation_not_dispatch.py` | NO_CHANGE | RP-03-E014 | Automation |
| `plasticos_claims/__manifest__.py` | EDIT | RP-07-E005 | Claims |
| `plasticos_claims/models/claim.py` | NO_CHANGE | RP-05-E023 | Claims |
| `plasticos_claims/models/document_inherit.py` | EDIT | RP-05-E022 | Claims |
| `plasticos_claims/tests/__init__.py` | EDIT | RP-05-E025 | Claims |
| `plasticos_claims/tests/test_document_export_evidence.py` | CREATE | RP-05-E024 | Claims |
| `plasticos_claims/tests/test_integration_flows.py` | EDIT | RP-07-E086 | plasticos_claims |
| `plasticos_claims/tests/test_state_machines.py` | EDIT | RP-07-E085 | plasticos_claims |
| `plasticos_commission/__manifest__.py` | EDIT | RP-07-E028 | Commission |
| `plasticos_commission/models/sales_dashboard.py` | EDIT | RP-05-E026 | Commission |
| `plasticos_commission/security/record_rules.xml` | NO_CHANGE | RP-06-E008 | Commission |
| `plasticos_commission/tests/test_golden_flows.py` | EDIT | RP-07-E088 | plasticos_commission |
| `plasticos_commission/tests/test_sales_dashboard_payout_access.py` | EDIT | RP-05-E027 | Commission |
| `plasticos_crm_bridge/__manifest__.py` | NO_CHANGE | RP-07-E024 | CRM Bridge |
| `plasticos_crm_bridge/models/crm_lead.py` | NO_CHANGE | RP-07-E025 | CRM Bridge |
| `plasticos_crm_bridge/models/material_profile.py` | NO_CHANGE | RP-07-E071 | CRM Bridge |
| `plasticos_crm_sync/__manifest__.py` | NO_CHANGE | RP-07-E066 | CRM Sync |
| `plasticos_crm_sync/services/orchestrator.py` | NO_CHANGE | RP-07-E026 | CRM Sync |
| `plasticos_crm_sync/tests/test_crm45_classification.py` | NO_CHANGE | RP-07-E067 | CRM Sync |
| `plasticos_crm_sync/tests/test_orchestrator_upsert.py` | NO_CHANGE | RP-07-E068 | CRM Sync |
| `plasticos_documents/__init__.py` | NO_CHANGE | RP-07-E017 | Documents |
| `plasticos_documents/__manifest__.py` | EDIT | RP-07-E002 | Documents |
| `plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md` | EDIT | RP-07-E023 | Documents |
| `plasticos_documents/business_rules/README.md` | EDIT | RP-07-E077 | Documents |
| `plasticos_documents/business_rules/SUPERSESSION.md` | EDIT | RP-07-E022 | Documents |
| `plasticos_documents/data/cron.xml` | NO_CHANGE | RP-05-E009 | Documents |
| `plasticos_documents/data/cron_missing_docs.xml` | NO_CHANGE | RP-05-E008 | Documents |
| `plasticos_documents/migrations/19.0.2.1.3/post-migrate.py` | NO_ADD | RP-07-E009 | Documents |
| `plasticos_documents/migrations/19.0.2.1.3/pre-migrate.py` | NO_ADD | RP-07-E008 | Documents |
| `plasticos_documents/migrations/19.0.2.1.4/post-migrate.py` | NO_CHANGE | RP-07-E096 | Documents |
| `plasticos_documents/migrations/19.0.2.1.7/post-migrate.py` | CREATE | RP-07-E095 | Documents |
| `plasticos_documents/migrations/19.0.2.1.7/pre-migrate.py` | CREATE | RP-07-E094 | Documents |
| `plasticos_documents/migrations/19.0.2.2.0/pre-migrate.py` | NO_CHANGE | RP-07-E074 | Documents |
| `plasticos_documents/models/__init__.py` | NO_CHANGE | RP-05-E013 | Documents |
| `plasticos_documents/models/compliance_service.py` | EDIT | RP-05-E003 | Documents |
| `plasticos_documents/models/document.py` | EDIT | RP-05-E001 | Documents |
| `plasticos_documents/models/document_evidence_link.py` | NO_ADD | RP-05-E002 | Documents |
| `plasticos_documents/models/document_rule.py` | NO_CHANGE | RP-05-E005 | Documents |
| `plasticos_documents/models/document_validation_matrix.py` | NO_CHANGE | RP-05-E006 | Documents |
| `plasticos_documents/models/load_docs_bridge.py` | EDIT | RP-05-E029 | Documents |
| `plasticos_documents/models/midnight_recompute.py` | NO_CHANGE | RP-05-E007 | Documents |
| `plasticos_documents/models/transaction_docs.py` | EDIT | RP-05-E004 | Documents |
| `plasticos_documents/models/transaction_docs_bridge.py` | EDIT | RP-05-E028 | Documents |
| `plasticos_documents/security/ir.model.access.csv` | EDIT | RP-05-E010 | Documents |
| `plasticos_documents/security/security.xml` | EDIT | RP-05-E011 | Documents |
| `plasticos_documents/tests/__init__.py` | EDIT | RP-05-E016 | Documents |
| `plasticos_documents/tests/test_account_move_transaction_link.py` | NO_CHANGE | RP-07-E097 | plasticos_documents |
| `plasticos_documents/tests/test_compliance_service.py` | EDIT | RP-05-E015 | Documents |
| `plasticos_documents/tests/test_exact_association.py` | NO_CHANGE | RP-07-E098 | plasticos_documents |
| `plasticos_documents/tests/test_native_verification_delegation.py` | NO_CHANGE | RP-07-E099 | plasticos_documents |
| `plasticos_documents/tests/test_pr322_findings.py` | NO_CHANGE | RP-07-E100 | plasticos_documents |
| `plasticos_documents/tests/test_scoped_evidence.py` | CREATE | RP-05-E014 | Documents |
| `plasticos_documents/tests/test_verification_writer.py` | NO_CHANGE | RP-07-E101 | plasticos_documents |
| `plasticos_documents/views/document_views.xml` | EDIT | RP-05-E012 | Documents |
| `plasticos_documents_native/__init__.py` | NO_CHANGE | RP-07-E018 | Native Documents |
| `plasticos_documents_native/__manifest__.py` | EDIT | RP-07-E003 | Native Documents |
| `plasticos_documents_native/migrations/19.0.1.2.6/post-migrate.py` | NO_ADD | RP-07-E011 | Native Documents |
| `plasticos_documents_native/migrations/19.0.1.2.6/pre-migrate.py` | NO_CHANGE | RP-07-E010 | Native Documents |
| `plasticos_documents_native/models/document_native.py` | EDIT | RP-05-E017 | Native Documents |
| `plasticos_documents_native/models/document_sync.py` | NO_CHANGE | RP-05-E018 | Native Documents |
| `plasticos_documents_native/tests/__init__.py` | NO_CHANGE | RP-05-E020 | Native Documents |
| `plasticos_documents_native/tests/test_native_evidence_bridge.py` | NO_ADD | RP-05-E021 | Native Documents |
| `plasticos_documents_native/tests/test_native_search_parity.py` | EDIT | RP-05-E031 | Native Documents |
| `plasticos_documents_native/tests/test_verification_delegation.py` | EDIT | RP-05-E030 | Native Documents |
| `plasticos_documents_native/views/document_native_views.xml` | NO_CHANGE | RP-05-E019 | Native Documents |
| `plasticos_export/README.md` | CREATE | RP-07-E093 | Export |
| `plasticos_export/__init__.py` | CREATE | RP-07-E039 | Export |
| `plasticos_export/__manifest__.py` | CREATE | RP-07-E040 | Export |
| `plasticos_export/controllers/` | NO_ADD | RP-07-E063 | Export |
| `plasticos_export/data/linda_booking_inbound.xml` | CREATE | RP-04-E011 | Export |
| `plasticos_export/models/__init__.py` | CREATE | RP-07-E041 | Export |
| `plasticos_export/models/booking.py` | CREATE | RP-07-E042 | Export |
| `plasticos_export/models/booking_allocation.py` | CREATE | RP-07-E043 | Export |
| `plasticos_export/models/booking_revision.py` | NO_ADD | RP-07-E045 | Export |
| `plasticos_export/models/load_extension.py` | NO_ADD | RP-07-E046 | Export |
| `plasticos_export/models/logistics_integration.py` | CREATE | RP-07-E044 | Export |
| `plasticos_export/report/export_report_actions.xml` | CREATE | RP-07-E054 | Export |
| `plasticos_export/report/report_booking_summary.xml` | CREATE | RP-07-E055 | Export |
| `plasticos_export/report/report_container_manifest.xml` | CREATE | RP-07-E056 | Export |
| `plasticos_export/security/export_record_rules.xml` | CREATE | RP-07-E048 | Export |
| `plasticos_export/security/ir.model.access.csv` | CREATE | RP-07-E047 | Export |
| `plasticos_export/tests/__init__.py` | CREATE | RP-07-E057 | Export |
| `plasticos_export/tests/test_booking_allocation.py` | CREATE | RP-07-E059 | Export |
| `plasticos_export/tests/test_booking_and_revision.py` | CREATE | RP-07-E058 | Export |
| `plasticos_export/tests/test_export_owner_handoff.py` | CREATE | RP-07-E060 | Export |
| `plasticos_export/tests/test_multicompany_permissions.py` | CREATE | RP-07-E062 | Export |
| `plasticos_export/tests/test_views_and_reports.py` | CREATE | RP-07-E061 | Export |
| `plasticos_export/views/allocation_views.xml` | CREATE | RP-07-E050 | Export |
| `plasticos_export/views/booking_views.xml` | CREATE | RP-07-E049 | Export |
| `plasticos_export/views/export_analysis_views.xml` | CREATE | RP-07-E052 | Export |
| `plasticos_export/views/export_menus.xml` | CREATE | RP-07-E053 | Export |
| `plasticos_export/views/shipment_views.xml` | CREATE | RP-07-E051 | Export |
| `plasticos_facility_profile/__manifest__.py` | INDEPENDENT | RP-07-E037 | Facility Profile |
| `plasticos_logistics/LINDA_BUILD_PLAN.md` | EDIT | RP-07-E078 | Logistics |
| `plasticos_logistics/__init__.py` | NO_CHANGE | RP-07-E016 | Logistics |
| `plasticos_logistics/__manifest__.py` | EDIT | RP-07-E001 | Logistics |
| `plasticos_logistics/business_rules/NATIVE_DOCUMENTS_INTEROP.md` | EDIT | RP-07-E021 | Logistics |
| `plasticos_logistics/business_rules/README.md` | EDIT | RP-07-E076 | Logistics |
| `plasticos_logistics/business_rules/SUPERSESSION.md` | EDIT | RP-07-E020 | Logistics |
| `plasticos_logistics/data/cron.xml` | EDIT | RP-03-E006 | Logistics |
| `plasticos_logistics/data/linda_booking_mail_template.xml` | CREATE | RP-04-E004 | Linda |
| `plasticos_logistics/data/linda_dispatch_ack_notice.xml` | CREATE | RP-03-E019 | Linda |
| `plasticos_logistics/data/linda_document_chase.xml` | CREATE | RP-04-E012 | Linda |
| `plasticos_logistics/data/linda_inbound_ai.xml` | NO_CHANGE | RP-04-E003 | Linda |
| `plasticos_logistics/data/linda_order_cancel_mail_templates.xml` | NO_CHANGE | RP-04-E007 | Linda |
| `plasticos_logistics/data/linda_po_mail_template.xml` | NO_CHANGE | RP-04-E005 | Linda |
| `plasticos_logistics/data/linda_so_mail_template.xml` | NO_CHANGE | RP-04-E006 | Linda |
| `plasticos_logistics/data/sequence.xml` | NO_CHANGE | RP-02-E006 | Logistics |
| `plasticos_logistics/migrations/19.0.1.14.6/post-migrate.py` | CREATE | RP-07-E007 | Logistics |
| `plasticos_logistics/migrations/19.0.1.14.6/pre-migrate.py` | CREATE | RP-07-E006 | Logistics |
| `plasticos_logistics/models/__init__.py` | EDIT | RP-02-E003 | Logistics |
| `plasticos_logistics/models/dispatch.py` | EDIT | RP-03-E002 | Logistics |
| `plasticos_logistics/models/freight_estimate.py` | NO_CHANGE | RP-01-E009 | Logistics |
| `plasticos_logistics/models/freight_governance.py` | EDIT | RP-01-E003 | Logistics |
| `plasticos_logistics/models/freight_quote.py` | NO_CHANGE | RP-01-E007 | Logistics |
| `plasticos_logistics/models/iso_journey.py` | CREATE | RP-02-E001 | Logistics |
| `plasticos_logistics/models/linda_request.py` | EDIT | RP-04-E001 | Linda |
| `plasticos_logistics/models/linda_response.py` | EDIT | RP-04-E002 | Linda |
| `plasticos_logistics/models/load.py` | EDIT | RP-01-E001, RP-03-E001, RP-01-E015 | Logistics |
| `plasticos_logistics/models/load_dashboard.py` | EDIT | RP-06-E004 | Logistics |
| `plasticos_logistics/models/mail_mail_inherit.py` | EDIT | RP-03-E005, RP-04-E010 | Logistics |
| `plasticos_logistics/models/purchase_order_inherit.py` | NO_CHANGE | RP-01-E014 | Logistics |
| `plasticos_logistics/models/rate_memory.py` | NO_CHANGE | RP-01-E008 | Logistics |
| `plasticos_logistics/models/sale_order_inherit.py` | NO_CHANGE | RP-01-E013 | Logistics |
| `plasticos_logistics/models/transaction_inherit.py` | EDIT | RP-01-E002 | Logistics |
| `plasticos_logistics/report/report_bol_delivery.xml` | EDIT | RP-03-E009 | Logistics |
| `plasticos_logistics/report/report_bol_pickup.xml` | EDIT | RP-03-E008 | Logistics |
| `plasticos_logistics/report/report_delivery_order.xml` | EDIT | RP-03-E007 | Logistics |
| `plasticos_logistics/security/ir.model.access.csv` | EDIT | RP-02-E004 | Logistics |
| `plasticos_logistics/security/record_rules.xml` | EDIT | RP-02-E005 | Logistics |
| `plasticos_logistics/services/freight_context.py` | EDIT | RP-01-E004 | Logistics |
| `plasticos_logistics/services/freight_history.py` | NO_CHANGE | RP-01-E006 | Logistics |
| `plasticos_logistics/services/sal_resolver.py` | EDIT | RP-01-E005 | Logistics |
| `plasticos_logistics/services/state_machine.py` | NO_CHANGE | RP-03-E004 | Logistics |
| `plasticos_logistics/tests/__init__.py` | EDIT | RP-07-E014 | Logistics |
| `plasticos_logistics/tests/test_export_release_guards.py` | CREATE | RP-03-E016 | Logistics |
| `plasticos_logistics/tests/test_iso_journey.py` | CREATE | RP-02-E007 | Logistics |
| `plasticos_logistics/tests/test_linda_booking_source.py` | CREATE | RP-04-E008 | Linda |
| `plasticos_logistics/tests/test_linda_freight_models.py` | EDIT | RP-03-E020 | Linda |
| `plasticos_logistics/tests/test_linda_inbound.py` | EDIT | RP-04-E009 | Linda |
| `plasticos_logistics/tests/test_load_cardinality.py` | EDIT | RP-07-E015 | Logistics |
| `plasticos_logistics/views/iso_journey_views.xml` | CREATE | RP-02-E002 | Logistics |
| `plasticos_logistics/views/load_dashboard_views.xml` | NO_CHANGE | RP-06-E005 | Logistics |
| `plasticos_logistics/views/load_views.xml` | EDIT | RP-03-E021 | Logistics |
| `plasticos_logistics/wizards/load_bulk_update_wizard.py` | NO_CHANGE | RP-03-E003 | Logistics |
| `plasticos_material_profile/__manifest__.py` | NO_CHANGE | RP-07-E069 | Material Profile |
| `plasticos_material_profile/models/material_normalizer.py` | NO_CHANGE | RP-07-E027 | Material Profile |
| `plasticos_material_profile/tests/test_material_normalizer.py` | NO_CHANGE | RP-07-E070 | Material Profile |
| `plasticos_security_base/__init__.py` | NO_CHANGE | RP-07-E019 | Security |
| `plasticos_security_base/__manifest__.py` | EDIT | RP-07-E004 | Security |
| `plasticos_security_base/migrations/19.0.1.2.22/post-migrate.py` | NO_ADD | RP-07-E013 | Security |
| `plasticos_security_base/migrations/19.0.1.2.22/pre-migrate.py` | CREATE | RP-07-E012 | Security |
| `plasticos_security_base/security/ir.model.access.csv` | EDIT | RP-06-E003 | Security |
| `plasticos_security_base/security/record_rules.xml` | EDIT | RP-06-E001 | Security |
| `plasticos_security_base/security/security_groups.xml` | NO_CHANGE | RP-07-E075 | Security |
| `plasticos_security_base/tests/test_action_methods.py` | EDIT | RP-07-E087 | plasticos_security_base |
| `plasticos_security_base/tests/test_bridge_contracts.py` | EDIT | RP-06-E002 | Security |
| `plasticos_transaction/__manifest__.py` | NO_CHANGE | RP-07-E030 | Transaction |
| `plasticos_transaction/models/native_document_import.py` | NO_CHANGE | RP-07-E079 | Transaction |
| `plasticos_transaction/models/transaction.py` | NO_CHANGE | RP-01-E010, RP-03-E022 | Transaction |
| `plasticos_transaction/models/transaction_bridge.py` | NO_CHANGE | RP-01-E012 | Transaction |
| `plasticos_transaction/models/transaction_line.py` | NO_CHANGE | RP-01-E011 | Transaction |
| `plasticos_transaction/tests/__init__.py` | NO_CHANGE | RP-07-E103 | plasticos_transaction |
| `plasticos_transaction/tests/test_compliance_does_not_post.py` | NO_CHANGE | RP-07-E102 | plasticos_transaction |
| `runtime:database-configured-actions-and-upgrade-census` | BLOCKED | RP-07-E082 | Integration |
| `runtime:installed-Odoo19-Enterprise-registry` | BLOCKED | RP-07-E081 | Native Odoo |
| `scripts/check_module_wiring.py` | NO_CHANGE | RP-07-E033 | Integration |
| `scripts/get_odoo_module_order.py` | NO_CHANGE | RP-07-E073 | Integration |
| `scripts/run-odoo-tests.sh` | NO_ADD | RP-07-E089 | Integration |
| `scripts/test_env.sh` | EDIT | RP-07-E083 | Integration |
| `tests/test_freight_context_service.py` | EDIT | RP-07-E080 | Integration |
| `tests/test_test_env_safety.py` | EDIT | RP-07-E084 | Integration |

## Effect-level accountable decisions

Every entry supplies the actual/proposed owner surface, source basis, before/after meaning, migration and recovery obligation, and verification. These are selected **technical planning decisions**, not evidence of completed implementation or approval by a fictional person.

### RP-01

#### RP-01-E001 | EDIT | `plasticos_logistics/models/load.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/load.py#L43-L46. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Stored company is related to SO; create chooses first matching SO transaction.

**Decision:** Use explicit source-proven company, immutable after acceptance. Preserve valid existing transaction.load_id pairs. Auto-associate only one eligible unlinked transaction for the exact SO with matching company/source; zero or multiple eligible candidates leaves the real load unlinked and creates one internal review activity. No first-match choice. All create/write/import/copy and helper paths use the same validation. The load remains real even without SO or transaction; no fake counterpart.

**Basis:** The load owns physical company; the transaction remains the commercial owner. See C01 for exact authority and migration rules.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** buyerless PO / multi-company / two transactions same SO / domestic SO positive (V01, V03, V16; NOT_RUN).

#### RP-01-E002 | EDIT | `plasticos_logistics/models/transaction_inherit.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/transaction_inherit.py#L8-L62. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** UNIQUE(transaction.load_id), constraint requires supplier and buyer for all linked loads.

**Decision:** Keep UNIQUE(transaction.load_id). Replace blanket supplier-and-buyer requirement with route-specific source-authority checks. For an actual sale-backed pair require the real buyer; for PO-only/owned-custody movement require proven company/source and permit absent buyer. Do not require a fictitious supplier on owned-stock fulfillment. Exact PO/SO companies must agree with the load; no new transaction-to-many-load relation.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** buyerless source positive, sale-backed buyer required, duplicate load negative, no new tx cardinality (V01, V03, V16; NOT_RUN).

#### RP-01-E003 | EDIT | `plasticos_logistics/models/freight_governance.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/freight_governance.py#L30-L61. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Freight evidence derives company via SO or fallback current env.company.

**Decision:** Remove env.company fallback for authoritative freight writes. Validate an existing load company and every actual PO/SO reference; accepted audit history remains immutable. Extend existing event facts for attributable actual pickup/delivery time and source attachment, without creating an event store. Existing company-less/contradictory records are migration exceptions, never defaulted to the migration user.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** cross-company attempt negative, freight evidence source-company equal, legacy positives (V01, V03, V16; NOT_RUN).

#### RP-01-E004 | EDIT | `plasticos_logistics/services/freight_context.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/services/freight_context.py#L51-L96. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Repeat context assumes transaction intake and may emit equipment_class=None.

**Decision:** Keep the legacy v3 builder byte-compatible for unchanged legacy intake-backed freight contexts. Add a separately versioned buyerless/manual context branch with exact company, origin/destination physical snapshot, reference weight, sourced equipment or explicit unknown, and repeat_stream absent. Manual confirmation uses the appropriate branch; missing repeat stream alone must not block an otherwise authorized manual rate. Version selection and stale checks must use the recorded context version, never silently rehash accepted v3 provenance.

**Basis:** Manual freight currently shares an intake-dependent context with SAL. Legitimate buyerless manual freight otherwise remains impossible. A new branch is an implementation of existing manual/route independence, not a new pricing engine.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V03: valid buyerless manual rate with no intake; SAL abstains; unchanged v3 positive/digest golden; changed lane/equipment invalidates only its authorization. (V01, V03, V16; NOT_RUN).

#### RP-01-E005 | EDIT | `plasticos_logistics/services/sal_resolver.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/services/sal_resolver.py#L25-L81. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Requires exact intake repeat stream and company; returns no qualification if missing.

**Decision:** Keep SAL restricted to its admitted exact intake repeat stream. Explicitly return not_eligible for a buyerless/manual context without that stream before searching historical candidates. Never allow a None stream to match all no-intake records. Preserve legacy v3 eligibility and existing source-company filters.

**Basis:** A context may now be valid for manual confirmation while ineligible for repeat-rate reuse. This consumer needs an explicit branch, not a blanket no-change assertion.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V03: no-intake manual context returns not_eligible; valid legacy intake SAL still qualifies; unknown equipment is never treated as a known different equipment match. (V01, V03, V16; NOT_RUN).

#### RP-01-E006 | NO_CHANGE | `plasticos_logistics/services/freight_history.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/services/freight_history.py#L13-L66. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing comparisons company-local, with load lane and selected receipts.

**Decision:** Keep reads from real load and company; no infer market freight from booking alone; recheck after company migration.

**Basis:** Source reads load.company_id and SO fallback, which remains valid for old SO backed records; nullable company newly refused.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** company filter negative; no claimed history when no comparable source (V01, V03, V16; NOT_RUN).

#### RP-01-E007 | NO_CHANGE | `plasticos_logistics/models/freight_quote.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/freight_quote.py#L22-L27. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** RFQ episode requires load.transaction_id and proven company.

**Decision:** Leave RFQ inapplicable for legitimate buyerless/no-transaction movements in Phase 1; do not create fake transaction for an RFQ.

**Basis:** Explicit scope exclusion: user requested no universal buyerless freight tender; existing RFQ requires transaction.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** RFQ no-transaction fails with clear not-eligible; normal transaction RFQ succeeds (V01, V03, V16; NOT_RUN).

#### RP-01-E008 | NO_CHANGE | `plasticos_logistics/models/rate_memory.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/rate_memory.py#L64-L85. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Rate memory resolves company from canonical source load or SO.

**Decision:** Keep existing transaction/load-only rate memory; no synthetic data from container slots.

**Basis:** Current source uses load.company_id first; legacy SO fallback can remain only for legacy valid records.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** source company exact on inherited SO and new standalone load; no cross-company reuse (V01, V03, V16; NOT_RUN).

#### RP-01-E009 | NO_CHANGE | `plasticos_logistics/models/freight_estimate.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/freight_estimate.py#L77-L125. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Immutable freight estimates with sourced company and fixed provenance.

**Decision:** Preserve estimate model and no new export-specific valuation; do not generate from unproven load context.

**Basis:** No new estimate writer required for Phase 1 booking logistics.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** existing immutable estimation tests and no cross-company observation (V01, V03, V16; NOT_RUN).

#### RP-01-E010 | NO_CHANGE | `plasticos_transaction/models/transaction.py`

**Owner / stage:** Transaction; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/models/transaction.py#L40-L62. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Buyer is already optional; native SO/PO links remain commercial fact owner.

**Decision:** Keep commercial transaction identity and money/weight truth unchanged; Logistics must not rewrite commercial status to simulate movement.

**Basis:** Physical J1/J2 is separate from commercial transaction; existing buyer_id nullable.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-TX: preserve old transaction monetary and partner state; clone restore on mutation error.

**Verification:** PO-only native flow, one SO multi-load, no fake AR/AP/price effects (V01, V03, V16; NOT_RUN).

#### RP-01-E011 | NO_CHANGE | `plasticos_transaction/models/transaction_line.py`

**Owner / stage:** Transaction; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/models/transaction_line.py#L1-L100. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** container_no denotes legacy packaging/source text, not stable ISO journey identity.

**Decision:** Keep legacy string; never migrate its value to physical J1 without external exact proof.

**Basis:** Physical subject identity is new Logistics J1, not transaction-line packaging.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-TX: preserve old transaction monetary and partner state; clone restore on mutation error.

**Verification:** duplicate packaging values do not collapse journeys; old transaction line display unchanged (V01, V03, V16; NOT_RUN).

#### RP-01-E012 | NO_CHANGE | `plasticos_transaction/models/transaction_bridge.py`

**Owner / stage:** Transaction; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/models/transaction_bridge.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** The inspected transaction_bridge.py only adds intake_id and action_view_intake navigation; it is not the commercial order compiler.

**Decision:** Keep the intake relation and navigation unchanged. Export never creates an intake or transaction to manufacture eligibility; exact load linkage is handled in Logistics.

**Basis:** Corrects the earlier inaccurate source description. No field, method, or inverse relation in this bridge changes.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-TX: preserve old transaction monetary and partner state; clone restore on mutation error.

**Verification:** SO auto-transaction smoke, no new buyerless synthetic SO or transaction (V01, V03, V16; NOT_RUN).

#### RP-01-E013 | NO_CHANGE | `plasticos_logistics/models/sale_order_inherit.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/sale_order_inherit.py#L20-L84. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** action_create_load opens a form with default_sale_order_id; it does not create a load on SO confirmation. Other methods own existing SO issuance/cancellation.

**Decision:** Leave this form action and order-release methods unchanged. The future load.create derives company from that exact SO and only binds a uniquely eligible transaction. Buyerless entry uses the Logistics form, not a fabricated SO.

**Basis:** Source-inspected form context reaches the changed owner create method; no duplicate logic in the Sales bridge.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V01/V07: form opens correct SO; zero/one/two eligible transactions handled by load.create; PO/SO releases unchanged. (V01, V03, V16; NOT_RUN).

#### RP-01-E014 | NO_CHANGE | `plasticos_logistics/models/purchase_order_inherit.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/purchase_order_inherit.py#L20-L57. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** PO approval controls Linda PO issue and native procurement state.

**Decision:** Preserve independent supplier PO issuance before booking; no booking auto-reissue of PO.

**Basis:** Owner dependency is already PO/Logistics; Export never changes native purchase commitment.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** PO 1 to many independent weekly bookings; no duplicate PO send (V01, V03, V16; NOT_RUN).

#### RP-01-E015 | EDIT | `plasticos_logistics/models/load.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/load.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing dispatched_at/delivered_at are transition times; no independent actual pickup evidence clock is supplied.

**Decision:** Add guarded actual_pickup_at and actual_delivery_at timestamps with exact original/evidence association and correction reason retained in existing freight event facts. State-only changes never populate these actual timestamps. Legacy workflow timestamps remain unchanged; historical event time is populated only from exact attested evidence.

**Basis:** Actual pickup is not dispatch and operator entry time is not observed delivery. Required document clocks must not manufacture an event.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V10: delayed manual entry preserves actual time; missing evidence leaves deadline unknown; correction is attributable and does not duplicate notices. (V01, V03, V16; NOT_RUN).

### RP-02

#### RP-02-E001 | CREATE | `plasticos_logistics/models/iso_journey.py`

**Owner / stage:** Logistics; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No source-owned stable ISO journey/provenance model installed.

**Decision:** Define J1 physical identity and J2 typed-source association in same file, stable company/occurrence/source-cycle key; no stock ledger, no automatic status from booking.

**Basis:** Necessary physical identity: two feeders to one ISO, FAS with no load.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** two feeder sources one ISO, one feeder two journeys, same ISO another voyage, no booking, company mismatch (V02, V05, V18; NOT_RUN).

#### RP-02-E002 | CREATE | `plasticos_logistics/views/iso_journey_views.xml`

**Owner / stage:** Logistics; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No operator J1 form for real FAS or third-party movement.

**Decision:** Minimal list/form of physical journey and attributable source with review-state; no fake load/stock transaction.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** FAS/manual company-scoped operator UX, ACL negatives (V02, V05, V18; NOT_RUN).

#### RP-02-E003 | EDIT | `plasticos_logistics/models/__init__.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Imports existing logistics model set.

**Decision:** Register iso_journey model before dependent UI and SQL model consumers; preserve load_dashboard-last import sequence.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** fresh registry init and existing load dashboard view build (V02, V05, V18; NOT_RUN).

#### RP-02-E004 | EDIT | `plasticos_logistics/security/ir.model.access.csv`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/security/ir.model.access.csv. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing Load and Linda ACLs, no J1/J2 grants.

**Decision:** Register J1/J2 model permissions without granting base.group_user universal create/write/delete. Logistics can grant base.group_system controlled administration locally. Actual business-role ACL rows belong in downstream Security Base, which already depends on Logistics; accepted J1/J2 deletion is rejected by the model even for a broadly granted role.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** normal operator read, elevated write, global-user denied unauthorized edit (V02, V05, V18; NOT_RUN).

#### RP-02-E005 | EDIT | `plasticos_logistics/security/record_rules.xml`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/security/record_rules.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing company scoped freight/Linda rules; no J1/J2 global controls.

**Decision:** Add global company filters to J1/J2 and explicitly validate journey/source company equality on create/write/accept. No company-null escape. Keep role grants out of this upstream module when their group owner is Security Base. Use restrict rather than destructive cascade for accepted evidence references.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** cross-company source association negative and allowed company read (V02, V05, V18; NOT_RUN).

#### RP-02-E006 | NO_CHANGE | `plasticos_logistics/data/sequence.xml`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/data/sequence.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing sequences for load/freight identities.

**Decision:** Use stable source-cycle key and database PK for J1; do not invent a second display sequence unless operator requires one.

**Basis:** J1 requires stable identity, not extra operator sequence; E1/E3 remains separate.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** two journeys same container no collision, repeat operation idempotent (V02, V05, V18; NOT_RUN).

#### RP-02-E007 | CREATE | `plasticos_logistics/tests/test_iso_journey.py`

**Owner / stage:** Logistics; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No tests of J1/J2 yet.

**Decision:** Add precise Odoo TransactionCase J1/J2 cardinality, provenance, idempotency, multi-company, FAS without stock.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** J1/J2 positive negative and concurrency tests in Enterprise fixture (V02, V05, V18; NOT_RUN).

#### RP-02-E008 | NO_CHANGE | `native:stock.move.line`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Odoo Stock is authoritative for actual company-owned movement quantities.

**Decision:** Read native move-line in J2/E4 where genuinely executed; no custom stock move or fake picking.

**Basis:** Read-only consumer contract pending installed Odoo 19 EE field proof.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** real owned-stock execution and supplier FAS without picking (V02, V05, V18; NOT_RUN).

#### RP-02-E009 | NO_CHANGE | `native:purchase.order.line`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Native PO lines own supplier order economics and purchasing quantities.

**Decision:** Keep source line canonical; J2 references physical execution, not PO as arrival proof.

**Basis:** Keep source line canonical; J2 references physical execution, not PO as arrival proof. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** one PO four physical journeys, no cloned PO and no invoice amount rewrite (V02, V05, V18; NOT_RUN).

#### RP-02-E010 | NO_CHANGE | `native:sale.order.line`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Native SO line owns buyer commitment but may be absent at physical receipt.

**Decision:** Do not require SO for buyerless physical journey; bind later actual SO through Export E4 only with evidence.

**Basis:** Do not require SO for buyerless physical journey; bind later actual SO through Export E4 only with evidence. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** new sale after ocean loading, no history rewrite (V02, V05, V18; NOT_RUN).

#### RP-02-E011 | NO_CHANGE | `native:ir.attachment`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Native attachment belongs to exact retained original; no custom binary needed.

**Decision:** J2 attribution points to exact attachment with authorized source and company; no original duplication.

**Basis:** J2 attribution points to exact attachment with authorized source and company; no original duplication. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** one original several associations without binary duplication (V02, V05, V18; NOT_RUN).

### RP-03

#### RP-03-E001 | EDIT | `plasticos_logistics/models/load.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/load.py#L43-L46. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** action_dispatch, _transition, direct/composer sends and a T+4h resend cron have distinct paths.

**Decision:** Apply the frozen physical-operation guard at every release path, including _transition, direct actions, composer handoff, native mail claim and ACK jobs. Separate permission to issue a NEW instruction from recording an already-observed physical event: a rolled booking blocks new release, not truthful evidence of cargo already picked up or delivered. Replace full-packet ACK resend with Linda-owned +2h notice and +4h escalation anchored to actual sent evidence. Do not stamp sent from queueing. See C03/C04/C07 for race, audience and clock semantics.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** direct dispatch, stale roll, blind resend, concurrent hold and packet attachment tests (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E002 | EDIT | `plasticos_logistics/models/dispatch.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/dispatch.py#L14-L53. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Separate plasticos.dispatch.action_transition changes state without load._transition guard.

**Decision:** Preserve the independent dispatch graph but reject direct create/write state bypasses and call the common Logistics guard before newly releasing physical instructions. Reporting an attributable already-performed movement retains history and records any current-booking exception; it must not be erased or rewound.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** direct transition bypass negative; delivered/closed unaffected on domestic (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E003 | NO_CHANGE | `plasticos_logistics/wizards/load_bulk_update_wizard.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/wizards/load_bulk_update_wizard.py#L61-L104. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Bulk update already calls load._transition rather than writing raw state.

**Decision:** Keep as is if the new central guard is applied at load._transition; no second guard in wizard.

**Basis:** Source calls centralized _transition; duplicate guard would create inconsistent policy.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** wizard dispatch stale-booking negative, regular batch transition positive (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E004 | NO_CHANGE | `plasticos_logistics/services/state_machine.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/services/state_machine.py#L9-L27. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Defines existing Load and Dispatch transition graphs.

**Decision:** Do not add export stages to domestic state graphs; enforce booking-context hold at source owner command boundary.

**Basis:** No state explosion; Export booking revision is distinct from logistics state.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** all existing transitions unchanged and booking hold blocks only export-scoped release (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E005 | EDIT | `plasticos_logistics/models/mail_mail_inherit.py`

**Owner / stage:** Logistics; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/mail_mail_inherit.py#L22-L52. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Native outgoing mail path already uses Linda request claim and unknown outcome protection.

**Decision:** Retain the existing single-mail native transport interposer, but revalidate current source/recipient/packet under the claim transaction at the final authorization point, not only in send(). Use shared lock ordering with booking revision acceptance. A durable claim is the logical send authorization; a later revision treats that request as in-flight/history and cannot unsend it. Unknown provider outcomes remain unknown and never auto-retry. Ordinary mail is not intercepted.

**Basis:** The queued-row claim checks attempt count but not source revision. A previous pre-send check alone is racy. This is one narrow correction in the existing sender, not a second transport.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V06: revision-before-claim prevents SMTP; claim-before-revision keeps immutable prior request and a scoped follow-up hold; two workers one claim; unknown is never replayed. (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E006 | EDIT | `plasticos_logistics/data/cron.xml`

**Owner / stage:** Logistics; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/data/cron.xml#L15-L24. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Acknowledgment cron is active on a FOUR-HOUR interval, incompatible with T+2h reminder.

**Decision:** Change only the ACK job cadence to five-minute due polling; evaluate +2h/+4h on actual successful send time, with one purpose/recipient/revision obligation per touch. Preserve other cron definitions. Preserve activation state across upgrade and keep the rehearsal entirely neutralized; never use a data-file update to enable a previously disabled job. No hard wall-clock guarantee beyond measured poll/worker delay; overdue work remains observable.

**Basis:** Source owner BRS requires 2h reminder/4h escalation; 4h poll cannot implement it. Alternative event scheduling only via separate owner decision after EE native API proof.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V10/V19: no early sends; one due obligation per purpose despite repeated polls; known lag; active=False remains false; no full packet attachments in notices. (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E007 | EDIT | `plasticos_logistics/report/report_delivery_order.xml`

**Owner / stage:** Logistics; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/report/report_delivery_order.xml#L32-L40. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Source company/header dereferences doc.sale_order_id.company_id.

**Decision:** Render source-company-safe carrier paperwork from load.company_id and actual party; no sale-buyer details when absent.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** buyerless PO-only QWeb, domestic exact golden PDF, wrong-company negative (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E008 | EDIT | `plasticos_logistics/report/report_bol_pickup.xml`

**Owner / stage:** Logistics; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/report/report_bol_pickup.xml#L56-L75. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Source party/company dereferences SO-derived company.

**Decision:** Use source-owned load.company_id for company identity; preserve actual pickup partner and BOL source.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** buyerless pickup and existing domestic PDF unchanged (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E009 | EDIT | `plasticos_logistics/report/report_bol_delivery.xml`

**Owner / stage:** Logistics; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/report/report_bol_delivery.xml#L56-L90. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Source party/company dereferences SO-derived company.

**Decision:** Use source-owned load.company_id, actual delivery party, no fabricated end buyer.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** terminal destination BOL and domestic PDF golden (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E010 | EDIT | `plasticos_automation/data/email_templates.xml`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/data/email_templates.xml#L110-L305. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Carrier packet/three mail templates read object.sale_order_id.company_id for from, contact and disclaimers.

**Decision:** Switch carrier templates to exact load.company_id with intentional no-SO display, never infer carrier recipients or economics.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-AUTO: template XML upgrade only, no data re-key; hold outbound mail during upgrade; preserve old message IDs and unknown statuses.

**Recovery:** R-MAIL: hold outbound queue, restore template XML/data via consistent DB+filestore restore; no replay of already sent messages.

**Verification:** four carrier template renderings on buyerless and sale-backed records; sender and reply-to exact (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E011 | NO_CHANGE | `plasticos_automation/data/workflow_automations.xml`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/data/workflow_automations.xml#L202-L217. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Carrier reservation automatic dispatch rule is deliberately inactive and server action is pass.

**Decision:** Preserve disabled rule and no new booking->automatic carrier dispatch.

**Basis:** Known inactive automation has no intended reachability to export release; prove no newly enabled action.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: hold outbound queue, restore template XML/data via consistent DB+filestore restore; no replay of already sent messages.

**Verification:** existing carrier-reservation-not-dispatch regression passes (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E012 | NO_CHANGE | `plasticos_automation/models/stock_picking_automation.py`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/models/stock_picking_automation.py#L34-L84. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Trucker followup uses native stock.picking and an independent cron.

**Decision:** Do not inject booking dispatch; keep native picking route out of Export for buyerless non-stock.

**Basis:** Stock-owned picking route not a physical release for FAS without picking; paired with disabled cron.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: hold outbound queue, restore template XML/data via consistent DB+filestore restore; no replay of already sent messages.

**Verification:** cron disabled; no accidental supplier-FAS stock event; no carrier packet on reservation (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E013 | NO_CHANGE | `plasticos_automation/data/cron_trucker_followup.xml`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/data/cron_trucker_followup.xml#L5-L13. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing trucker followup scheduled action has active=False.

**Decision:** Keep disabled; do not start a second sender or appointment timer.

**Basis:** The source XML explicitly sets the legacy stock-picking trucker followup inactive. The new ACK obligation is load/Linda-request owned; no change to this disabled schedule or reactivation is needed.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: hold outbound queue, restore template XML/data via consistent DB+filestore restore; no replay of already sent messages.

**Verification:** V10/V19: upgrade retains active=False; no stock reservation or reminder poll emits a second carrier notice. (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E014 | NO_CHANGE | `plasticos_automation/tests/test_carrier_reservation_not_dispatch.py`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/tests/test_carrier_reservation_not_dispatch.py#L1-L61. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing regression checks disabled native reservation action.

**Decision:** Preserve test as a mandatory guard; no weakening its assertions.

**Basis:** This regression already asserts the disabled legacy dispatch action is inert and a reserved stock picking does not send or stamp dispatch. That acceptance expectation is preserved unchanged; new guarded load/booking tests complement rather than weaken it.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** unchanged regression on final installed module graph (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E015 | CREATE | `plasticos_automation/tests/test_buyerless_carrier_templates.py`

**Owner / stage:** Automation; S4. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No negative QWeb/email identity regression for buyerless load.

**Decision:** Test mail.template rendering and no unsolicited SMTP for buyerless SO-less record.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** sender identity, attachment accuracy, no first-transmission on upgrade (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E016 | CREATE | `plasticos_logistics/tests/test_export_release_guards.py`

**Owner / stage:** Logistics; S4. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No export booking/revision release-path test.

**Decision:** At Logistics level test the common guard with an owner-provided test override, not an import of the downstream Export addon. Exercise standalone dispatch, load._transition, wizard, direct/composer paths and actual-event reporting. Actual E1/E2 rollover tests belong in plasticos_export/tests/test_export_owner_handoff.py.

**Basis:** Avoid a reverse addon test dependency and false independence. Source-owner unit proof and downstream real composition proof are different.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** negative stale roll on each enumerated path; domestic control positives (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E017 | EDIT | `plasticos_automation/__manifest__.py`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Current version 19.0.2.1.6, template data loaded.

**Decision:** Bump selected candidate to 19.0.2.1.7 and keep mail action loading after Logistics; no new circular dependency.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-AUTO: template XML upgrade only, no data re-key; hold outbound mail during upgrade; preserve old message IDs and unknown statuses.

**Recovery:** R-MAIL: hold outbound queue, restore template XML/data via consistent DB+filestore restore; no replay of already sent messages.

**Verification:** module update + template rendering on EE, old inactive action unchanged (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E018 | EDIT | `plasticos_automation/tests/__init__.py`

**Owner / stage:** Automation; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_automation/tests/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing tests package imports known test modules.

**Decision:** Register new buyerless carrier-template test without disabling prior reservation test.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** test is collected and executed (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E019 | CREATE | `plasticos_logistics/data/linda_dispatch_ack_notice.xml`

**Owner / stage:** Linda; S4. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No source-owned load acknowledgment reminder template separate from full carrier dispatch packet.

**Decision:** Define T+2h non-packet carrier reminder and T+4h carrier+ops escalation with exact load/message identity; request instance Linda owned, queued once, current company and recipient validated.

**Basis:** The specified purpose/model needs its own native XML record at the existing semantic owner; PO/SO templates cannot safely impersonate that subject.

**Migration:** M-LINDA: extend existing booking and load-ACK request/response identity and CHECK/UNIQUE without rewriting PO/SO rows; backfill source kind for existing PO/SO; refuse ambiguous/unknown send outcomes; no automatic replay.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** mail sink proves one reminder and one escalation with no duplicate packet (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E020 | EDIT | `plasticos_logistics/tests/test_linda_freight_models.py`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/tests/test_linda_freight_models.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing Linda/Freight tests focus modeled load freight and request invariants.

**Decision:** Add load ACK source-kind, +2h and +4h due and cancellation/no-resend/unknown-send negative tests.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** time-frozen idempotent ACK reminder/escalation, stale packet and unknown outcome (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E021 | EDIT | `plasticos_logistics/views/load_views.xml`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/views/load_views.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Current form is sale-oriented and has actions for freight and four packet composers.

**Decision:** Expose exact source company, route provenance, actual-event evidence and governed carrier actions without requiring an SO. Preserve domestic visibility. Do not add a second sender or editable accepted-history controls.

**Basis:** Manual/paperwork operation needs a real entry surface for the planned fields and guarded actions.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V01/V04/V10: buyerless form works; ordinary user cannot bypass guard through editable fields; domestic form controls preserved. (V04, V06, V10, V19; NOT_RUN).

#### RP-03-E022 | NO_CHANGE | `plasticos_transaction/models/transaction.py`

**Owner / stage:** Transaction; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/models/transaction.py#L1269-L1402. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Supplier followup and delivery-order cron iterate existing commercial transactions; DO cron may confirm a real draft PO and choose an existing picking. The merged compliance compute is now observational and its no-post test must remain intact.

**Decision:** Export/J1/J2 and migration never synthesize a transaction, stamp its supplier confirmation or move its commercial state. Therefore Export does not enroll new records into these existing cron populations. Preserve this implementation; retain a negative witness and record unrelated first-picking policy debt separately.

**Basis:** Exact method inspection bounds the changed population. This exclusion is not a claim that the legacy DO algorithm is globally correct.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V18/V19: accepting booking/physical evidence creates no new transaction, PO confirmation or stock picking; existing domestic controls unchanged. (V04, V06, V10, V19; NOT_RUN).

### RP-04

#### RP-04-E001 | EDIT | `plasticos_logistics/models/linda_request.py`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/linda_request.py#L121-L150. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Request purpose, CHECK, UNIQUE and _source_order only support PO and SO.

**Decision:** Extend the existing Linda request with exact typed source-kind/id/revision, purpose and immutable audience/render snapshot per C04. Preserve PO/SO fields and their branch CHECK/uniqueness. For booking requests resolve the source only through an Export-provided normal _inherit hook; unavailable resolver returns not_available. No upstream Export FK/import. Add load packet/ACK and document-chase obligations on their actual existing source types; source revision, company, recipient and business identity define dedupe, not an email timestamp.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LINDA: extend existing booking and load-ACK request/response identity and CHECK/UNIQUE without rewriting PO/SO rows; backfill source kind for existing PO/SO; refuse ambiguous/unknown send outcomes; no automatic replay.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** existing PO/SO issue/cancel preserved; booking issue/roll/cancel idempotent; unknown outcome cannot resend (V06, V07, V10; NOT_RUN).

#### RP-04-E002 | EDIT | `plasticos_logistics/models/linda_response.py`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/linda_response.py#L40. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Reply CHECK and native routing require exactly one SO or PO.

**Decision:** Retain the original inbound message and attributable ancestry. Add typed source branches to the current request/response path, preserving PO/SO CHECKs in their branches. Booking model resolution is supplied by the downstream Export hook. A From match is not authentication; inbound text is candidate evidence, not accepted booking terms, READY, verification, stock or payment.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LINDA: extend existing booking and load-ACK request/response identity and CHECK/UNIQUE without rewriting PO/SO rows; backfill source kind for existing PO/SO; refuse ambiguous/unknown send outcomes; no automatic replay.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** booking inbound exact ancestry and wrong-party/forward/duplicate negative (V06, V07, V10; NOT_RUN).

#### RP-04-E003 | NO_CHANGE | `plasticos_logistics/data/linda_inbound_ai.xml`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/data/linda_inbound_ai.xml#L15-L28. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Inbound base.automation matches only mail.message.model purchase.order and sale.order.

**Decision:** Preserve the upstream PO/SO-only base.automation filter. Install the booking-only mail.message trigger in plasticos_export/data/linda_booking_inbound.xml and route to the SAME Linda response owner via an Export _inherit source resolver. Mutually exclusive target filters plus existing Message-ID dedupe prevent double processing.

**Basis:** Upstream XML must not require the downstream Export model. The requested booking reachability is realized explicitly downstream rather than changing the base filter.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** V07: real booking reply reaches Linda once with original retained; PO/SO still once; uninstall/absence of Export leaves upstream install valid. (V06, V07, V10; NOT_RUN).

#### RP-04-E004 | CREATE | `plasticos_logistics/data/linda_booking_mail_template.xml`

**Owner / stage:** Linda; S4. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No separate booking issue/amend/cancel mail template.

**Decision:** Define booking issue/amend/cancel native mail templates on plasticos.logistics.request, not plasticos.export.booking. Render only the immutable audience-safe request snapshot prepared from an accepted revision by the Export source resolver. Explicit template IDs registered in the Logistics manifest. Missing source, currentness or audience evidence withholds rather than fabricating content.

**Basis:** The specified purpose/model needs its own native XML record at the existing semantic owner; PO/SO templates cannot safely impersonate that subject.

**Migration:** M-LINDA: extend existing booking and load-ACK request/response identity and CHECK/UNIQUE without rewriting PO/SO rows; backfill source kind for existing PO/SO; refuse ambiguous/unknown send outcomes; no automatic replay.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** recipient/attachment redaction and stale dispatch withheld; mail sink (V06, V07, V10; NOT_RUN).

#### RP-04-E005 | NO_CHANGE | `plasticos_logistics/data/linda_po_mail_template.xml`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/data/linda_po_mail_template.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Native order-issued PO template has its own source and purpose.

**Decision:** Preserve PO issuance unaffected by independent booking rolls.

**Basis:** The template is a released purchase.order artifact with the exact supplier audience and supported native report. Booking mail renders a Linda request, not this PO template; no field or source semantics used by this template changes.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** old PO revision and dedupe tests; booking does not cause PO reissue (V06, V07, V10; NOT_RUN).

#### RP-04-E006 | NO_CHANGE | `plasticos_logistics/data/linda_so_mail_template.xml`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/data/linda_so_mail_template.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Native SO issuance template exists and binds own original.

**Decision:** Preserve SO path, including optional buyer arriving later.

**Basis:** The template is a released sale.order artifact and buyer audience. Booking/J1 changes neither its receiver model nor native commercial release or payload. Linda retains its PO/SO branches; no template rewrite is needed.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** SO original identity and no duplicate after booking amendment (V06, V07, V10; NOT_RUN).

#### RP-04-E007 | NO_CHANGE | `plasticos_logistics/data/linda_order_cancel_mail_templates.xml`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/data/linda_order_cancel_mail_templates.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** PO/SO cancellations use existing order cancellation templates.

**Decision:** Keep PO/SO cancellation semantics; booking change uses new booking template.

**Basis:** The two cancellation templates remain per-original PO/SO cycle and original audience. A booking revision is not native order cancellation, so reuse or expansion would conflate distinct obligations.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** PO/SO cancel remains exact and duplicate-safe (V06, V07, V10; NOT_RUN).

#### RP-04-E008 | CREATE | `plasticos_logistics/tests/test_linda_booking_source.py`

**Owner / stage:** Linda; S4. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No booking-source Linda request/response tests.

**Decision:** Base Logistics tests validate typed request CHECKs/dedupe/unknown outcomes using a deliberately registered in-test source resolver. Real Export E1 message processing is exercised only in the downstream Export test suite. Tests must prove the resolver is NOT available when Export is absent, not bypass that failure.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** five negative tests: duplicate, stale, unauthenticated, uncertain SMTP, wrong audience (V06, V07, V10; NOT_RUN).

#### RP-04-E009 | EDIT | `plasticos_logistics/tests/test_linda_inbound.py`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/tests/test_linda_inbound.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing PO/SO inbound test harness with controlled mail sink.

**Decision:** Preserve existing PO/SO inbound tests and original retention/unauthenticated cases. Add branch-level negative tests for an unregistered source kind. Real booking model routing belongs to the downstream Export suite and must not be imported into the upstream addon.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** PO/SO test set plus booking target delivered by automation (V06, V07, V10; NOT_RUN).

#### RP-04-E010 | EDIT | `plasticos_logistics/models/mail_mail_inherit.py`

**Owner / stage:** Linda; S4. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/mail_mail_inherit.py#L22-L52. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing single-mail claim uses request row and native _send ordering.

**Decision:** Retain the existing single-mail native transport interposer, but revalidate current source/recipient/packet under the claim transaction at the final authorization point, not only in send(). Use shared lock ordering with booking revision acceptance. A durable claim is the logical send authorization; a later revision treats that request as in-flight/history and cannot unsend it. Unknown provider outcomes remain unknown and never auto-retry. Ordinary mail is not intercepted.

**Basis:** The queued-row claim checks attempt count but not source revision. A previous pre-send check alone is racy. This is one narrow correction in the existing sender, not a second transport.

**Migration:** M-LINDA: extend existing booking and load-ACK request/response identity and CHECK/UNIQUE without rewriting PO/SO rows; backfill source kind for existing PO/SO; refuse ambiguous/unknown send outcomes; no automatic replay.

**Recovery:** R-MAIL: stop queue and preserve unknown/sent mail outcomes and Message-IDs; do not resend; DB+filestore snapshot restoration after mail isolation.

**Verification:** V06: revision-before-claim prevents SMTP; claim-before-revision keeps immutable prior request and a scoped follow-up hold; two workers one claim; unknown is never replayed. (V06, V07, V10; NOT_RUN).

#### RP-04-E011 | CREATE | `plasticos_export/data/linda_booking_inbound.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json ; https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/__manifest__.py. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** No Export addon/booking-native mail trigger exists.

**Decision:** Install a booking-only native incoming mail.message automation, using the existing Linda response action/owner and exact saved native ancestry. Base PO/SO trigger stays untouched. Register this XML in Export manifest and keep external-effect behavior disabled.

**Basis:** This is the minimal downstream bridge required by F-005; avoids an upstream dependency on the Export model.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V07: one booking incoming original -> one candidate response; no PO/SO duplicate; original missing, wrong party, forward and stale all withheld. (V06, V07, V10; NOT_RUN).

#### RP-04-E012 | CREATE | `plasticos_logistics/data/linda_document_chase.xml`

**Owner / stage:** Linda; S4. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json ; https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/__manifest__.py. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** Existing document policy requires external chasers but the planned owner request kinds covered only orders/bookings/load ACK.

**Decision:** Provide one native request-targeted template for the existing supplier/carrier/buyer document obligation. Recipient, actual event clock, category and source revision are frozen in Linda request; no attachments of unrelated trade and no finance action.

**Basis:** Completes the already-required Documents -> Linda handoff, not a new campaign/sender.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V08/V10: current missing obligation sends at most once per permitted local day; clearing evidence cancels queued chase; no missing-evidence finance effect. (V06, V07, V10; NOT_RUN).

### RP-05

#### RP-05-E001 | EDIT | `plasticos_documents/models/document.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/document.py#L15-L58. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** At current HEAD the existing business document already owns guarded verification, exact association, original digest, company provenance, lifecycle/currentness and multi-subject rows over one attachment.

**Decision:** Reuse that single writer and action_associate/action_verify/action_override controls. Extend existing plasticos.document rows with explicit obligation_kind (legacy default), operation_revision_key (separate from source_revision attachment checksum), coverage_key, quantity_known and evidence_uom_id. Keep legacy row identity and API defaults unchanged. Add the frozen get_scoped_evidence_verdict facade and typed subject-resolver hooks; accepted scope fields are immutable and all create/write/import paths check the same authority. Old/new subject invalidation must include scoped changes. Never create a parallel evidence association model.

**Basis:** The newly merged source can already represent multiple exact business rows on one original. Only operation/revision distinctions are missing; another association model would duplicate the authoritative owner.

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** V08/V09: legacy association unchanged; two obligations on the same source differ by explicit operation revision; no global native Boolean or unrelated legacy compliance promotion; checksum replacement invalidates each applicable row. (V08, V09, V10; NOT_RUN).

#### RP-05-E002 | NO_ADD | `plasticos_documents/models/document_evidence_link.py`

**Owner / stage:** Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** This was an earlier proposed path. Current plasticos.document already supports exact multi-subject evidence over one original; it still needs the separately planned operation-scope dimensions.

**Decision:** Do not add models/document_evidence_link.py or a second evidence-link model. Realize its required operation scope on the existing plasticos.document rows now supplied by the merged exact-association owner. Preserve this superseded proposed path in the ledger.

**Basis:** Material source change removes the earlier irreducibility justification. The public Documents verdict signature and E1-E4/J1-J2 contract are unchanged.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** V08/V09: multi-subject/obligation/version cases use one business evidence owner and one original, with no second acceptance ledger. (V08, V09, V10; NOT_RUN).

#### RP-05-E003 | EDIT | `plasticos_documents/models/compliance_service.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/compliance_service.py#L17-L63. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current compliance filters accepted association rows through _currently_eligible and quantity coverage; RECEIVING requires one exact row and is not aggregated.

**Decision:** Reuse _currently_eligible and the existing legacy invoice/close behavior. Filter legacy callers to legacy obligation rows; add the exact company/subject/obligation/operation_revision query through the frozen document facade. Preserve the one-row RECEIVING coverage policy and do not sum partial receipts. Unknown operation or unavailable subject resolver returns not_available. No finance side effect.

**Basis:** Existing currentness and quantity checks are already implemented. The residual change is operation-specific isolation, not a replacement compliance engine.

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** invoice/close golden; missing export scoped evidence abstains; one original multi-link (V08, V09, V10; NOT_RUN).

#### RP-05-E004 | EDIT | `plasticos_documents/models/transaction_docs.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/transaction_docs.py#L59-L96. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Transaction docs cron currently computes deadlines from transaction create_date rather than actual pickup/delivery.

**Decision:** Use actual, attributable pickup/delivery timestamps, never create_date or dispatched_at substitutes. Supplier +1/+5 BD and carrier +2/+6 BD after actual pickup; buyer +1/+5 BD after actual delivery. Missing real event leaves that deadline unknown and one internal activity. Produce exact missing-obligation intents for Linda; do not add a Documents external sender. Include expiry/supersession invalidation and wrong-scope negatives.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** business-day freeze at pickup/delivery, supplier 1/5, carrier 2/6, buyer 1/5, exactly-once reminder, no export doc false positive (V08, V09, V10; NOT_RUN).

#### RP-05-E005 | NO_CHANGE | `plasticos_documents/models/document_rule.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/document_rule.py#L8-L45. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Rule table has invoice/close/dispatch flags, but no native export boolean.

**Decision:** Keep the existing rule fields and domestic tag/category grain. Resolve each known operation purpose through an explicit owner allowlist using existing required_for_invoice/close/dispatch flags; unknown purposes return not_available rather than empty-list compliant. No universal export-required Boolean.

**Basis:** A new export Boolean would duplicate obligation semantics and increase migration scope.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** invoice close flags unchanged and scoped export criterion distinct (V08, V09, V10; NOT_RUN).

#### RP-05-E006 | NO_CHANGE | `plasticos_documents/models/document_validation_matrix.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/document_validation_matrix.py#L33-L53. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Matrix indexes category+tag, domestic status.

**Decision:** No schema change; retain native domestic checks, scope Export separately by subject/revision.

**Basis:** The existing category/tag matrix has invoice/close/dispatch flags and no original, booking, revision or quantity ownership. Its unchanged domestic schema is consumed by the changed operation-scoped compliance query; adding a second Export policy matrix would duplicate that owner.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** V08/V09: legacy category/tag requirement still applies; an Export-only link or unknown purpose cannot clear domestic invoice/close. (V08, V09, V10; NOT_RUN).

#### RP-05-E007 | NO_CHANGE | `plasticos_documents/models/midnight_recompute.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/midnight_recompute.py#L17-L55. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing expiry recompute only changes expiry state on document.

**Decision:** Keep this expiry recomputation job, which updates is_expired on the original. Authoritative scoped and legacy verdicts independently compare expiry_date against the current date; correctness must not wait for a six-hour cron. Invalidation of stored display projections is handled by document.py and bridge dependencies, not a new scheduler.

**Basis:** Keep this expiry recomputation job, which updates is_expired on the original. Authoritative scoped and legacy verdicts independently compare expiry_date against the current date; correctness must not wait for a six-hour cron. Invalidation of stored display projections is handled by document.py and bridge dependencies, not a new scheduler. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** newly expired original revokes effective scoped satisfaction by next read (V08, V09, V10; NOT_RUN).

#### RP-05-E008 | NO_CHANGE | `plasticos_documents/data/cron_missing_docs.xml`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/data/cron_missing_docs.xml#L5-L13. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing six-hour missing-doc cron calls transaction_docs cron method.

**Decision:** Keep the six-hour missing-document poll. Its changed transaction_docs method creates idempotent due intents with original event clocks; Linda handles external sending. This cadence is for day-level document chasers, not the two-hour carrier ACK deadline.

**Basis:** Keep the six-hour missing-document poll. Its changed transaction_docs method creates idempotent due intents with original event clocks; Linda handles external sending. This cadence is for day-level document chasers, not the two-hour carrier ACK deadline. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** once per observed cycle, no suppression or duplicate send (V08, V09, V10; NOT_RUN).

#### RP-05-E009 | NO_CHANGE | `plasticos_documents/data/cron.xml`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/data/cron.xml#L5-L13. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Compliance audit scheduled action exists but inactive.

**Decision:** Keep inactive; do not create shadow reconciliation sender.

**Basis:** Keep inactive; do not create shadow reconciliation sender. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** inactive flag remains false on upgrade (V08, V09, V10; NOT_RUN).

#### RP-05-E010 | EDIT | `plasticos_documents/security/ir.model.access.csv`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/security/ir.model.access.csv#L2-L13. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Broad base.group_user CRUD rows remain, but current model-level grants already refuse direct verification and accepted-association writes. Residual deletion/subject visibility and scoped-role policy must be reconciled without claiming the merged writer protection is absent.

**Decision:** Narrow broad document mutation ACLs only where they bypass the existing verifier/association policy. Reuse the current plasticos.document model for scoped rows; no new-model ACL is added. Model-level accepted-decision/scope immutability remains mandatory regardless of group union.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** ordinary user direct write denied, approved manager allowed, unauthorized unlink denied (V08, V09, V10; NOT_RUN).

#### RP-05-E011 | EDIT | `plasticos_documents/security/security.xml`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/security/security.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Defines Documents group privileges; lacks scoped link company rules.

**Decision:** Use existing verifier and manager groups. Add exact subject_company_id/subject-access isolation for accepted scoped rows and preserve restricted pending Inbox workflows; no new evidence-model group or signature role. Do not make all company-null pending originals globally visible.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** cross-company link CRUD denied and manager authorizations correct (V08, V09, V10; NOT_RUN).

#### RP-05-E012 | EDIT | `plasticos_documents/views/document_views.xml`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/views/document_views.xml#L62-L100. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current form already offers guarded exact association, verify/override and provenance controls.

**Decision:** Extend that owner form with operation obligation/revision/coverage/UoM and per-scope status, keeping the existing legacy defaults and decision guards. No second original UI, direct editable acceptance flags or native Boolean aggregate.

**Basis:** Only missing operation scope is added to the existing authoring surface.

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** operator original -> link -> scope review; no read leak (V08, V09, V10; NOT_RUN).

#### RP-05-E013 | NO_CHANGE | `plasticos_documents/models/__init__.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Registers old Docs models and bridge.

**Decision:** Keep existing model imports unchanged: all new scope semantics live in the already-imported document.py and compliance_service.py. Do not register a retired parallel evidence-link model.

**Basis:** No new production Python file in this module is necessary after the source rebind.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** V12: new fields/methods load through existing imports; no stale document_evidence_link import. (V08, V09, V10; NOT_RUN).

#### RP-05-E014 | CREATE | `plasticos_documents/tests/test_scoped_evidence.py`

**Owner / stage:** Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No typed-scoped-evidence test.

**Decision:** Add operation-scoped cases on plasticos.document while retaining the newly merged exact-association/writer/regression suites. Cover independent obligation/revision, known versus unknown quantity, UoM, source ownership, scope immutability, currentness and no claims/finance contamination.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** current/revoked/expired, cross-company, two operations, no duplicate original (V08, V09, V10; NOT_RUN).

#### RP-05-E015 | EDIT | `plasticos_documents/tests/test_compliance_service.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/test_compliance_service.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing invoice/close compatibility tests.

**Decision:** Add proof that invoice/close behavior is unaffected while scoped Export does not contaminate.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** existing positive/negative tests and new operation test pass (V08, V09, V10; NOT_RUN).

#### RP-05-E016 | EDIT | `plasticos_documents/tests/__init__.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/__init__.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Registers current compliance test modules.

**Decision:** Import test_scoped_evidence without changing earlier tests.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** test runner discovers new test (V08, V09, V10; NOT_RUN).

#### RP-05-E017 | EDIT | `plasticos_documents_native/models/document_native.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/models/document_native.py#L30-L42. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current Native model already projects business decisions, refuses direct writes, delegates actions, rejects ambiguous multi-row bindings, and leaves partner-only sources unlinked.

**Decision:** Preserve those merged behaviors. Narrow exact projection and positive-search predicates to the legacy obligation scope so a sole operation-specific row cannot masquerade as global native verification. Multi-row originals remain ambiguous at the native Boolean and decisions are made on exact Documents rows. Do not rewrite delegation, historical snapshots or search-complement parity.

**Basis:** The original one-writer/recency defect is already source-corrected. The only new consequence is the new operation discriminator on the existing business row.

**Migration:** M-NATIVE: compare native and business flags, source attachment identity and conflicting links; preserve native originals, do not promote native unverified flags or recency guesses.

**Recovery:** R-DOC: restore DB+filestore originals and reconcile sync direction; no unproven verified bit promotion.

**Verification:** V08/V09: one legacy row still projects; one operation-only row does not; multiple rows remain ambiguous; positive/negative native search matches computation. (V08, V09, V10; NOT_RUN).

#### RP-05-E018 | NO_CHANGE | `plasticos_documents_native/models/document_sync.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/models/document_sync.py#L47-L144. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current sync creates or returns a pending exact-original shell, leaves verification untouched, retains existing links and schedules at most one internal review activity.

**Decision:** Keep this sync unchanged. New operation rows are authored by the Documents owner, never by native sync; legacy-default pending shells stay unaccepted until the existing command. No native flag is copied back into business decisions.

**Basis:** Current source already satisfies the one-way custody and no-acceptance boundary. Adding scope fields with legacy defaults does not change sync inputs or writes.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore originals and reconcile sync direction; no unproven verified bit promotion.

**Verification:** V08/V09: repeated sync after multiple scope rows neither duplicates original nor changes accepted scope/verification; no new external mail. (V08, V09, V10; NOT_RUN).

#### RP-05-E019 | NO_CHANGE | `plasticos_documents_native/views/document_native_views.xml`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/views/document_native_views.xml#L11-L44. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current native form actions delegate and verification/actor/time/override fields are read-only; exact-association fields remain legacy.

**Decision:** Retain native UI unchanged. New operation scope is inspected/edited in the authoritative Documents form. Do not add another native authoring form or duplicate scope fields.

**Basis:** The current native UI already respects one writer. The narrowed model projection supplies the required truthful read-only behavior without XML changes.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore originals and reconcile sync direction; no unproven verified bit promotion.

**Verification:** non-manager manual flags cannot satisfy export compliance; Odoo 19 EE view renders (V08, V09, V10; NOT_RUN).

#### RP-05-E020 | NO_CHANGE | `plasticos_documents_native/tests/__init__.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/tests/__init__.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** tests/__init__.py already exists and imports test_native_search_parity plus test_verification_delegation.

**Decision:** Retain the two current imports; extend those existing suites for operation-scope projection rather than adding another test module.

**Basis:** The merged source now supplies the test loader and appropriate test homes.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V12: both existing suites are collected and execute operation-scope negatives. (V08, V09, V10; NOT_RUN).

#### RP-05-E021 | NO_ADD | `plasticos_documents_native/tests/test_native_evidence_bridge.py`

**Owner / stage:** Native Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** This was an earlier proposed test path. Current Native Documents already has verification_delegation and native_search_parity suites; those existing files are extended instead.

**Decision:** Do not add test_native_evidence_bridge.py. Extend the existing verification_delegation and native_search_parity test files, with explicit effect rows below.

**Basis:** The current repository already contains both concern-specific regression homes. No new file is needed for this obligation.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** installed Enterprise documents/document_account; exact native original and conflict negative (V08, V09, V10; NOT_RUN).

#### RP-05-E022 | EDIT | `plasticos_claims/models/document_inherit.py`

**Owner / stage:** Claims; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_claims/models/document_inherit.py#L7-L59. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Document.create can auto-create buyer_claim for selected tags and look up transaction by load limit=1.

**Decision:** Keep the exact legacy claim path but explicitly reject non-legacy operation rows before create-time claim detection. A new operation row on the same original is not another claim or notification. Validate the true trade/company for legacy claim initiation; retain existing claim finance and lifecycle logic.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-CLAIMS: no stored-field migration expected; preserve existing claim IDs, source_document_id and notification state; reconcile preexisting duplicates without deleting monetary history.

**Recovery:** R-CLAIM: retain monetary claims and notifications, restore exact DB state; no duplicate-creation replay.

**Verification:** one original two links -> at most one correct claim; buyerless no fake buyer claim; no second notification (V08, V09, V10; NOT_RUN).

#### RP-05-E023 | NO_CHANGE | `plasticos_claims/models/claim.py`

**Owner / stage:** Claims; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_claims/models/claim.py#L23-L40. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Claim financial record and notification rely on source_document/transaction id.

**Decision:** Preserve claim state and send semantics; eligibility change stays in document trigger, not claim money model.

**Basis:** Keep monetary source owner; only adapter eligibility is altered.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-CLAIM: retain monetary claims and notifications, restore exact DB state; no duplicate-creation replay.

**Verification:** existing recovery totals unchanged and notification count exactly one (V08, V09, V10; NOT_RUN).

#### RP-05-E024 | CREATE | `plasticos_claims/tests/test_document_export_evidence.py`

**Owner / stage:** Claims; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No cross-module scoped evidence -> claim trigger test.

**Decision:** Test new typed associations do not create claim or second outgoing mail; valid claim tag still works.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** repeat sync, no buyer, multi-link, duplicate native original negatives (V08, V09, V10; NOT_RUN).

#### RP-05-E025 | EDIT | `plasticos_claims/tests/__init__.py`

**Owner / stage:** Claims; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_claims/tests/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Imports existing claims tests.

**Decision:** Register new claim-evidence test with existing claims harness.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** test discovery and zero unintended sends (V08, V09, V10; NOT_RUN).

#### RP-05-E026 | EDIT | `plasticos_commission/models/sales_dashboard.py`

**Owner / stage:** Commission; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_commission/models/sales_dashboard.py#L145-L194. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Transaction-grain SQL view left joins load; doc checklist reads business verified/override.

**Decision:** Keep transaction-grain SQL, payouts and rates untouched. Resolve its checklist against exact currently eligible legacy business rows, not the native per-original projection, which intentionally becomes ambiguous when scopes multiply. Operation-only rows never clear legacy checklist items. Preserve access rules and one row per transaction.

**Basis:** The current checklist interprets verified/override directly; source-scoped currentness must reach this consumer explicitly, not be assumed.

**Migration:** M-COMM: no schema change; preserve transaction-grain SQL view and existing commission amounts; verify no new sourced-doc double count.

**Recovery:** R-COMM: restore SQL view/data via safe addon rollback/DB restore if necessary; preserve payouts.

**Verification:** V09/V11: one transaction row; unrelated scoped link never OK; superseded/expired source not OK; own-rep payout and documents remain private. (V08, V09, V10; NOT_RUN).

#### RP-05-E027 | EDIT | `plasticos_commission/tests/test_sales_dashboard_payout_access.py`

**Owner / stage:** Commission; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_commission/tests/test_sales_dashboard_payout_access.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Has existing dashboard ACL regressions.

**Decision:** Extend with export scoped evidence non-contamination and no row multiplication.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** rep ACL, payout/projection unchanged, export doc false-positive denied (V08, V09, V10; NOT_RUN).

#### RP-05-E028 | EDIT | `plasticos_documents/models/transaction_docs_bridge.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/transaction_docs_bridge.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current bridge includes elapsed-expiry refresh on compliance search, but still has the legacy relation/dependency list.

**Decision:** Preserve the merged search-time expiry behavior. Add operation-scope exclusion to its exact legacy row query and remaining currentness/old-new association invalidation. Keep transaction row grain and quiet recursion guard; no money posting.

**Basis:** A source can cease to be effective without its verified bit changing. Consumers must not retain false green projections.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V09: supersede or expire accepted original -> displayed transaction compliance clears; unrelated operation link does not set OK. (V08, V09, V10; NOT_RUN).

#### RP-05-E029 | EDIT | `plasticos_documents/models/load_docs_bridge.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/models/load_docs_bridge.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing bridge only exposes a load document smart button through direct document.load_id.

**Decision:** Keep source-owned navigation and add downstream evidence-policy specialization of the common Logistics guard for exact load/journey scope. Buyerless navigation follows load/typed evidence without inventing a transaction. Base Logistics does not import Documents.

**Basis:** This is the existing downstream interop file for Documents-on-Logistics behavior; use it instead of another adapter addon.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V04/V08: expired/other-company evidence denies new release; observed actual event can still be recorded; no-Documents base install retains its declared base behavior. (V08, V09, V10; NOT_RUN).

#### RP-05-E030 | EDIT | `plasticos_documents_native/tests/test_verification_delegation.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/tests/test_verification_delegation.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** These concern-specific regression suites now exist after the merged verification repair.

**Decision:** Preserve existing writer/delegation/ambiguity/search-parity expectations. Add a sole operation-only business row and mixed legacy/operation original cases; native flags cannot become global operation acceptance. No new test file.

**Basis:** Reuses the current owner test surfaces after source rebind.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12: computation and positive/negative search agree; no native decision writer or binary duplication. (V08, V09, V10; NOT_RUN).

#### RP-05-E031 | EDIT | `plasticos_documents_native/tests/test_native_search_parity.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/tests/test_native_search_parity.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** These concern-specific regression suites now exist after the merged verification repair.

**Decision:** Preserve existing writer/delegation/ambiguity/search-parity expectations. Add a sole operation-only business row and mixed legacy/operation original cases; native flags cannot become global operation acceptance. No new test file.

**Basis:** Reuses the current owner test surfaces after source rebind.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12: computation and positive/negative search agree; no native decision writer or binary duplication. (V08, V09, V10; NOT_RUN).

### RP-06

#### RP-06-E001 | EDIT | `plasticos_security_base/security/record_rules.xml`

**Owner / stage:** Security; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/security/record_rules.xml#L124-L158. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Global Load rule permits company_id=False; Sales Rep visibility uses sale_order_id.user_id.

**Decision:** After source-proven company backfill, remove the Load company-null escape. Add independent global company isolation for the SQL Load dashboard, and J1/J2 role restrictions using existing groups. No legitimate source-owned record is reassigned to the active user company. Bare internal users and Sales reps gain no new buyerless operational visibility.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-SEC: global company rule tightened only after Logistics has proven complete non-null backfill; preflight active user company scopes; preserve legitimate domestic role access.

**Recovery:** R-SEC: snapshot restore of rules plus backfilled companies together; never loosen cross-company rules as an emergency shortcut.

**Verification:** legacy SO rep access; company-null hidden; buyerless allowed Logistics only; multi-company negatives (V11, V15; NOT_RUN).

#### RP-06-E002 | EDIT | `plasticos_security_base/tests/test_bridge_contracts.py`

**Owner / stage:** Security; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/tests/test_bridge_contracts.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing cross-module security bridge regression surface.

**Decision:** Test missing-company rejection, role access and new J1/J2 rule interaction with global restrictions.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** unauthorized company bypass and missing company denied (V11, V15; NOT_RUN).

#### RP-06-E003 | EDIT | `plasticos_security_base/security/ir.model.access.csv`

**Owner / stage:** Security; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/security/ir.model.access.csv. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing global groups and ACLs for prior models.

**Decision:** Add J1/J2 business-role ACL grants here using existing plasticos_security_base.group_logistics and group_operations_manager; no new role and no base.group_user mutation grant. Respect upstream global company filters and guarded accepted-history immutability. Read-only operational access for other roles is only through already-authorized source data, not a universal J1 grant.

**Basis:** Security Base already depends on Logistics, so it can legally reference its models and its own groups. Logistics cannot depend back on Security Base.

**Migration:** M-SEC: global company rule tightened only after Logistics has proven complete non-null backfill; preflight active user company scopes; preserve legitimate domestic role access.

**Recovery:** R-SEC: snapshot restore of rules plus backfilled companies together; never loosen cross-company rules as an emergency shortcut.

**Verification:** V11: bare internal user cannot create/write J1/J2; Logistics allowed in company; multi-role union cannot bypass global company deny. (V11, V15; NOT_RUN).

#### RP-06-E004 | EDIT | `plasticos_logistics/models/load_dashboard.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/models/load_dashboard.py#L73-L159. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Load-grain SQL view left joins transaction and has fallback without transaction column.

**Decision:** Add read-only company_id to the SQL dashboard model and l.company_id AS company_id in BOTH the normal and fallback view definitions. Keep one row per load. Add the corresponding global dashboard company rule in Security Base. Preserve transaction join and domestic dimensions. Buyerless documents drilldown resolves exact load evidence through the downstream Documents bridge, not a fake transaction.

**Basis:** A record rule on plasticos.load does not automatically constrain a different SQL-view model. Existing SQL has no company projection.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V11/V12: direct dashboard search/read_group/QWeb/navigation cross-company negative; both view definitions fresh-install; one buyerless row not leaked. (V11, V15; NOT_RUN).

#### RP-06-E005 | NO_CHANGE | `plasticos_logistics/views/load_dashboard_views.xml`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/views/load_dashboard_views.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Legacy dashboard UI actions target load view.

**Decision:** Keep domestic dashboard and no Export booking tab; Export native report UX separate.

**Basis:** The list/search actions consume the unchanged load-dashboard row grain and existing fields. Adding a model company_id and global rule does not require displaying a new column. Buyerless source navigation is repaired at the model/bridge, not by duplicating ACL or source logic in XML.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** one load one row with/without transaction and role-safe filters (V11, V15; NOT_RUN).

#### RP-06-E006 | NO_CHANGE | `plasticos_admin_dashboard/models/admin_dashboard.py`

**Owner / stage:** Admin Dashboard; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_admin_dashboard/models/admin_dashboard.py#L282-L315. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** KPI rows aggregate existing transaction quantities; load dashboard is a navigation action.

**Decision:** Keep transaction KPI grain, no container-slot recomputation; verify navigation and company safety on buyerless loads.

**Basis:** Source SQL computes transaction not J1/E3 counts; no new Export metrics here.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-READ: no write expected; rollback consists of restoring original action/config on clone if changed by install.

**Verification:** existing KPI counts, action target, permissions under new security (V11, V15; NOT_RUN).

#### RP-06-E007 | NO_CHANGE | `plasticos_admin_dashboard/views/admin_dashboard_views.xml`

**Owner / stage:** Admin Dashboard; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_admin_dashboard/views/admin_dashboard_views.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Native admin dashboard displays existing KPI/action references.

**Decision:** Keep existing actions; Export supplies its own report menu; do not add duplicate dashboard.

**Basis:** The admin views expose existing commercial KPIs and the same Logistics dashboard action. Neither the transaction population nor view fields is widened to J1/E3; model company filtering is corrected at its owning dashboard.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-READ: no write expected; rollback consists of restoring original action/config on clone if changed by install.

**Verification:** V11/V15: unchanged admin view opens the company-filtered Logistics action; no journey/slot multiplication of commercial KPI rows. (V11, V15; NOT_RUN).

#### RP-06-E008 | NO_CHANGE | `plasticos_commission/security/record_rules.xml`

**Owner / stage:** Commission; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_commission/security/record_rules.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing commission/sales rep transaction access rules.

**Decision:** Keep transaction-grain rep access; new J1 records have separate Logistics ACL.

**Basis:** The existing Commission rules restrict unchanged transaction-grain dashboard and payout models by their existing roles. This campaign changes only document currentness/checklist reads, not commission SQL grain, money or a J1 join; preserve these role rules and their access regressions.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-COMM: restore SQL view/data via safe addon rollback/DB restore if necessary; preserve payouts.

**Verification:** sales rep cannot enumerate other-company J1 via dashboard action (V11, V15; NOT_RUN).

#### RP-06-E009 | NO_CHANGE | `native:spreadsheet_dashboard`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Installed Odoo dashboard may or may not expose native spreadsheet feature.

**Decision:** Use existing Odoo native dashboard/report surfaces only after installed module verification; no new OWL/JS.

**Basis:** Use existing Odoo native dashboard/report surfaces only after installed module verification; no new OWL/JS. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** six reports, identical filter/drilldown and full company ACL when installed (V11, V15; NOT_RUN).

### RP-07

#### RP-07-E001 | EDIT | `plasticos_logistics/__manifest__.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Version 19.0.1.14.5; loads security/tests/records/PO-SO Linda data.

**Decision:** Bump Logistics 19.0.1.14.5 -> 19.0.1.14.6. Register J1/J2 view and Linda request-targeted booking/ACK/document-chase templates. No dependency on Documents, Native Documents, Security Base or Export. Initialize the context-version compatibility branch and preserve load_dashboard-last import order.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** fresh install and upgrade, all XML IDs and native Odoo 19 code-check gates (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E002 | EDIT | `plasticos_documents/__manifest__.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/__manifest__.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current Documents manifest is 19.0.2.1.6 after the exact-association/one-writer merge.

**Decision:** Bump 19.0.2.1.6 -> 19.0.2.1.7 for residual operation-scope fields/query/ACL/UI and tests. Keep dependencies unchanged and do not register a retired evidence-link model.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-DOC: census duplicate/ambiguous original records and verification conflicts; add scoped links only from exact proof; keep one original and old invoice/close semantics; uncertain links to review.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** fresh install + upgrade + link ACL load (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E003 | EDIT | `plasticos_documents_native/__manifest__.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/__manifest__.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current Native Documents manifest is 19.0.1.2.10.

**Decision:** Bump 19.0.1.2.10 -> 19.0.1.2.11 for the narrow operation-discriminator projection/search guard and existing-suite regression additions. No new persisted Native schema and no new migration needed.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-NATIVE: compare native and business flags, source attachment identity and conflicting links; preserve native originals, do not promote native unverified flags or recency guesses.

**Recovery:** R-DOC: restore DB+filestore originals and reconcile sync direction; no unproven verified bit promotion.

**Verification:** Enterprise installed model+view+ACL on updated registry (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E004 | EDIT | `plasticos_security_base/__manifest__.py`

**Owner / stage:** Security; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Version 19.0.1.2.21 depends on logistics, docs, automation.

**Decision:** Target version 19.0.1.2.22; maintain DAG and process security after company data repair.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-SEC: global company rule tightened only after Logistics has proven complete non-null backfill; preflight active user company scopes; preserve legitimate domestic role access.

**Recovery:** R-SEC: snapshot restore of rules plus backfilled companies together; never loosen cross-company rules as an emergency shortcut.

**Verification:** module graph acyclic and security upgrade in correct order (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E005 | EDIT | `plasticos_claims/__manifest__.py`

**Owner / stage:** Claims; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_claims/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Version 19.0.1.1.2 and depends on Documents/Logistics.

**Decision:** Target version 19.0.1.1.3 after claim-trigger repair; no new Export dependency.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-CLAIMS: no stored-field migration expected; preserve existing claim IDs, source_document_id and notification state; reconcile preexisting duplicates without deleting monetary history.

**Recovery:** R-CLAIM: retain monetary claims and notifications, restore exact DB state; no duplicate-creation replay.

**Verification:** claims update and golden financial behavior (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E006 | CREATE | `plasticos_logistics/migrations/19.0.1.14.6/pre-migrate.py`

**Owner / stage:** Logistics; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Existing 19.0.1.10.3 backfill checks only uniqueness of load_id.

**Decision:** While all workers/mail/cron are quiesced, census version/schema and exact load/source company. Perform only deterministic existing-column company repair BEFORE Odoo loads the new required field/constraints; abort the entire upgrade on ambiguous/missing/conflicting ownership. Snapshot outgoing request state and activation flags before request CHECK changes. Do not create J1 from legacy container strings. See M-LOG decision table.

**Basis:** A new module-version migration must be its own versioned file; editing an older migration would rewrite historical behavior. This file owns the explicit C07 pre/post obligation.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** preflight fails on duplicate SO candidate or ambiguous company; zero guessed links (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E007 | CREATE | `plasticos_logistics/migrations/19.0.1.14.6/post-migrate.py`

**Owner / stage:** Logistics; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No J1/J2 population or exact company migration exists.

**Decision:** After schema load, verify pre-repaired company and existing 1:1 links; backfill new Linda source-kind fields only from exact existing PO/SO/load identities, then validate new branch constraints. Keep J1/J2 empty unless operator-supplied proof mappings exist. Rebuild SQL projections, restore prior inactive flags, leave outbound suppressed pending release. Rerun is a no-op or a precise discrepancy, not duplicate creation.

**Basis:** A new module-version migration must be its own versioned file; editing an older migration would rewrite historical behavior. This file owns the explicit C07 pre/post obligation.

**Migration:** M-LOG: exact post-bump preflight of legacy load companies/duplicate SO matching; preserve proven links; staged company backfill before non-null/ACL tightening; add J1/J2 empty, no guessed imports; booking-request constraints only after old row census.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** idempotent repeated run on clone, same counts/reports, fail on unproven source (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E008 | NO_ADD | `plasticos_documents/migrations/19.0.2.1.3/pre-migrate.py`

**Owner / stage:** Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Current migrations predate scoped associations.

**Decision:** Do not add the previously proposed 19.0.2.1.3 migration path: it is below the current 19.0.2.1.6 source version. Replacement scripts are explicitly listed at 19.0.2.1.7.

**Basis:** Current source advancement invalidates the earlier proposed version coordinate. Never reuse a lower version and assume Odoo will execute it.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** ambiguous native verification blocked, no lost attachment (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E009 | NO_ADD | `plasticos_documents/migrations/19.0.2.1.3/post-migrate.py`

**Owner / stage:** Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No scoped business links exist.

**Decision:** Do not add the previously proposed 19.0.2.1.3 migration path: it is below the current 19.0.2.1.6 source version. Replacement scripts are explicitly listed at 19.0.2.1.7.

**Basis:** Current source advancement invalidates the earlier proposed version coordinate. Never reuse a lower version and assume Odoo will execute it.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** idempotent and no row multiplication; original hash unchanged (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E010 | NO_CHANGE | `plasticos_documents_native/migrations/19.0.1.2.6/pre-migrate.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/migrations/19.0.1.2.6/pre-migrate.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** The exact path now exists and preserves historical native verification into immutable conflict snapshots before the earlier computed-projection change.

**Decision:** Preserve the already-merged 19.0.1.2.6 pre-migration byte-for-byte. Do not overwrite it with this campaign. The selected 2.10 -> 2.11 interval does not execute it; an older installed tenant must first complete and verify its existing baseline upgrade.

**Basis:** Current source has satisfied this earlier migration obligation under its own revision. The Export plan is not authority to alter migration history.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore originals and reconcile sync direction; no unproven verified bit promotion.

**Verification:** conflicts fail closed; no unverified bit promotion (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E011 | NO_ADD | `plasticos_documents_native/migrations/19.0.1.2.6/post-migrate.py`

**Owner / stage:** Native Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Existing sync may previously have written business flags from native.

**Decision:** Do not add a historical 19.0.1.2.6 post-migration or a new 2.11 post-migration for code-only projection narrowing. Preserve current historical snapshots and execute compatibility tests.

**Basis:** No persisted Native data shape is changed by the residual scope guard; repeating the previous conversion would invent an unnecessary migration.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** same original IDs, deterministic repeat/restart, conflict review list (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E012 | CREATE | `plasticos_security_base/migrations/19.0.1.2.22/pre-migrate.py`

**Owner / stage:** Security; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Global rule permits company null; current data populations not counted.

**Decision:** Before tightening rules, assert every retained operational Load has a proven company and SQL dashboard company projection is installed. Do not assign company in Security Base. Preserve role membership, never auto-grant a reviewer/cron broad manager rights. If data is hidden by the new rule unexpectedly, abort/recover rather than weakening the filter.

**Basis:** A new module-version migration must be its own versioned file; editing an older migration would rewrite historical behavior. This file owns the explicit C07 pre/post obligation.

**Migration:** M-SEC: global company rule tightened only after Logistics has proven complete non-null backfill; preflight active user company scopes; preserve legitimate domestic role access.

**Recovery:** R-SEC: snapshot restore of rules plus backfilled companies together; never loosen cross-company rules as an emergency shortcut.

**Verification:** missing-company blocks migration before potentially hiding live loads (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E013 | NO_ADD | `plasticos_security_base/migrations/19.0.1.2.22/post-migrate.py`

**Owner / stage:** Security; S2. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Security rule is declarative XML and load owner backfill precedes it.

**Decision:** Do not add a Security Base post-migration file. Owner data repair is completed and checked in Logistics before this module; declarative rules and the preflight are sufficient. A measured target-specific need is new evidence requiring plan revision, not a preauthorized optional file.

**Basis:** This path does not exist in the inspected tree; it is an explicit exclusion, not an existing file verified unchanged.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** rule active and all data visible only to authorized companies (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E014 | EDIT | `plasticos_logistics/tests/__init__.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/tests/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Registers existing tests including Linda and load cardinality.

**Decision:** Import new J1/J2, release guard and booking source tests; do not weaken existing assertions.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** test loader enumerates all new tests in EE (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E015 | EDIT | `plasticos_logistics/tests/test_load_cardinality.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/tests/test_load_cardinality.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing positive test expects one linked transaction per load.

**Decision:** Preserve positive constraint; add two transactions same SO and buyerless negative/positive cases.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** duplicate Tx load denied; exact association branch tested (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E016 | NO_CHANGE | `plasticos_logistics/__init__.py`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Already imports models and wizards; test discovery currently works for listed tests.

**Decision:** Keep the existing addon-root __init__.py unchanged. Register new tests only in the tests subpackage __init__.py and rely on the documented Odoo 19 loader. Runtime collection counts must prove execution later; missing collection is not permission to improvise root imports.

**Basis:** Odoo 19 official unit-test tutorial explicitly says not to import tests at addon root. Existing root already imports its product models/hooks.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DB: restore consistent Odoo PostgreSQL+filestore snapshot on test clone; preserve old IDs, do not auto-unlink ambiguous loads; rerun company/one-to-one invariants.

**Verification:** V12: new tests discoverable via tests/__init__.py; no product import-time execution of tests. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E017 | NO_CHANGE | `plasticos_documents/__init__.py`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Root already imports models and hooks.

**Decision:** Keep the existing addon-root __init__.py unchanged. Register new tests only in the tests subpackage __init__.py and rely on the documented Odoo 19 loader. Runtime collection counts must prove execution later; missing collection is not permission to improvise root imports.

**Basis:** Odoo 19 official unit-test tutorial explicitly says not to import tests at addon root. Existing root already imports its product models/hooks.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore atomically; preserve original attachments and audit flags; do not silently backdate acceptance.

**Verification:** V12: new tests discoverable via tests/__init__.py; no product import-time execution of tests. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E018 | NO_CHANGE | `plasticos_documents_native/__init__.py`

**Owner / stage:** Native Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents_native/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Root imports models but not tests, and tests folder lacks init.

**Decision:** Keep the existing addon-root __init__.py unchanged. Register new tests only in the tests subpackage __init__.py and rely on the documented Odoo 19 loader. Runtime collection counts must prove execution later; missing collection is not permission to improvise root imports.

**Basis:** Odoo 19 official unit-test tutorial explicitly says not to import tests at addon root. Existing root already imports its product models/hooks.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-DOC: restore DB+filestore originals and reconcile sync direction; no unproven verified bit promotion.

**Verification:** V12: new tests discoverable via tests/__init__.py; no product import-time execution of tests. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E019 | NO_CHANGE | `plasticos_security_base/__init__.py`

**Owner / stage:** Security; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/__init__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Root imports models and existing hooks.

**Decision:** Keep the existing addon-root __init__.py unchanged. Register new tests only in the tests subpackage __init__.py and rely on the documented Odoo 19 loader. Runtime collection counts must prove execution later; missing collection is not permission to improvise root imports.

**Basis:** Odoo 19 official unit-test tutorial explicitly says not to import tests at addon root. Existing root already imports its product models/hooks.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-SEC: snapshot restore of rules plus backfilled companies together; never loosen cross-company rules as an emergency shortcut.

**Verification:** V12: new tests discoverable via tests/__init__.py; no product import-time execution of tests. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E020 | EDIT | `plasticos_logistics/business_rules/SUPERSESSION.md`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/business_rules/SUPERSESSION.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Logistics BRS historical/operative status under source owner.

**Decision:** Owner accepts exact company/J1/J2/Linda semantics with traceable supersession, without rewriting BRS-01..07 originals.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** owner adoption review & BRS rule regression trace (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E021 | EDIT | `plasticos_logistics/business_rules/NATIVE_DOCUMENTS_INTEROP.md`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/business_rules/NATIVE_DOCUMENTS_INTEROP.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing Logistics-Docs ownership bridge text.

**Decision:** Add exact owner handoffs and no duplicate verification/SMTP semantics.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** source-contract trace, installed module handoff test (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E022 | EDIT | `plasticos_documents/business_rules/SUPERSESSION.md`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/business_rules/SUPERSESSION.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Documents BRS existing supersession law.

**Decision:** Adopt scoped association/one-verifier semantics at native owner; keep original BRS unedited.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** Documents source-contract trace and governance checks (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E023 | EDIT | `plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Documents owners original/verification bridge.

**Decision:** Resolve precise one business verifier, native original and transaction reminder behavior; no Export alternate owner.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** joint Documents and Native owner acceptance (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E024 | NO_CHANGE | `plasticos_crm_bridge/__manifest__.py`

**Owner / stage:** CRM Bridge; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_bridge/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Depends on Logistics/Security but does not author physical ISO or booking model.

**Decision:** Keep CRM Bridge dependency and public CRM shapes unchanged; new Logistics company is optional for CRM lead.

**Basis:** The CRM Bridge already reaches Logistics through its declared dependencies. Its production code and required upstream model names remain unchanged; no Export dependency or version bump is warranted.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-READ: no write expected; preserve CRM mappings and records; rollback only via full snapshot if unforeseen side effect.

**Verification:** CRM UI source-only and no booking fields created; installed registry unchanged (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E025 | NO_CHANGE | `plasticos_crm_bridge/models/crm_lead.py`

**Owner / stage:** CRM Bridge; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_bridge/models/crm_lead.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** CRM lead model does not expose physical journey/Load semantic in inspected paths.

**Decision:** Keep CRM field ownership and lead data unchanged; no contact import coupling.

**Basis:** The inspected CRM lead surface contains no direct load, transaction or company field use affected by the selected physical schema. It does not consume Export/J1 or accept document evidence; preserve existing CRM behavior and exercise downstream regression.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-READ: no write expected; preserve CRM mappings and records; rollback only via full snapshot if unforeseen side effect.

**Verification:** no new load / booking lead fields, CRM source Lead smoke (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E026 | NO_CHANGE | `plasticos_crm_sync/services/orchestrator.py`

**Owner / stage:** CRM Sync; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_sync/services/orchestrator.py#L1-L65. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Current CRM sync orchestrator maps upstream leads/contacts and material; changed since old Export pack SHA.

**Decision:** Keep import watermarks and material exact-phrase behavior unchanged; no new Load/Export mutation.

**Basis:** HEAD drift changed CRM importer, not Logistics, but end-to-end regression still required.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-CRM: no rebootstrap/replay of CRM data as an Export recovery step; preserve watermarks.

**Verification:** current CRM classifications plus full/upsert import regression (no Export booking side effect) (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E027 | NO_CHANGE | `plasticos_material_profile/models/material_normalizer.py`

**Owner / stage:** Material Profile; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_material_profile/models/material_normalizer.py#L1-L110. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Current HEAD adds approved CRM phrase-only material matching.

**Decision:** Preserve normalization and canonical polymer master; Export E4 may read product but not reinterpret lead descriptions.

**Basis:** Source HEAD delta inspected: CRM phrase mapping only; no Export field introduced.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAT: preserve material registry and CRM import state; no export mutation.

**Verification:** existing material phrase unit suite plus no new source material owner (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E028 | EDIT | `plasticos_commission/__manifest__.py`

**Owner / stage:** Commission; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_commission/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Version 19.0.1.4.3, depends on Logistics/Security.

**Decision:** Bump Commission 19.0.1.4.3 -> 19.0.1.4.4 for the narrow document-checklist/currentness consumer repair and its regressions. Preserve every commission rate, payout and SQL transaction grain.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-COMM: no schema change; preserve transaction-grain SQL view and existing commission amounts; verify no new sourced-doc double count.

**Recovery:** R-COMM: restore SQL view/data via safe addon rollback/DB restore if necessary; preserve payouts.

**Verification:** version/check_module_wiring test on exact EE install; no SQL report behavior change (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E029 | NO_CHANGE | `plasticos_admin_dashboard/__manifest__.py`

**Owner / stage:** Admin Dashboard; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_admin_dashboard/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Version 19.0.1.1.0, depends on Logistics/Security.

**Decision:** No schema change; only native navigation/ACL regression witness.

**Basis:** The Admin Dashboard production model/view contracts are retained and its Logistics action points to the same corrected SQL model. No source bytes in this addon require modification, so no version advance or migration is justified.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-READ: no write expected; rollback consists of restoring original action/config on clone if changed by install.

**Verification:** admin dashboard install and current company read (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E030 | NO_CHANGE | `plasticos_transaction/__manifest__.py`

**Owner / stage:** Transaction; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/__manifest__.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Current Transaction version is 19.0.2.3.43. _compute_compliance is now explicitly observational and no longer calls invoice posting.

**Decision:** Leave Transaction version and production code unchanged. Preserve the merged no-post boundary and original commercial relations. No Export/J1 command may invoke explicit Accounting posting or synthesize commercial records.

**Basis:** Transaction buyer fields and commercial model remain unchanged; the problematic load constraint is owned by Logistics. The selected 1:1 relation and transaction population remain stable, so no Transaction module version/migration is added.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-TX: preserve old transaction monetary and partner state; clone restore on mutation error.

**Verification:** DAG cycle check + transaction smoke (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E031 | NO_CHANGE | `native:documents.document,documents_account`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Odoo 19 Enterprise models and views have not been verified in a live fixture in this session.

**Decision:** Use existing EE originals, Document/account integration and native attachment; custom bridge adapts without Odoo core edit.

**Basis:** Use existing EE originals, Document/account integration and native attachment; custom bridge adapts without Odoo core edit. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** installed EE field/model/QWeb/ACL source receipt, clone install without missing model (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E032 | NO_CHANGE | `native:stock.picking,mail.mail`

**Owner / stage:** Native Odoo; S1. **Source:** TARGET_RUNTIME_EVIDENCE_REQUIRED. **Observation scope:** OWNERSHIP_EXCLUSION_WITH_INSTALLED_API_UNOBSERVED.

**Before:** Native Stock and mail own actual movements and send outcomes.

**Decision:** No core monkeypatch; reuse owner-native operations with scoped custom module protections.

**Basis:** No core monkeypatch; reuse owner-native operations with scoped custom module protections. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-NATIVE: Odoo.sh native backup and tested off-provider independent copy; preserve core app/native data in same atomic recovery point.

**Verification:** native partial deliveries, mail queue claim once, no unowned send (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E033 | NO_CHANGE | `scripts/check_module_wiring.py`

**Owner / stage:** Integration; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/scripts/check_module_wiring.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Repository checks addon imports/manifest registration.

**Decision:** Keep the existing generic tracked-file model/import/manifest checker. In later implementation verification ensure all planned new files are present in the candidate tracked-file inventory before running it; an untracked omission is not a passing wiring proof.

**Basis:** The current script discovers git-tracked plasticos_* directories and manifests rather than an Export-specific hard-coded roster. Existing behavior covers the new addon without a parallel checker.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-INT: backup+restore witness on isolated clone, capture backup ID, PostgreSQL/filestore checksums and point-in-time recovery limits; no unverified automatic down-migrate.

**Verification:** V12/V17: tracked new addon/models/XML references included; deliberately missing import/dependency fails the existing checker. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E034 | NO_CHANGE | `ci/check_circular_deps.py`

**Owner / stage:** Integration; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/ci/check_circular_deps.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Existing dependency graph cycle test.

**Decision:** Keep the existing SCC and cross-module dependency checker. Verify the complete candidate tracked inventory and require no base-owner reverse dependency on Export. Do not treat an empty/untracked scan as closure.

**Basis:** The inspected implementation enumerates tracked manifests and checks dependency cycles generically. No new algorithm or module-specific exception is required.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-INT: backup+restore witness on isolated clone, capture backup ID, PostgreSQL/filestore checksums and point-in-time recovery limits; no unverified automatic down-migrate.

**Verification:** V12/V17: complete candidate DAG passes; injected Logistics -> Export reverse dependency fails. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E035 | NO_CHANGE | `INVARIANTS.md`

**Owner / stage:** Governance; S0. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/INVARIANTS.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Repository constitutional file remains v2.2.0.

**Decision:** Do not silently replace constitution with candidate POS-INV-26; apply pack-local no-code gate until separately admitted.

**Basis:** The repository constitution remains its own versioned authority. This task only completes the working plan; POS-INV-26 remains the explicit pack-local operator restriction and is not silently admitted by editing unrelated repository law.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-GOV: no repository mutation, revert planning candidate only; never substitute draft for admitted law.

**Verification:** operator directive present at handoff; source-owner governance acceptance recorded (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E036 | EDIT | `docs/adr/README.md`

**Owner / stage:** Integration; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/README.md. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Repository ADR index exists.

**Decision:** Register the single planned ADR-129 export physical/evidence/owner contract in the canonical ADR index. Preserve all existing entries/statuses; do not call an unimplemented interface runtime-proven.

**Basis:** The source README expressly requires an ADR for cross-module contracts and costly schema choices, plus indexes in this file and ARCHITECTURE.md and an agent task link. The earlier unconditional no-ADR decision was invalid.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12/V17: ADR and both required index links resolve; agent task read path reaches it; original BRS/technical contract digests unchanged. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E037 | INDEPENDENT | `plasticos_facility_profile/__manifest__.py`

**Owner / stage:** Facility Profile; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_facility_profile/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Facility profile owns facility equipment, not ocean ISO identity.

**Decision:** Keep facility equipment registry distinct from Logistics J1; no export shipment equipment writing.

**Basis:** The Facility Profile manifest owns facility capability/equipment registries upstream of Logistics. The inspected equipment taxonomy describes plant machinery/handling, not an ISO container cycle. Export/J1 reads actual source-party identity without modifying or reusing this registry as physical transport truth.

**Migration:** M-FAC: no export equipment registry rewrite; facility equipment and physical ISO are different grains.

**Recovery:** R-FAC: preserve facility registry, no export mutation.

**Verification:** no J1/equipment class import or reverse dependency, immutable source census (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E038 | INDEPENDENT | `plasticos_accounting/__manifest__.py`

**Owner / stage:** Accounting; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_accounting/__manifest__.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Accounting addon depends only on account and does not own new booking or journey model.

**Decision:** Keep native AP/AR and supplier price/weight decisions outside Export; no automatic invoice change.

**Basis:** The standalone plasticos_accounting manifest depends only on native account. The selected Export work cannot post finance, and no Accounting model, report, money field or callback is added. The changed Documents eligibility query is planned at its real owner; no native account rewrite is needed.

**Migration:** M-ACC: native AP/AR amounts remain with accounting, no automatic weigh-ticket price rewrites.

**Recovery:** R-ACC: no AP/AR rollback by export, restore accounting owner ledger only from valid backup if a separate authorized migration touches it.

**Verification:** V08/V09/V18: booking/evidence acceptance, migration and replay create no account.move posting, payment, recovery or accounting total change. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E039 | CREATE | `plasticos_export/__init__.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export addon installed at HEAD.

**Decision:** Register proposed Export models only after owner interfaces accepted, default external effects disabled.

**Basis:** The selected new addon/model/test package needs this loader to make its declared files reachable under Odoo; this is registration, not a new semantic layer.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** fresh install, test discovery and undo/install rehearsal (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E040 | CREATE | `plasticos_export/__manifest__.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No installed Export depends graph.

**Decision:** Create Export manifest at 19.0.1.0.0 with depends on plasticos_documents_native (which already reaches required native/owner modules) and any directly imported owner explicitly listed under repository wiring law. Set installable=True, application=True, auto_install=False. Register all XML/ACL/views/reports and booking-only inbound automation. Default external-effect enable flag absent/False; no automatic production activation. Explicit integration fixture installs Export, not the domestic default profile.

**Basis:** This is the already-selected source file for the frozen new owner; the predecessor technical contract identifies the exact responsibility and absence of an equivalent existing field/model.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** DAG, registry, install+update and no pre-install client writes (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E041 | CREATE | `plasticos_export/models/__init__.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export model registry.

**Decision:** Register E1+E2, E3+E4, and narrow Logistics inheritance only; no duplicate physical model.

**Basis:** The selected new addon/model/test package needs this loader to make its declared files reachable under Odoo; this is registration, not a new semantic layer.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** all six E/J owner models accessible exactly once (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E042 | CREATE | `plasticos_export/models/booking.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Older filetree suggested conditional separate revision file.

**Decision:** E1 reservation + E2 immutable accepted revision in one file; exact current pointer CAS, provenance and idempotency.

**Basis:** This is the already-selected source file for the frozen new owner; the predecessor technical contract identifies the exact responsibility and absence of an equivalent existing field/model.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** revision stale/roll race, same booking/number identities, no original copy (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E043 | CREATE | `plasticos_export/models/booking_allocation.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Older allocation candidate associated each slot directly with a load.

**Decision:** E3 slots bind nullable physical J1 and distinct-slot capacity; E4 cargo is exact native source link and planned-only quantity.

**Basis:** This is the already-selected source file for the frozen new owner; the predecessor technical contract identifies the exact responsibility and absence of an equivalent existing field/model.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** five slots / four POs, two feeder sources one slot, downsize held, concurrent binds (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E044 | CREATE | `plasticos_export/models/logistics_integration.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** v2.7 requires enforcement at physical owner but prohibits Logistics depending on Export.

**Decision:** Use this already-planned downstream integration file for normal _inherit extensions of the Logistics physical guard, Linda request/response source resolver and Documents evidence subject lookup. E1/E2 lookup, booking-currentness and affected-load scope stay here. No monkey patch, generic plugin registry, reverse FK, or direct SMTP. Expose the frozen public methods at their named model receiver.

**Basis:** One Odoo extension file may express the existing v2.7 source-owner dispatch contract; not a new business owner.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** with/without Export installed, booking currentness enforced; no module cycle (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E045 | NO_ADD | `plasticos_export/models/booking_revision.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Old candidate said separate E2 file only if needed.

**Decision:** Do not create this file: E2 belongs in booking.py and is required by selected v2.7 design.

**Basis:** Do-not-add decision explicitly disposes obsolete prior filetree.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** one revision model only, exact source accepted and no duplicate verification (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E046 | NO_ADD | `plasticos_export/models/load_extension.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** Old candidate suggested direct booking to load association.

**Decision:** Do not create old direct load FK path; any necessary Odoo inheritance is narrow logistics_integration.py release hook with J1/E3 physical boundary.

**Basis:** Explicit reject old one-load-per-slot realization.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** no booking.slot.load_id, buyerless without load, both feeder sources preserved (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E047 | CREATE | `plasticos_export/security/ir.model.access.csv`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No E1-E4 operator rights.

**Decision:** Create least-privilege company/role grants, denial for accepted revision mutation and unscoped write.

**Basis:** The absent Export addon needs its own model ACL/rules. An upstream module cannot legally reference this downstream model without a reverse dependency.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** multi-company access matrix; stale replay unauthorized (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E048 | CREATE | `plasticos_export/security/export_record_rules.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export operation company record rules.

**Decision:** Deny cross-company booking/revision/slot/cargo links across all read/write/unlink paths.

**Basis:** The absent Export addon needs its own model ACL/rules. An upstream module cannot legally reference this downstream model without a reverse dependency.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** other company user cannot see counted slots or report rows (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E049 | CREATE | `plasticos_export/views/booking_views.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No booking list/form.

**Decision:** Native Odoo booking list/search/form accepted source revision and operator action controls.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** review acceptance with source original and no stage bypass (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E050 | CREATE | `plasticos_export/views/allocation_views.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No allocation/space UI.

**Decision:** Slot-grain capacity, held/committed/available with correct company filter.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** five actual slots counted once with multiple cargo sources (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E051 | CREATE | `plasticos_export/views/shipment_views.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No J1 read-only Export navigation.

**Decision:** Read-only source attribution/journey links with navigation to Logistics owner; no Export physical state writer.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** one J1 multiple feeders correctly displayed (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E052 | CREATE | `plasticos_export/views/export_analysis_views.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No native Export report actions.

**Decision:** Native filtered list/pivot/graph views for six defined reports; no separate warehouse or OWL client.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** six report grains, ACL and no join inflation (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E053 | CREATE | `plasticos_export/views/export_menus.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export navigation.

**Decision:** Operator Overview/Bookings/Allocations/Shipments/Deadlines/Reporting menu, no Phase 2 provider action.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** six drilldowns and role access under EE (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E054 | CREATE | `plasticos_export/report/export_report_actions.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export-owned report actions.

**Decision:** Register source-linked booking summary/container manifest only; native core report reuse.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** report action works by company/subject and no unauthorized attachment (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E055 | CREATE | `plasticos_export/report/report_booking_summary.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export QWeb booking report.

**Decision:** Source-labeled accepted booking/revision/issuer currentness and exact carrier confirmation.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** revision roll renders historical correctly, no unknown terms promoted (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E056 | CREATE | `plasticos_export/report/report_container_manifest.xml`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No source-correct manifest.

**Decision:** Render physical J1 and E4 planned sources with original provenance, no inferred shipped/stock quantities.

**Basis:** The absent owner needs the specified native view/report surface for its already-frozen operator workflow; existing upstream modules cannot own downstream model XML.

**Migration:** M-EXP: fresh install after upstream; no migration from packaging container_no or synthetic bookings; create E1-E4 only on authenticated user action/evidence.

**Recovery:** R-EXP: disable Export actions and sends; restore full DB+filestore to pre-install point for faulty state, never delete historical accepted revisions by hand.

**Verification:** one container two feeders and no false gate-in/sailing (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E057 | CREATE | `plasticos_export/tests/__init__.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No Export tests.

**Decision:** Import all Export acceptance suites using installed Odoo 19 discovery mechanism.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** all selected test modules collected and run (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E058 | CREATE | `plasticos_export/tests/test_booking_and_revision.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No current Export regression suite.

**Decision:** Add candidate/acceptance/roll/idempotent source and stale mutation regression with no real outbound mail.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** enterprise fixture and full positive/negative integrations (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E059 | CREATE | `plasticos_export/tests/test_booking_allocation.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No current Export regression suite.

**Decision:** Add equipment true slot count, concurrent E4, J1 binding regression with no real outbound mail.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** enterprise fixture and full positive/negative integrations (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E060 | CREATE | `plasticos_export/tests/test_export_owner_handoff.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No current Export regression suite.

**Decision:** Add Documents/Linda/Logistics owner boundary and no shadow writer regression with no real outbound mail.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** enterprise fixture and full positive/negative integrations (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E061 | CREATE | `plasticos_export/tests/test_views_and_reports.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No current Export regression suite.

**Decision:** Add six report grains, QWeb, drilldown and filters regression with no real outbound mail.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** enterprise fixture and full positive/negative integrations (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E062 | CREATE | `plasticos_export/tests/test_multicompany_permissions.py`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No current Export regression suite.

**Decision:** Add company ACL and source-linked attachment access regression with no real outbound mail.

**Basis:** This file groups the new owner-specific acceptance obligation already selected by the predecessor plan. It cannot import a downstream owner as a shortcut; the listed existing suites remain intact.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** enterprise fixture and full positive/negative integrations (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E063 | NO_ADD | `plasticos_export/controllers/`

**Owner / stage:** Export; S5. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md. **Observation scope:** PLANNED_NEW_NOT_INSTALLED.

**Before:** No controller in accepted Phase 1 envelope.

**Decision:** Do not add public API/portal; no external data egress needed for existing native operator UI.

**Basis:** Do not add public API/portal; no external data egress needed for existing native operator UI. This exclusion is limited to the named unchanged consumer contract and is falsified by the attached regression expectation.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** no controllers or http routes registered (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E064 | REVIEW_ONLY | `GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md`

**Owner / stage:** Governance; S0. **Source:** GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md. **Observation scope:** PACK_BYTES_INSPECTED_AND_PRESERVED_OR_EXPLICITLY_UPDATED.

**Before:** POS-INV-26 is pack-local draft, not admitted to constitutional source.

**Decision:** Preserve the operative POS-INV-26 file byte-for-byte; reference the successor plan and do not promote it into constitutional repository law.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-GOV: candidate rule and review packet only; constitutional admission separate, no code change under pack alone.

**Recovery:** R-GOV: no repository mutation, revert planning candidate only; never substitute draft for admitted law.

**Verification:** no replacement of repo INVARIANTS.md or automatic source law promotion (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E065 | REVIEW_ONLY | `EXPORT_BRS/INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md`

**Owner / stage:** Integration; S0. **Source:** EXPORT_BRS/INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md. **Observation scope:** PACK_BYTES_INSPECTED_AND_PRESERVED_OR_EXPLICITLY_UPDATED.

**Before:** Prior RP-01..07 are OPEN and no effect-level plan existed.

**Decision:** Update the existing pack-local gate to point to v2.7.5 and distinguish source planning, target observation, code authorization, runtime proof and deployment; never self-clear S1-TARGET.

**Basis:** Respect selected E1-E4/J1-J2 ownership and preserve domestic correctness

**Migration:** M-INT: non-mutating production clone census then dry-run full DB+filestore restore, pre/post install comparison and reversible rehearsal; no data deletion.

**Recovery:** R-INT: backup+restore witness on isolated clone, capture backup ID, PostgreSQL/filestore checksums and point-in-time recovery limits; no unverified automatic down-migrate.

**Verification:** technical source evidence + negative unplanned-edit test + checked final HEAD diff (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E066 | NO_CHANGE | `plasticos_crm_sync/__manifest__.py`

**Owner / stage:** CRM Sync; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_sync/__manifest__.py#L1-L50. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Current CRM Sync manifest version 19.0.1.9.12 is newer than prior Export source pin.

**Decision:** Do not alter CRM Sync dependency or version to accommodate Export; capture current version in integration baseline.

**Basis:** Changed in 3-commit source drift; current exact HEAD is the baseline.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-CRM: no rebootstrap/replay of CRM data as an Export recovery step; preserve watermarks.

**Verification:** CRM Sync manifest graph/installation and no Export dependency (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E067 | NO_CHANGE | `plasticos_crm_sync/tests/test_crm45_classification.py`

**Owner / stage:** CRM Sync; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_sync/tests/test_crm45_classification.py#L1-L100. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Classification assertions changed in the latest CRM/material delta.

**Decision:** Keep changed CRM classification tests as the existing regression oracle, no Export edits.

**Basis:** Explicit source drift test, not a booking consumer.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** existing CRM45 classification suite on current HEAD (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E068 | NO_CHANGE | `plasticos_crm_sync/tests/test_orchestrator_upsert.py`

**Owner / stage:** CRM Sync; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_sync/tests/test_orchestrator_upsert.py#L1-L100. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Recent head added upsert behavior assertions.

**Decision:** Keep CRM upsert test unchanged; ensure no Export source links are introduced.

**Basis:** Current HEAD delta only, not Export integration.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** upsert idempotence and watermark regression unchanged (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E069 | NO_CHANGE | `plasticos_material_profile/__manifest__.py`

**Owner / stage:** Material Profile; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_material_profile/__manifest__.py#L1-L50. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Material Profile version 19.0.5.10.9 changed in latest HEAD.

**Decision:** No material registry schema/source changes needed for Export J1/E4; preserve current manifest.

**Basis:** Physical J1 identity never derives from material descriptions.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-MAT: preserve material registry and CRM import state; no export mutation.

**Verification:** module DAG and existing material normalization tests (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E070 | NO_CHANGE | `plasticos_material_profile/tests/test_material_normalizer.py`

**Owner / stage:** Material Profile; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_material_profile/tests/test_material_normalizer.py#L1-L100. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** New exact-phrase normalization regression in source drift.

**Decision:** Preserve source-level CRM matching golden tests, no Export modification.

**Basis:** No automatic material-grade inference in physical journey.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** full existing normalizer test suite executes unchanged (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E071 | NO_CHANGE | `plasticos_crm_bridge/models/material_profile.py`

**Owner / stage:** CRM Bridge; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_bridge/models/material_profile.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** The current material profile bridge computes transaction_count/total_revenue from supplier_profile_id or buyer_profile_id, then last_pickup_date via tx.load_id and existing pickup_datetime in picked_up/delivered/closed states.

**Decision:** Preserve that exact commercial relation and existing pickup_datetime display semantics. J1-only activity never creates a transaction or commercial revenue and is not added to the CRM statistic. No change to lead-owned/facility-owned material-profile APIs.

**Basis:** Exact current source confirms a real Logistics consumer, but the selected change preserves every field and relation it reads. New actual-event clocks do not silently redefine this historical CRM display.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** R-READ: no write expected; preserve CRM mappings and records; rollback only via full snapshot if unforeseen side effect.

**Verification:** V16/V18: existing transaction/load statistics unchanged; multiple feeders/J1s do not duplicate transaction revenue; no buyer or profile is manufactured by an Export operation. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E072 | EDIT | `config/odoo_module_order.yaml`

**Owner / stage:** Integration; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/config/odoo_module_order.yaml. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Default domestic install list excludes Native Documents; Enterprise list exists; reader supports named sections.

**Decision:** Add export_integration_modules as a named explicit test profile listing plasticos_export and its installed Enterprise prerequisites. Keep default_install_order, excluded_modules and legacy scopes unchanged. No production default install.

**Basis:** The new addon otherwise might not be included by the existing default test commands. A profile is sufficient; no new runner.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V12: named profile returns Export; default domestic profile unchanged; actual installed dependency registry includes documents/documents_account. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E073 | NO_CHANGE | `scripts/get_odoo_module_order.py`

**Owner / stage:** Integration; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/scripts/get_odoo_module_order.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Script reads arbitrary named YAML list via --section and discovers manifests for --all-installable.

**Decision:** Use its existing named-section support; do not add hard-coded Export to CUSTOM_DEFAULT or rewrite parsing. Explicit Enterprise profile avoids installing Export in domestic default.

**Basis:** Current source supports the required configuration extension without code changes.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V12: existing parser returns export_integration_modules and leaves default list unchanged. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E074 | NO_CHANGE | `plasticos_documents/migrations/19.0.2.2.0/pre-migrate.py`

**Owner / stage:** Documents; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/migrations/19.0.2.2.0/pre-migrate.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing future script renames legacy x_ columns; current Documents source manifest is 19.0.2.1.6.

**Decision:** Leave this historical/future script unchanged and do not traverse it for target 19.0.2.1.7. S1 compares actual installed versions and columns; if the tenant is already at or past the selected target, stop and rebind versions before coding, never opportunistically upgrade across this script.

**Basis:** Prevents an unnoticed version-range side effect and unrelated column rename from entering the change bundle.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V13: target-version range excludes 2.2.0; unexpected installed version/schema is a refusal with no guessed column rename. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E075 | NO_CHANGE | `plasticos_security_base/security/security_groups.xml`

**Owner / stage:** Security; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/security/security_groups.xml. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing group_logistics and group_operations_manager provide relevant roles; operations manager implies logistics_ops.

**Decision:** Reuse existing exact XML IDs. No new group, privilege, auto-membership or human-signature role is created. New model ACL rows live in Security Base and keep global company restrictions.

**Basis:** No new role is necessary to satisfy the current physical/operational responsibility.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V11: intended existing group implication works; group combinations cannot bypass global company rule. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E076 | EDIT | `plasticos_logistics/business_rules/README.md`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/business_rules/README.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Module-local index routes agents to source BRS, supersession and build plan.

**Decision:** Reference the exact implemented successor owner interface and the unchanged original BRS IDs after authorized realization; distinguish target behavior from runtime proof. No new approval actors.

**Basis:** New interop behavior must be discoverable at the actual module entry point rather than only in a private ZIP.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12: module reading path points to the updated supersession and owner contract without claiming tests ran. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E077 | EDIT | `plasticos_documents/business_rules/README.md`

**Owner / stage:** Documents; S3. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/business_rules/README.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Module-local index is shared by core Documents and Native bridge.

**Decision:** Reference the one authoritative scoped-evidence interface, current supersession and exact acceptance cases; preserve original 44 local BRS source texts and hashes.

**Basis:** Prevents a second shadow rule authority in Export.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12: original BRS hashes unchanged and both modules consume one Documents policy. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E078 | EDIT | `plasticos_logistics/LINDA_BUILD_PLAN.md`

**Owner / stage:** Logistics; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_logistics/LINDA_BUILD_PLAN.md. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Plan contains source-SO/company and existing owner assumptions used by agents.

**Decision:** Narrowly reconcile only assumptions superseded by exact buyerless company, typed Linda source and no-resend rules; retain other business requirements and their IDs. Add successor-source references, not a second rule registry.

**Basis:** The source search identifies this active consumer of the old SO-company assumption.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12: no old first-by-SO or four-hour packet-resend instruction remains operative for this campaign. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E079 | NO_CHANGE | `plasticos_transaction/models/native_document_import.py`

**Owner / stage:** Transaction; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/models/native_document_import.py#L1-L90. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Importer creates native sale/purchase/account documents from exact ERP source IDs; the term document here is commercial, not scoped evidence.

**Decision:** Do not alter its commercial order/invoice/bill mapping. New Export does not call it, create native orders from a booking, or import ISO identities from its trailer strings. Preserve import_mode and no-automation behavior through changed owner guards.

**Basis:** Semantic naming alone is not a dependency on the new verification-link model. Exact entrypoint purpose was inspected.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V16/V18: historical replay remains idempotent; no booking/J1/verification/SMTP created by import or inverse Export command. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E080 | EDIT | `tests/test_freight_context_service.py`

**Owner / stage:** Integration; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/tests/test_freight_context_service.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing pure freight-context regression surface asserts legacy context behavior.

**Decision:** Retain golden legacy v3 cases and add the distinct manual/no-intake context branch, version mismatch, unknown equipment and changed-source invalidation. Do not loosen required company or actual location identity.

**Basis:** Companion test obligation of RP-01-E004/E005.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V03: deterministic legacy bytes unchanged; valid manual new branch; no SAL qualification by missing stream. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E081 | BLOCKED | `runtime:installed-Odoo19-Enterprise-registry`

**Owner / stage:** Native Odoo; S1. **Source:** GitHub enterprise branch lookup in this completion session: 404; target registry not supplied.. **Observation scope:** UNOBSERVED_INSTALLED_TARGET.

**Before:** No exact installed Enterprise checkout/registry was accessed; GitHub enterprise branch lookup returned 404.

**Decision:** Perform read-only S1-TARGET inspection of named required models/fields/methods/views and existing provider overrides. Compare against the protected six-model/twelve-command target and source-owned native adapters. Match -> no plan expansion; mismatch -> exact affected rows blocked and re-plan before code.

**Basis:** This is a real target-evidence prerequisite, not a human signature or a demand that unwritten implementation tests pass.

**Migration:** Read-only observation only. Identify installed versions/schema and supported census classes; no schema/data change is authorized by S1.

**Recovery:** No business or schema write is permitted. Stop on unexpected write-capable access; preserve observation evidence and do not run actions, imports, mail, crons or upgrades.

**Verification:** S1-TARGET receipt: community/Enterprise SHAs, installed modules/versions, required field/type/view/ACL/native-Mail method coordinates, no write/test execution. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E082 | BLOCKED | `runtime:database-configured-actions-and-upgrade-census`

**Owner / stage:** Integration; S1. **Source:** Not present in repository or supplied artifacts; mandatory read-only target census.. **Observation scope:** UNOBSERVED_INSTALLED_TARGET.

**Before:** Database-only base.automation/server actions/cron overrides/ACLs/aliases and actual legacy company/source conflicts are not visible in Git source.

**Decision:** In S1 inspect read-only metadata and source-census partitions for the exact target clone. Every active record on an affected model must map to the source file policy, be disabled-by-design, or receive an explicit change/no-change row. Run no live actions. Counts alone are not code blockers; an unsupported schema/data class or unplanned dynamic caller is.

**Basis:** A repository grep cannot prove the absence of database-defined consumers. This boundary remains explicit instead of a false exhaustive-census claim.

**Migration:** Read-only observation only. Identify installed versions/schema and supported census classes; no schema/data change is authorized by S1.

**Recovery:** No business or schema write is permitted. Stop on unexpected write-capable access; preserve observation evidence and do not run actions, imports, mail, crons or upgrades.

**Verification:** S1-TARGET receipt: exact record IDs/model/code hash/active flag/owner, installed-version comparison, each census class counted with mapped disposition; clone identity and no writes. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E083 | EDIT | `scripts/test_env.sh`

**Owner / stage:** Integration; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/scripts/test_env.sh#L1040-L1175. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** test_scope accepts only the default roster; run_tests upgrades that roster. A newly optional Export addon is currently refused, and a named YAML section alone is inert.

**Decision:** Extend the EXISTING owned-clone test path to recognize explicitly selected export_integration_modules. Keep the admitted base template and its fingerprint unchanged. Install the declared Export extras only on a separately owned neutralized clone, then upgrade/test the base plus selected extras; actual effective roster is recorded in the existing receipt upgraded/scope values. Reject undeclared extras and default domestic tests on an Export-populated clone. Keep leases, ownership, fingerprint, dirty-source and zero-test refusals. No new runner or template-replacement shortcut.

**Basis:** The current script proves that config-only test wiring would be incomplete. This narrow clone-only extension reaches the new addon without widening production installation.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V12: explicit Export selection installs/tests it on its clone; domestic base clone remains without Export; unknown module/foreign DB/stale fixture/zero tests refuse; template untouched. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E084 | EDIT | `tests/test_test_env_safety.py`

**Owner / stage:** Integration; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/tests/test_test_env_safety.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Existing safety suite exercises test_env.sh with stub local inputs and named roster.

**Decision:** Add negative and positive fixtures for the explicit Export clone-only extension: unchanged base template identity, unknown extra refused, cross-scope clone contamination refused, effective upgrade roster includes Export only when selected, existing target/lease/fingerprint guards unchanged. Tests of the harness do not substitute for real Enterprise runtime.

**Basis:** Companion obligation of the actual runner change, not a new execution framework.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V12/V17: known-bad extra/target/profile cases fail before any Docker/database operation; permitted owned clone path passes harness. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E085 | EDIT | `plasticos_claims/tests/test_state_machines.py`

**Owner / stage:** plasticos_claims; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_claims/tests/test_state_machines.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Exact-source search identifies direct load transitions in these downstream positive-flow fixtures.

**Decision:** Bring the positive physical-release fixtures into the accepted source-company, current freight and attributable readiness/evidence contract. Preserve original assertions and add the missing bypass-denial counterpart where the fixture called a lower-level transition. No fake buyer/source, no skip, no weakened security or financial assertion.

**Basis:** A strengthened upstream state guard changes the fixture prerequisites even where commercial production logic is unchanged.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V01/V04/V09: original domain assertion still passes with real required fixture facts; absent facts deny rather than bypass. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E086 | EDIT | `plasticos_claims/tests/test_integration_flows.py`

**Owner / stage:** plasticos_claims; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_claims/tests/test_integration_flows.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Exact-source search identifies direct load transitions in these downstream positive-flow fixtures.

**Decision:** Bring the positive physical-release fixtures into the accepted source-company, current freight and attributable readiness/evidence contract. Preserve original assertions and add the missing bypass-denial counterpart where the fixture called a lower-level transition. No fake buyer/source, no skip, no weakened security or financial assertion.

**Basis:** A strengthened upstream state guard changes the fixture prerequisites even where commercial production logic is unchanged.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V01/V04/V09: original domain assertion still passes with real required fixture facts; absent facts deny rather than bypass. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E087 | EDIT | `plasticos_security_base/tests/test_action_methods.py`

**Owner / stage:** plasticos_security_base; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_security_base/tests/test_action_methods.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Exact-source search identifies direct load transitions in these downstream positive-flow fixtures.

**Decision:** Bring the positive physical-release fixtures into the accepted source-company, current freight and attributable readiness/evidence contract. Preserve original assertions and add the missing bypass-denial counterpart where the fixture called a lower-level transition. No fake buyer/source, no skip, no weakened security or financial assertion.

**Basis:** A strengthened upstream state guard changes the fixture prerequisites even where commercial production logic is unchanged.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V01/V04/V09: original domain assertion still passes with real required fixture facts; absent facts deny rather than bypass. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E088 | EDIT | `plasticos_commission/tests/test_golden_flows.py`

**Owner / stage:** plasticos_commission; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_commission/tests/test_golden_flows.py. **Observation scope:** PRIOR_OWNER_OBSERVATION_REUSED_AFTER_UNCHANGED_BLOB_COMPARE.

**Before:** Exact-source search identifies direct load transitions in these downstream positive-flow fixtures.

**Decision:** Bring the positive physical-release fixtures into the accepted source-company, current freight and attributable readiness/evidence contract. Preserve original assertions and add the missing bypass-denial counterpart where the fixture called a lower-level transition. No fake buyer/source, no skip, no weakened security or financial assertion.

**Basis:** A strengthened upstream state guard changes the fixture prerequisites even where commercial production logic is unchanged.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V01/V04/V09: original domain assertion still passes with real required fixture facts; absent facts deny rather than bypass. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E089 | NO_ADD | `scripts/run-odoo-tests.sh`

**Owner / stage:** Integration; S1. **Source:** Exact pinned-revision GitHub fetch of scripts/run-odoo-tests.sh returned 404 in this completion session.. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** Comments and generated historical indexes name this path, but exact GitHub fetch at the pinned revision returns 404.

**Decision:** Do not create, call or delegate this nonexistent script. Bind verification to the actually present scripts/test_env.sh and explicit module reader. Historical comments/indexes are not executable authorities.

**Basis:** Command existence was checked, not assumed. No new script is needed.

**Migration:** No new file/schema/data transition for this rejected path. Any replacement is a separately enumerated effect; historical paths are not overwritten.

**Recovery:** No effect is executed for this proposal. Preserve the prior archive and any already-existing migration source.

**Verification:** V17: handoff contains no executable instruction naming the absent script. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E090 | CREATE | `docs/adr/ADR-129-export-physical-evidence-and-owner-contracts.md`

**Owner / stage:** Integration; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/README.md. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** No current ADR records the selected Export/J1/J2 cross-module schema and one-writer boundaries.

**Decision:** Record the already-selected E1-E4/J1-J2 meanings, source-company ownership, exact owner signatures, typed evidence and Linda handoff, acyclic addon direction, optional-install boundary and source-bound references. Reference original BRS and protected technical contract, do not copy private originals or invent new business rules.

**Basis:** The current docs/adr/README.md explicitly requires an ADR for cross-module and expensive schema choices. A module BRS does not replace the repository architecture owner.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12/V17: one ADR, exact source/contract digests, canonical index and agent links; no new authority or duplicated normative rule. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E091 | EDIT | `ARCHITECTURE.md`

**Owner / stage:** Integration; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/README.md#L47-L61. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** The repository ADR procedure requires its architecture table to index each binding architecture record.

**Decision:** Add only the ADR-129 entry and its exact addon ownership/dependency reference needed for this campaign. Preserve unrelated topology and existing decisions.

**Basis:** Mandatory companion of the new ADR under docs/adr/README.md; not a broad architecture rewrite.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12/V17: ADR table resolves to the same single record and unchanged original contract. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E092 | EDIT | `AGENTS.md`

**Owner / stage:** Integration; S2. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/AGENTS.md#L1-L15. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** The current task read path covers Linda BRS; canonical ADR procedure requires an agent link for cross-module task classes.

**Decision:** Add the Export/J1/J2 task read path to ADR-129, module-local BRS supersessions and the new Export README. Update affected derived addon counts only from the realized source census. Preserve unrelated commands/skills/governance; no invented approval or new execution ceremony.

**Basis:** Makes the selected decisions reachable to actual repository agents at their existing entrypoint.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12/V17: task path resolves; no duplicate BRS authority or private pack ingestion; unchanged publication boundary. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E093 | CREATE | `plasticos_export/README.md`

**Owner / stage:** Export; S5. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/README.md. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** The new addon is absent; its earlier proposed file tree already includes a README.

**Decision:** Document addon purpose, supported manual workflows, dependency/installation-off boundary, ADR-129 and preserved BRS references, exact test scope, and public-versus-private pack boundary. Do not repeat all normative rules or claim implementation tests passed before evidence exists.

**Basis:** A new addon needs its own declared reading/usage path; existing module READMEs cannot own the downstream Export installation boundary.

**Migration:** Documentation-only effect: no database or business-record transformation. Preserve original source-rule bytes; register exact successor references after separate repository edit authorization.

**Recovery:** Restore the prior documentation bytes/index links if rejected; no database restore or runtime action is induced by this documentation effect.

**Verification:** V12/V17: reader reaches the actual owner contracts, no optional feature expansion, private originals never listed as repository payload. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E094 | CREATE | `plasticos_documents/migrations/19.0.2.1.7/pre-migrate.py`

**Owner / stage:** Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json ; https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/__manifest__.py. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** Operation-scope fields are absent; current rows already carry exact association/digest and legacy decision history.

**Decision:** Census legacy source/digest/subject classes, snapshot eligibility and financial totals, and verify installed baseline is the reconciled 2.1.6 schema. Abort on unsupported version or contradictory source. Never overwrite 2.1.4 history or cross future 2.2.0.

**Basis:** Needed before adding constrained operation-scope dimensions to the existing owner.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V13: supported baseline proceeds; wrong schema/version and conflicting accepted evidence refuse before mutation. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E095 | CREATE | `plasticos_documents/migrations/19.0.2.1.7/post-migrate.py`

**Owner / stage:** Documents; S3. **Source:** WORKING_PACK::EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json ; https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/__manifest__.py. **Observation scope:** PROPOSED_NOT_INSTALLED.

**Before:** New scope fields must preserve all existing accepted/default legacy meanings.

**Decision:** Classify existing rows as legacy without changing accepted actor/time/source digest. Do not infer quantity_known/UoM or operation_revision_key from old covered_quantity or checksum; new explicit operation rows begin only from attributed source. Validate constraints, exact currentness equivalence and original hashes.

**Basis:** Keeps existing financial/document meaning while separating new operation evidence.

**Migration:** See the owner-specific migration/recovery table; no state may be inferred from installation.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V13: same legacy eligibility/totals before and after; idempotent rerun; unknown operation quantity remains unknown. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E096 | NO_CHANGE | `plasticos_documents/migrations/19.0.2.1.4/post-migrate.py`

**Owner / stage:** Documents; S1. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/migrations/19.0.2.1.4/post-migrate.py. **Observation scope:** PINNED_SOURCE_ANCHOR_INSPECTED.

**Before:** Merged migration preserves proven historical subjects and marks unproven links review.

**Decision:** Preserve this migration unchanged; it is not reimplemented in the Export successor. The supported baseline is already 2.1.6; older installed state requires its own baseline upgrade proof before this campaign.

**Basis:** No rewrite of admitted historical migration behavior.

**Migration:** No data/schema rewrite by this effect. Preserve its current semantics; run the named compatibility witness after the owner migration. If the same file changes for another effect, apply its migration obligations there.

**Recovery:** Before any irreversible external effect, restore the coherent pre-upgrade DB+filestore+code/config set on failure; after a possibly sent message retain unknown/history and use explicit reconciliation, not blind rollback/replay.

**Verification:** V13: chosen 2.1.6 -> 2.1.7 range excludes 2.1.4; earlier upgrade evidence not fabricated. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E097 | NO_CHANGE | `plasticos_documents/tests/test_account_move_transaction_link.py`

**Owner / stage:** plasticos_documents; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/test_account_move_transaction_link.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E098 | NO_CHANGE | `plasticos_documents/tests/test_exact_association.py`

**Owner / stage:** plasticos_documents; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/test_exact_association.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E099 | NO_CHANGE | `plasticos_documents/tests/test_native_verification_delegation.py`

**Owner / stage:** plasticos_documents; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/test_native_verification_delegation.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E100 | NO_CHANGE | `plasticos_documents/tests/test_pr322_findings.py`

**Owner / stage:** plasticos_documents; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/test_pr322_findings.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E101 | NO_CHANGE | `plasticos_documents/tests/test_verification_writer.py`

**Owner / stage:** plasticos_documents; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_documents/tests/test_verification_writer.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E102 | NO_CHANGE | `plasticos_transaction/tests/test_compliance_does_not_post.py`

**Owner / stage:** plasticos_transaction; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/tests/test_compliance_does_not_post.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

#### RP-07-E103 | NO_CHANGE | `plasticos_transaction/tests/__init__.py`

**Owner / stage:** plasticos_transaction; S6. **Source:** https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_transaction/tests/__init__.py. **Observation scope:** CURRENT_COMPARE_INVENTORY_AND_OWNER_CONTRACT_RECONCILED.

**Before:** Current merged baseline includes this regression/loader for exact association, one writer or observational compliance.

**Decision:** Retain baseline expectations and test source. New operation fields default to legacy for existing callers; all existing APIs and non-posting assertions remain. Run the suite alongside new scoped cases rather than weaken assertions or replace approved tests.

**Basis:** The new scope is additive and isolated from exact legacy behavior. Compare inventory confirms the changed baseline test; expected public behavior is preserved, not reinterpreted.

**Migration:** Test-only file: no production schema/data migration. Fixture data is created only in an owned isolated test database; no seed-data rewrite.

**Recovery:** Discard/recreate only the authorized test clone on fixture failure; preserve logs and exact source evidence. Never weaken assertions or alter production data to obtain a pass.

**Verification:** V08/V09/V12/V18: unchanged baseline suite runs with original positive/negative semantics and no skipped failures. (V12, V13, V14, V16, V17, V19; NOT_RUN).

## Original audit finding disposition

No original finding is erased. Remediation planning is not implementation closure. The original audit remains historical evidence at its original revision.

| Finding | Mapped effects | Disposition |
| --- | --- | --- |
| F-001 | RP-07-E065 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-002 | RP-01-E001, RP-02-E001, RP-06-E004, RP-06-E005, RP-06-E006, RP-06-E007, RP-07-E024, RP-07-E029 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-003 | RP-03-E007, RP-03-E008, RP-03-E009 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-004 | RP-03-E010, RP-03-E015, RP-03-E017, RP-03-E018 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-005 | RP-04-E001, RP-04-E002, RP-04-E003, RP-04-E004, RP-04-E008, RP-04-E009 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-006 | RP-03-E001, RP-03-E006, RP-03-E015, RP-03-E019, RP-03-E020, RP-04-E010 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-007 | RP-03-E001, RP-03-E002, RP-03-E003, RP-03-E004, RP-03-E005, RP-03-E016, RP-07-E044 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-008 | RP-01-E003, RP-01-E004, RP-01-E005, RP-01-E006, RP-01-E007, RP-01-E008, RP-01-E009 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-009 | RP-02-E011, RP-05-E002, RP-05-E022, RP-05-E023, RP-05-E024, RP-05-E025, RP-07-E005 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-010 | RP-05-E026, RP-05-E027, RP-06-E008, RP-07-E028 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-011 | RP-05-E001, RP-05-E003, RP-05-E004, RP-05-E005, RP-05-E006, RP-05-E007, RP-05-E008, RP-05-E009, RP-05-E015, RP-07-E008, RP-07-E009 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-012 | RP-01-E001, RP-02-E004, RP-02-E005, RP-06-E001, RP-06-E002, RP-06-E003, RP-06-E008, RP-07-E006, RP-07-E012, RP-07-E015, RP-07-E047, RP-07-E048 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-013 | RP-05-E001, RP-05-E010, RP-05-E011, RP-05-E012, RP-05-E014, RP-05-E017, RP-05-E018, RP-05-E019 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-014 | RP-02-E001, RP-02-E003, RP-05-E013, RP-05-E016, RP-05-E020, RP-06-E009, RP-07-E001, RP-07-E002, RP-07-E003, RP-07-E004, RP-07-E006, RP-07-E007, RP-07-E008, RP-07-E009, RP-07-E010, RP-07-E011, RP-07-E012, RP-07-E013, RP-07-E014, RP-07-E016, RP-07-E017, RP-07-E018, RP-07-E019, RP-07-E031, RP-07-E032, RP-07-E057, RP-07-E058, RP-07-E059, RP-07-E060, RP-07-E061, RP-07-E062 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-015 | RP-01-E010, RP-01-E011, RP-01-E012, RP-01-E013, RP-01-E014, RP-02-E008, RP-02-E009, RP-02-E010, RP-03-E011, RP-03-E012, RP-03-E013, RP-03-E014, RP-06-E004, RP-06-E006, RP-07-E024, RP-07-E025, RP-07-E030, RP-07-E037, RP-07-E038, RP-07-E071 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-016 | RP-07-E026, RP-07-E027, RP-07-E066, RP-07-E067, RP-07-E068, RP-07-E069, RP-07-E070, RP-07-E071 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-017 | RP-02-E002, RP-02-E006, RP-07-E036, RP-07-E039, RP-07-E040, RP-07-E041, RP-07-E042, RP-07-E043, RP-07-E044, RP-07-E045, RP-07-E046, RP-07-E049, RP-07-E050, RP-07-E051, RP-07-E052, RP-07-E053, RP-07-E054, RP-07-E055, RP-07-E056, RP-07-E063 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-018 | RP-07-E033, RP-07-E034, RP-07-E035, RP-07-E064, RP-07-E065 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |
| F-019 | RP-02-E001, RP-02-E007, RP-03-E005, RP-03-E020, RP-04-E001, RP-04-E002, RP-04-E004, RP-04-E005, RP-04-E006, RP-04-E007, RP-04-E008, RP-04-E010, RP-05-E002, RP-05-E014, RP-05-E021, RP-07-E001, RP-07-E003, RP-07-E020, RP-07-E021, RP-07-E022, RP-07-E023, RP-07-E031, RP-07-E039, RP-07-E040, RP-07-E047, RP-07-E058, RP-07-E059, RP-07-E060, RP-07-E061, RP-07-E062 | REMEDIATION_PLANNED_NOT_IMPLEMENTED; installed-target and runtime proof not inferred |

## Current-source advancement: all 24 changed paths

| Path | Plan effects | Active disposition |
| --- | --- | --- |
| `plasticos_documents/__manifest__.py` | RP-07-E002 | EDIT |
| `plasticos_documents/migrations/19.0.2.1.4/post-migrate.py` | RP-07-E096 | NO_CHANGE |
| `plasticos_documents/models/compliance_service.py` | RP-05-E003 | EDIT |
| `plasticos_documents/models/document.py` | RP-05-E001 | EDIT |
| `plasticos_documents/models/transaction_docs_bridge.py` | RP-05-E028 | EDIT |
| `plasticos_documents/tests/__init__.py` | RP-05-E016 | EDIT |
| `plasticos_documents/tests/test_account_move_transaction_link.py` | RP-07-E097 | NO_CHANGE |
| `plasticos_documents/tests/test_exact_association.py` | RP-07-E098 | NO_CHANGE |
| `plasticos_documents/tests/test_native_verification_delegation.py` | RP-07-E099 | NO_CHANGE |
| `plasticos_documents/tests/test_pr322_findings.py` | RP-07-E100 | NO_CHANGE |
| `plasticos_documents/tests/test_verification_writer.py` | RP-07-E101 | NO_CHANGE |
| `plasticos_documents/views/document_views.xml` | RP-05-E012 | EDIT |
| `plasticos_documents_native/__manifest__.py` | RP-07-E003 | EDIT |
| `plasticos_documents_native/migrations/19.0.1.2.6/pre-migrate.py` | RP-07-E010 | NO_CHANGE |
| `plasticos_documents_native/models/document_native.py` | RP-05-E017 | EDIT |
| `plasticos_documents_native/models/document_sync.py` | RP-05-E018 | NO_CHANGE |
| `plasticos_documents_native/tests/__init__.py` | RP-05-E020 | NO_CHANGE |
| `plasticos_documents_native/tests/test_native_search_parity.py` | RP-05-E031 | EDIT |
| `plasticos_documents_native/tests/test_verification_delegation.py` | RP-05-E030 | EDIT |
| `plasticos_documents_native/views/document_native_views.xml` | RP-05-E019 | NO_CHANGE |
| `plasticos_transaction/__manifest__.py` | RP-07-E030 | NO_CHANGE |
| `plasticos_transaction/models/transaction.py` | RP-01-E010, RP-03-E022 | NO_CHANGE |
| `plasticos_transaction/tests/__init__.py` | RP-07-E103 | NO_CHANGE |
| `plasticos_transaction/tests/test_compliance_does_not_post.py` | RP-07-E102 | NO_CHANGE |

## Source and assurance scope

Primary basis is the predecessor ZIP, its unchanged operator invariant/business rules/technical contract, the original source-bound audit, and pinned repository owner code. Final source recheck discovered and reconciled the Documents merge, rather than silently certifying the old baseline. Public Odoo documentation was used only for native test-discovery and migration-stage/version semantics; installed Enterprise behavior remains S1-TARGET.

Official technical references:
- Odoo 19 testing: https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html
- Odoo 19 unit-test tutorial: https://www.odoo.com/documentation/19.0/developer/tutorials/unit_tests.html
- Odoo 19 upgrade scripts: https://www.odoo.com/documentation/19.0/developer/reference/upgrades/upgrade_scripts.html

No assertion is made that a source comment, a merged commit, a manifest hash, an Odoo-generated report or this pack's structural check proves runtime correctness. Review is single-session and not independent cognition. Canonical GAR projection/authority-consumption conformance is not certified. The current task never authorized product code, repository edits, PR/merge, migrations, live messages or deployment.

**Bounded next transition:** obtain the C09 read-only S1-TARGET observations against the actual authorized Enterprise target, reconcile any mismatch to this exact plan, and only then consider a separate coding grant. The expected observations and all later verification stages are already specified; another broad architecture expansion is not needed.

# PlasticOS | six corrective seams and owner decisions

**Status:** operator-directed remediation targets; this file makes **design proposals**, not code changes, accepted ADRs, permission grants, or a release. **Code source:** `cryptoxdog/IB-Odoo_19 Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`. **Current constitutional authority:** repository `INVARIANTS.md` v2.2.0 and Accepted ADRs. **Target design:** working candidate POS-INV v3.3.0.

## 1. FIX-DOC-WRITER | Single decision writer for business verification

**Observed:** [`plasticos_documents/models/document.py`](<https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/models/document.py>) owns `plasticos.document.verified`, `verified_by`, `verified_at`, `override` plus `action_verify`. [`plasticos_documents_native/models/document_native.py`](<https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents_native/models/document_native.py>) separately defines and writes those same business states on `documents.document`, including a distinct `action_override`. These surfaces can disagree. File custody is not verification authority.

**Resolution chosen as working architecture:** `plasticos_documents` is the sole semantic and mutation owner of documentary business evidence decisions. Native `documents.document` / `ir.attachment` owns originals, versions and UI but acts as a *delegate* (verified command) or *projection* (read-only display) for verification/override. A single decision must bind original/document revision, company/party, typed evidence subject and coverage, actor, time, authorization, reason and outcome. The domain owner decides expiry/supersession; no native bridge writes a second verified truth.

**Migration design gate:** inventory existing values on both models. Classify same/reconcilable/conflicting/no-binding rows, preserve original approvals and overrides, quarantine conflicts, and establish one canonical source before making an old field a projection. Do not drop historical booleans or timestamps without an admitted preservation/migration contract. Preserve native Documents original identity and original attachment bytes. Recompute compliance only through a side-effect-free operation-scoped evaluator. The exact schema and API are implementation-owner choices, not specified as installed Odoo features here.

**Negative controls:** native verify without authorized Docs role; native status differs from business owner; reupload inherits previous signature; AI auto-tag marks verified; expired superseded evidence closes invoice; verification side effect sends mail or posts. **BRS:** `BRS-POS-03-R001/R004/R005/R006/R007/R008`; native source `BRS-POS-02-R001/R005/R007`.

## 2. FIX-DOC-RECENCY | Remove guessed authoritative links

**Observed:** `documents.document._auto_link_partner` searches by partner, newest open `plasticos.transaction` and immediately writes `transaction_id` and potentially `load_id`. This is an impermissible inference when a partner has multiple orders, loads, or legal-company contexts.

**Resolution chosen as working architecture:** partner/date, AI suggestions and OCR are only **candidates**. The native bridge may preserve an inbound original and propose a link; it cannot accept it. The `plasticos_documents` evidence owner accepts typed links backed by independently checked source message/booking/PO/SO/load/picking identifiers, legal company, counterparty, purpose, revision and quantity coverage. Require correct object existence and the current authorization of that object's domain owner. A native `Linked to` pointer is navigation, not a one-file-one-business-fact invariant.

**Failure behavior:** if ambiguous, preserve file in native Inbox, status `UNMATCHED` or `CANDIDATE_CONFLICT`, with one internal review Activity for the exact obligation and revision. Never select latest record, fabricate a load or copy original files to get a second link. Partial receiving can justify a bounded quantity on one load without marking siblings complete. PO-only inbound links to real PO/picking without transaction or SO. An amended source revision changes only dependent links.

**Migration design gate:** inventory old auto-linked rows by source proof, mark insufficiently evidenced links for review instead of silently auto-accepting, protect native originals and verified historical evidence. Reconcile company scope and existing documented compliance before any bulk change. **BRS:** `BRS-POS-02-R001/R006/R007`, `BRS-POS-03-R002/R003/R005/R010`, `BRS-07-R047`.

## 3. FIX-LOG-MULTILOAD | Repair an incorrect universal cardinality assumption

**Observed:** `plasticos.transaction.load_id` is one slot; its SQL unique constraint forbids *a load owned by two transaction rows* but does **not** itself enforce one load per business transaction. The Many2one field permits each transaction to reference only one load. `load.create` links only the first eligible load when transaction.load_id is empty, leaving further real loads outside that legacy bridge. `_check_load_requires_supplier_buyer` requires both parties, and `plasticos.load.company_id` is related to `sale_order_id.company_id`. `plasticos.claim.load_id` is related to `transaction_id.load_id`, so the old one-load projection propagates into claims. This combination is the actual limitation; do **not** misdescribe the SQL uniqueness constraint as a one-to-one proof on its own.

**Resolution chosen as working architecture:** preserve native PO/SO and Stock as commercial and physical truth. A commercial transaction can have zero, one or many attributable physical load records, each with explicit quantities and native movement/picking evidence. If one physical load covers more than one economic allocation, use a separately authorized allocation relationship rather than relabeling booking as load or creating multiple physical duplicates. Different loads can legitimately share a sales order and transaction. Buyer-optional PO-only receipts stay native PO/picking scoped and do not need `plasticos.load`; if later admitted, dedicated load-like operations cannot borrow fake buyer/SO.

**Migration design gate:** enumerate every read/write of `transaction.load_id`, `load.transaction_id`, related claim/load fields, document rules, freight events, dashboards, reports, inventory, commissions, security, UI and external contracts. Choose smallest native Odoo-compatible relationship with stable IDs. Legacy `load_id` can serve as a compatibility read **only when exactly one eligible load**; multi-load views must not choose an arbitrary 'first' load. Preserve all historical links, payloads and financial entries. Revisit the SQL unique guard only when the new relationship ownership/cardinality is proven, not by dropping it reflexively. Use compatible versioned migrations and lossless backfill ledger, no automatic historical revaluation. Separate multiple physical load identity from future many-to-many *booking grouping*, which remains Export-deferred.

**Activation scope:** this is a **required PlasticOS foundation repair** for any multi-load domestic workflow, not an Export project. Do not claim the current one-load MVP is production-proven for multi-load behavior. It can stay on a separately authorized MVP remediation lane while Export/mobile/scale/warehouse stays parked. **BRS:** `BRS-01-R001/R002/R065`, `BRS-07-R047`, `POS-INV-10/11/21/22`.

## 4. DEC-SEED | Deterministic seed doctrine, not universal `noupdate`

**Observed constitutional conflict:** v2.2 invariant 4 states **all** XML reference data uses `noupdate=1`; real Odoo module rules and `plasticos_documents/security/security.xml` use `noupdate=0`; `plasticos_crm_bridge` uses adoption functions and migrations. An undifferentiated rule either overwrites user-owned references or blocks legitimate version-owned corrections.

**Proposed owner decision:** keep external IDs and XML/incremental migrations deterministic, but classify **each family** as `operator-owned immutable`, `module-upgrade-owned`, or `adopt-existing-with-verified-identity`. `noupdate=1` is appropriate to protect intended operator-managed state; `noupdate=0` applies only to explicitly version-owned upgrade state; migrations must be guarded and replay-safe. For mixed lifecycle fields, a documented field-level strategy and truth-preserving migration is necessary. No indiscriminate runtime seed generators, guessed IDs or duplicates. No change to BAN001. **Status:** resolved at draft-design level; constitutional revision requires operator approval.

**Falsifiers:** repeated upgrade changes manually edited customer-owned reference data; `noupdate=1` prevents necessary role group updates; another Buyer `crm.tag` appears; missing external ID silently creates duplicate; old v2.2 CI guards disappear.

## 5. DEC-GATE | Separate startup isolation from failed business results

**Accepted authority already resolves semantic policy.** `docs/adr/ADR-003-single-external-intelligence-authority.md` and `docs/adr/ADR-013-fail-closed-gate-transport.md` are Accepted. The v2.2 language 'Graph failures return empty results' is obsolete **when it means business success**. Odoo's registry may start when Gate/Neo4j is unavailable, but runtime matches/converge must classify retryable/permanent/unknown, preserve durable audit, surface degraded/failed state and decline success/writeback. No local matcher or direct CEG/EIE egress.

**Status:** semantic conflict resolved by accepted ADR, repository invariant wording still needs a no-loss amendment, runtime conformance still **UNKNOWN**. This is an authority-consistency correction, not a fresh AI design decision.

**Falsifiers:** Gate HTTP 503 shown as successful zero matches; CRM fields overwritten on timeout; silent in-Odoo local matching; Graph outage blocks registry startup; successfully completed empty result mistakenly counted as transport failure.

## 6. DEC-ACL | Least-privilege operating policy with workflow preservation

**Source:** `plasticos_documents`, `plasticos_claims`, and `plasticos_transaction` ACL CSVs give all internal users broad full-CRUD rows. Odoo ACL grants are additive. A later narrow row or a nonexistent group rule cannot revoke a broad grant. The October 25 `pr303-cursor-handoff/security-acl-brief.md` records both serious exposure and how naive deletion would break document-upload claim creation and transaction CSV import. The operator previously required a separate role policy.

**Proposed minimum policy, not yet admitted:**

| Actor / domain | Read | Create | Update | Delete | Protected authority |
|---|---|---|---|---|---|
| `base.group_user` only | own permitted native business projections | only safe standard intake commands | no claims/transaction line/verified evidence edits | no privileged deletion | No implicit admin/financial authority |
| Documents uploader | permitted own/company documents | upload original/metadata candidate | own draft/candidate metadata only | no historical verified evidence deletion | **Cannot verify/override** |
| Documents verifier | company-scoped current evidence | verification record via owner command | revoke/supersede with audit | no delete original/evidence history | Attribute actor/revision |
| Documents manager | approved override on correct company | as permitted | override with required reason | never erase audited original | Explicit manager group |
| Claims user / QC | company-scoped authorized claims | report/prepare claims, including from authorized upload | case facts under lifecycle policy | **no claim unlink** | Cannot independently recognize a credit |
| Claims manager | assigned/authorized claims | case management | resolution/escalation | only if business/retention policy explicitly permits | Financial recognition separate |
| Sales rep | own transaction + lines read per company | only approved source-owned mutations | no historical line write | no historical line delete | Cannot self-edit commission inputs |
| Logistics importer role | permitted transaction/line scope | all-or-nothing native import through verified command | source-bounded before posting/close | no history delete | No partial closed headers without lines |
| Accounting/authorized financial role | scoped document/line read | native accounting operation only | authorized adjustments | native accounting retention only | No Docs/Claims economic write-through |
| System admin | recorded and scoped platform maintenance | explicit administrative path | audited security/config changes | platform policy as explicitly approved | No silent cross-company access |

These are **policy proposals**. The user/role owner must approve exact groups, company scopes, whether claim creators may update recoveries and whether a given manager can delete any claim, after real Odoo 19 effective-ORM tests. Existing `plasticos_security_base` groups imply `base.group_user`; implication must be included in permission proofs. Prevent identity XMLID changes by all internal users. Review `product.template` exposure as separately tracked high risk. Do **not** add a broad `sudo()` to fix uploads or import, delete all ACL rows blindly, or build a second permission engine. Restrict **business commands**, then adjust native ACL/record rules with audit and meaningful denial cases.

**Required migration/workflow witnesses:** single upload that creates one authorized claim, unauthorized internal-only user cannot read claims; authorized claims user cannot unlink; sales/other internal-only cannot rewrite historical transaction lines; authorized CSV importer creates complete transaction+lines with atomic rollback on permission error; all company-scoped permissions reject foreign records; DOC manager override requires reason; native file access does not leak buyer/supplier originals.

## Mandatory boundaries for all six

- The **source defect** is confirmed where code proves a competing writer, recency linkage or singular field. **Actual database exposure/population/behavior and Enterprise tests are NOT_RUN/UNKNOWN** until a real receipt exists.
- Safety fixes require their own **approved coding scope and projection/validation receipts**; this pack does not authorize mutation, pushing, PR creation, merge or production release.
- Any Code Agent contract must cite exact current source head at execution time; source SHA in this pack is a read-only comparison baseline, **not** a claim that it remains the execution head.
- **Export, drayage buildout, warehouse/shop-floor, QR and scale integrations remain PARKED.** No capability's proposal grants live AI, communications, stock dispatch, accounting posting, or worker activation.

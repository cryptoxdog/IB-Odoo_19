# PlasticOS Export v2.7: Existing-addon change map

**Status:** Architecture implementation map, read-only proposal. No repository change is authorized or performed by this document.
**Pinned source:** `cryptoxdog/IB-Odoo_19`, `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`.
**Product source:** `PlasticOS_Export_Technical_Architecture_Closure_v2.7.0.zip`, `MODULE_DESIGN/TECHNICAL_CLOSURE_v2.7.md`.
**Authority:** Current repository `INVARIANTS.md` v2.2.0 remains constitutional; v3.3.0 draft is working context only. No source-owner adoption or Enterprise run is claimed.

## 1. Modify existing files in source-owning addons

### `plasticos_logistics` (primary owner)

| Path | Change | Status |
| --- | --- | --- |
| `models/load.py` | Replace SO-derived `company_id` with stable authorized source company; forbid first-transaction-by-SO guesses; keep real load state owner and central release/packet checks. | Required |
| `models/transaction_inherit.py` | Preserve valid UNIQUE(load_id); make buyerless PO/stock-authorized movement compatible; expose exact association operation without broad cardinality rewrite. | Required |
| `models/freight_governance.py` | Remove company fallback that could silently assign freight evidence to `env.company`; validate exact source company. | Required for company-safe provenance |
| `models/dispatch.py` | Reuse source-owner physical release check in its separate dispatch state path, rather than leaving an unguarded transition. | Required if path remains active |
| `models/linda_request.py` | Adopt non-PO/SO booking subject, purpose, revision, recipient, idempotency and CHECK/UNIQUE migration; preserve native PO/SO behavior and unknown-send rules. | Required |
| `models/linda_response.py` | Make exact native-reply ancestry capable of binding legitimate booking responses without requiring a fictitious PO/SO. | Required for booking inbound scope |
| `models/mail_mail_inherit.py` | Verify central send-time check covers booking-source and old composer/direct-send paths; modify only if the owner hook is insufficient. | Conditional on proof |
| `services/freight_context.py` | Bind company to approved source and real equipment where relevant; preserve SAL abstention when buyerless context lacks a proven repeat stream. | Conditional on freight scope |
| `models/__init__.py` | Register J1/J2 model implementation. | Required |
| `security/ir.model.access.csv` | ACLs for J1/J2 physical identity and sources. | Required |
| `security/record_rules.xml` | Global company restrictions for J1/J2; group-specific roles remain with Security Base. | Required |
| `__manifest__.py` | Version bump, register any J1 UI, preserve acyclic depends. | Required |
| `tests/__init__.py`, `tests/test_load_cardinality.py` | Register new tests; preserve legacy valid load/cardinality tests and add ambiguous-SO/buyerless negatives. | Required |
| `__init__.py` | Verify whether installed Odoo 19 Enterprise actually discovers tests without a root `from . import tests`; amend only if required by the observed loader. | Conditional test-registration gate |
| `views/load_views.xml` | Add a journey link or smart button only if proven necessary for the operator workflow; standalone J1 form must work without a load. | Conditional |
| `models/load_dashboard.py` | Change only if actual company/identity security tests prove existing dashboard exposure or incorrect population. | Conditional |

### `plasticos_documents`

| Path | Change | Status |
| --- | --- | --- |
| `models/document.py` | Maintain one business evidence verifier, scope statuses and explicit typed associations; no duplicate original. | Required |
| `models/compliance_service.py` | Add a scoped export-operation evidence verdict, preserving invoice/close behavior. | Required |
| `models/__init__.py` | Register the minimum new typed association model. | Required |
| `security/ir.model.access.csv`, `security/security.xml` | ACL and company/role rules for exact evidence association. | Required |
| `views/document_views.xml` | Display exact scoped associations and verified/pending states in existing UI. | Required for manual workflow |
| `__manifest__.py` | Version and model/security/view wiring. | Required |
| `tests/__init__.py`, `tests/test_compliance_service.py` | Register coverage, preserve prior invoice and close contracts. | Required |
| `__init__.py` | Verify root package registers test modules in installed test runner; modify if actual loader requires explicit import. | Conditional test-registration gate |
| `models/document_rule.py` | Change only if an accepted operation-scoped document policy needs a distinct rule field; do not add a blanket export boolean by default. | Conditional |

### `plasticos_documents_native`

| Path | Change | Status |
| --- | --- | --- |
| `models/document_native.py` | Stop independent `action_verify`/override authority and partner-recency accepted linking; delegate to Documents owner or hold for review. | Required |
| `models/document_sync.py` | Stop pushing native `verified/override` as independent business truth; preserve source originals and business-authoritative projections. | Required |
| `views/document_native_views.xml` | Make verification fields read-only projections and direct user actions to authoritative Documents workflow. | Required |
| `__manifest__.py` | Version update; retain real Enterprise dependency. | Required |
| `__init__.py` | Native bridge currently imports only models; add test import only if actual Enterprise runner does not discover newly created test package. | Conditional test-registration gate |

### `plasticos_security_base`

| Path | Change | Status |
| --- | --- | --- |
| `security/record_rules.xml` | Correct globally permissive `company_id=False` Load rule after a source-safe company backfill. Put role-specific J1/J2 rules here when they reference Security Base-defined groups. | Required |
| `__manifest__.py` | Version bump for record rule update. | Required |
| `tests/test_bridge_contracts.py` | Extend cross-company and missing-company negative tests in existing test surface. | Required proof, no new test file needed |
| `__init__.py` | Check test discovery and register tests only if the installed runner otherwise skips them. | Conditional test-registration gate |

### Source-owner rule/architecture adoption files

Update narrowly, only after owner/operator admission:

- `plasticos_logistics/business_rules/SUPERSESSION.md`, `NATIVE_DOCUMENTS_INTEROP.md`, and the effective-rules/decision register as applicable. Preserve original `BRS-01..07.md` unchanged.
- `plasticos_documents/business_rules/SUPERSESSION.md`, `OWNERSHIP_AND_INTEROP.md`, and the effective-rules/decision register as applicable. Preserve original source BRS text unchanged.
- A new `docs/adr/` ADR is **not mandatory by default**; use one only if owner governance explicitly requires a separate architecture decision not expressible in the accepted owner artifacts.

## 2. Proposed new files inside existing addons

### `plasticos_logistics`

| New path | Why irreducible |
| --- | --- |
| `models/iso_journey.py` | Both J1 `plasticos.iso.journey` and J2 `plasticos.iso.journey.source`: physical ISO identity and many-to-many provenance distinct from truckload, stock move and booking slot. Prefer both classes in one file rather than inventing a new addon. |
| `views/iso_journey_views.xml` | Manual FAS/third-party journey registration where no company load exists. |
| `tests/test_iso_journey.py` | Two feeders to one ISO, no-stock source, same ISO number on new cycle, wrong company, duplicate association. |
| `tests/test_linda_booking_source.py` | New Linda source kinds and SQL uniqueness, PO/SO backward compatibility, unknown-send and stale-booking negative cases. |
| `migrations/<next_version>/pre-migrate.py` | Preflight old load/company/link contradictions; preserve IDs and block ambiguous assignments. |
| `migrations/<next_version>/post-migrate.py` | Populate only provably attributable company/source records after registry migration. Never derive J1 from packaging string or booking slot. |

### `plasticos_documents`

| New path | Why irreducible |
| --- | --- |
| `models/document_evidence_link.py` | Explicit typed, revision- and company-scoped many-association evidence record to one original, with one business verifier. Existing single `res_model/res_id` cannot prove this on its own. |
| `tests/test_scoped_evidence.py` | One native original serving two different scoped obligations; stale, unauthorized, revoked, ambiguous and expired negatives. |
| `migrations/<next_version>/pre-migrate.py` | Census legacy records and source ambiguities before changing semantics. |
| `migrations/<next_version>/post-migrate.py` | Bind only unambiguously proven legacy originals and scope to the new representation. |

### `plasticos_documents_native`

| New path | Why irreducible |
| --- | --- |
| `tests/__init__.py` | Register Enterprise bridge tests (currently absent). |
| `tests/test_native_evidence_bridge.py` | Demonstrate native original retention, delegated verification, no partner-only auto-link, and cross-company isolation. |
| `migrations/<next_version>/pre-migrate.py` | Census native/legacy conflicting verified states. |
| `migrations/<next_version>/post-migrate.py` | Reconcile proven statuses without silently treating native flags as verified business evidence. |

**Migration scripts are release-conditional:** create `pre` and `post` only where actual installed Odoo 19 upgrade mechanics require them. Select exact `<next_version>` only after checking current module HEAD/version and accepted migration contract. The new test file names are recommended distinct concerns, not canonical model identifiers.

## 3. Do not modify by default

- `plasticos_transaction/models/transaction.py` or `plasticos_transaction/models/transaction_line.py`: the actual load association problem is injected in Logistics; keep `UNIQUE(load_id)` for valid pairs; old `container_no` is packaging and must not be migrated as ISO identity.
- Native Odoo Sale, Purchase, Stock, Accounting: read their actual quantities and state only, never create a second ledger.
- `plasticos_automation`: its legacy reserved-picking auto-dispatch rule is disabled and a regression test exists. It does not need Export-owned scheduling or another sender.
- `plasticos_facility_profile`: its equipment types describe facilities/machinery, not physical ISO shipping containers.
- Repository `INVARIANTS.md`: constitutional v2.2.0 remains active unless separately admitted successor; no silent v3.3 draft upgrade.
- No new booking template referring to `plasticos.export.booking` in Logistics because Logistics must not depend on Export. Any model-specific booking template and `_inherit` source check belong downstream inside `plasticos_export`; transport remains Linda/native Odoo Mail.

## 4. Proof and acceptance order

1. Pin current Staging and adopt owner BRS/ADR; prove Security Base and addon DAG remains acyclic.
2. Logistics migration/load company, exact association and J1/J2; run buyerless/FAS and no-fake-load negatives with a real Odoo Enterprise registry.
3. Documents scoped evidence and native delegation; run independent-verifier and ambiguous original negatives.
4. Linda source-kind migration and send-time guard; prove old PO/SO semantics, booking amendment, `unknown` protection and carrier redaction without real sending.
5. Only after owner interfaces and installed registries pass, implement E1-E4 in `plasticos_export`; integrated tests for the downstream `_inherit` hook and report ACLs live in Export.

No module edits, PRs, source-owner approvals, runtime PASS results, or migration outcomes are claimed by this map.

## Pinned code evidence

- `plasticos_logistics/models/load.py` L43-46 and L257-298: https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/load.py#L43-L46
- `plasticos_logistics/models/transaction_inherit.py` L18-62: https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/transaction_inherit.py#L18-L62
- `plasticos_logistics/models/linda_request.py` L153-282: https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/linda_request.py#L153-L282
- `plasticos_documents_native/models/document_native.py` L118-178: https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents_native/models/document_native.py#L118-L178
- `plasticos_documents_native/models/document_sync.py` L89-125: https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents_native/models/document_sync.py#L89-L125
- `plasticos_security_base/security/record_rules.xml` L125-151: https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_security_base/security/record_rules.xml#L125-L151

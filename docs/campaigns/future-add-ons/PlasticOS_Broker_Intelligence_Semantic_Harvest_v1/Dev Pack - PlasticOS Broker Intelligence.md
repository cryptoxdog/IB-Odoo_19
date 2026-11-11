```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only: []
  unlisted_repositories: no_access
```

# PlasticOS Broker Intelligence v2
## Complete Architecture and Coding Agent Development Pack

**Target:** Odoo 19 Enterprise / PlasticOS
**Implementation:** Evolve the existing standalone addon, incorporating the semantic harvest
**Delivery:** Installable, tested ZIP plus source and validation receipts
**Publication:** No push, PR, merge, or deployment authorized by this contract
**Execution environment:** Disposable local workspace and Odoo Docker test database
**Status:** Proposed implementation architecture for coding-agent realization

### 0. Objective and binding

Build an evidence-backed Broker Intelligence capability that provides useful recommendations across Mack, web leads, material inspection, offer preparation and commercial rejection recovery.

**Use these exact input artifacts:**

| Artifact | SHA-256 |
|---|---|
| `PlasticOS_Broker_Intelligence_Standalone_Odoo19_v1.zip` | `efddf4dc53aae0e6c2e322e9cfa4cab61ad1db333a15e410138c67f7b105436b` |
| `PlasticOS_Broker_Intelligence_Semantic_Harvest_v1_2026-11-11.zip` | `97fc549a840ac13fcf5e5b4550c77ff69e238412d2f6811e5df3c158ca64e6c2` |

**Repository evidence baseline:**

- `IB-Odoo_19/Staging`: `64896c7fc976daa67d90ca51ff4570900ce7b0c7`
- `IB-Odoo_19/Development` Mack WIP: `d9933baaf517750779e592181d9d5ef4abdc3485`
- These revisions were rechecked. They identify the inspected source, not the mandatory implementation branch.
- The harvest folder and new addons were **not present on the inspected Staging tree**. Use the supplied ZIPs; do not assume they have already been committed.

The coding agent may build against a local checkout or isolated working directory, but must preserve the required Odoo contracts and deliver the final source as a ZIP. Writable repository access allows scoped local implementation; it does not authorize remote publication.

**Acceptance definition:** The result is installable in Odoo 19, provides evidence-cited advisory answers, exposes all approved knowledge through a permission-safe interface, integrates with Mack and web leads when their optional modules are installed, supports rejection recovery without new business authority, and proves its behavior in a disposable Odoo database.

---

## 1. Product architecture

### 1.1 Logical structure

```text
                        ODOO 19
                           |
          +----------------+----------------+
          |                |                |
        MACK           WEB LEADS       OFFERS / MATCH
          |                |                |
          +----------------+----------------+
                           |
                BROKER INTELLIGENCE
                           |
              +------------+------------+
              |            |            |
          KNOWLEDGE      REASONING    REVIEW
           CATALOG       / ADVICE     CONTROL
              |            |            |
              +------------+------------+
                           |
                 SOURCE / EVIDENCE
                           |
          +----------------+----------------+
          |                |                |
      Harvest v1        PP KB v8       Odoo facts
      candidate pack    candidates     and records
```

Broker Intelligence owns **knowledge interpretation, advisory retrieval, and explanation**.

It does not own the operational facts it reads.

### 1.2 Existing authoritative owners

| Concern | Existing owner | New intelligence responsibility |
|---|---|---|
| Polymer, grade, form, material profile | `plasticos_material_profile` | Explain evidence gaps and quality implications |
| Web-lead HOT / REVIEW / COLD | `plasticos_web_leads` | Supply approved advisory context |
| Canonical intake | `plasticos_intake` | Read intake facts and answer broker questions |
| Buyer matching and scoring | `plasticos_matching`, Gate/CEG | Explain results; never select or score independently |
| Buyer/source enrichment | Gate/EIE | Explain available evidence; no local inference replacement |
| Offers and terms | `plasticos_offer` | Quote-readiness and rejection coaching |
| Logistics and freight | `plasticos_logistics` | Exception guidance, not dispatch |
| Documents and verification | Native Odoo Documents / PlasticOS document owners | Evidence checklist, not verification |
| Mack interactions | Native Odoo mail/chatter | Source-bound broker consultations |

Applicable project authority includes [INVARIANTS.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/INVARIANTS.md), [ADR-016](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/docs/adr/ADR-016-web-lead-triage-boundary.md), [ADR-018](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/docs/adr/ADR-018-human-brokerage-checkpoints.md), and [ADR-004](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/docs/adr/ADR-004-intake-vs-material-profile-domain-split.md).

**Mandatory invariants:** POS-INV-01 through 05 for native ownership, stable identity, factual integrity and isolation; POS-INV-06 through 08 for document/evidence separation; POS-INV-17 through 19 for external intelligence and matching boundaries; plus the repository-wide BAN001 restriction.

### 1.3 The four independently installable modules

| Addon | Dependencies | Purpose |
|---|---|---|
| `plasticos_broker_intelligence` | `base` | Knowledge, approval, retrieval, advice |
| `plasticos_broker_intelligence_mack` | Core, `plasticos_intake`, `mail` | Mack consultations and native Odoo interface |
| `plasticos_broker_intelligence_web_leads` | Core, `plasticos_web_leads` | Advisory UI and controlled qualification context |
| `plasticos_broker_intelligence_rejections` | Core, `plasticos_offer`, `plasticos_matching` | Offer/match rejection explanations |

All four must use `auto_install=False`.

None depends on `plasticos_mack_workbench`, `plasticos_semantic_kernel`, direct CEG SDK access, or a separate LLM/vector database.

---

## 2. Complete target file tree

**Legend:** `[E]` retain/extend an existing file from standalone v1, `[N]` justified new file, `[S]` existing harvest source, read-only.

```text
IB-Odoo_19/
│
├── plasticos_broker_intelligence/
│   ├── __init__.py                              [E]
│   ├── __manifest__.py                          [E]
│   ├── README.md                                [N]
│   │
│   ├── models/
│   │   ├── __init__.py                          [E]
│   │   ├── knowledge.py                         [E]
│   │   └── advisor.py                           [E]
│   │
│   ├── services/
│   │   ├── __init__.py                          [E]
│   │   ├── retrieval.py                         [E]
│   │   └── evidence_context.py                  [N]
│   │
│   ├── wizards/
│   │   ├── __init__.py                          [E]
│   │   └── broker_advice_wizard.py              [E]
│   │
│   ├── data/
│   │   ├── candidate_knowledge.xml              [E]
│   │   ├── kb_candidate_knowledge.xml           [E]
│   │   └── harvest_review_candidates.xml        [N]
│   │
│   ├── security/
│   │   ├── security_groups.xml                  [E]
│   │   ├── ir.model.access.csv                  [E]
│   │   └── knowledge_rules.xml                  [E]
│   │
│   ├── views/
│   │   ├── knowledge_views.xml                  [E]
│   │   ├── advice_wizard_views.xml              [E]
│   │   └── menus.xml                            [E]
│   │
│   └── tests/
│       ├── __init__.py                          [E]
│       ├── test_broker_knowledge.py              [E]
│       ├── test_harvest_admission.py             [N]
│       ├── test_advisory_contract.py             [N]
│       └── test_access_isolation.py              [N]
│
├── plasticos_broker_intelligence_mack/
│   ├── __init__.py                              [E]
│   ├── __manifest__.py                          [E]
│   ├── models/
│   │   ├── __init__.py                          [E]
│   │   ├── consultation.py                      [E]
│   │   └── intake_advice.py                     [E]
│   ├── data/
│   │   └── server_actions.xml                   [E]
│   ├── security/
│   │   ├── ir.model.access.csv                  [E]
│   │   └── consultation_rules.xml               [E]
│   ├── views/
│   │   └── consultation_views.xml               [E]
│   └── tests/
│       ├── __init__.py                          [E]
│       └── test_consultation.py                 [E]
│
├── plasticos_broker_intelligence_web_leads/
│   ├── __init__.py                              [E]
│   ├── __manifest__.py                          [E]
│   ├── models/
│   │   ├── __init__.py                          [E]
│   │   ├── web_lead.py                          [E]
│   │   └── web_lead_config.py                   [N]
│   ├── data/
│   │   └── server_actions.xml                   [E]
│   ├── views/
│   │   └── web_lead_config_views.xml            [N]
│   └── tests/
│       ├── __init__.py                          [N]
│       └── test_web_lead_guidance.py            [N]
│
├── plasticos_broker_intelligence_rejections/
│   ├── __init__.py                              [N]
│   ├── __manifest__.py                          [N]
│   ├── models/
│   │   ├── __init__.py                          [N]
│   │   ├── offer_advice.py                      [N]
│   │   └── match_result_advice.py               [N]
│   ├── data/
│   │   └── server_actions.xml                   [N]
│   └── tests/
│       ├── __init__.py                          [N]
│       └── test_rejection_guidance.py           [N]
│
└── docs/
    └── campaigns/
        └── future-add-ons/
            └── PlasticOS_Broker_Intelligence_Semantic_Harvest_v1/
                ├── README.md                    [S]
                ├── SEMANTIC_AUDIT.md            [S]
                ├── REPO_PLACEMENT.md            [S]
                ├── REVIEW_QUEUE.md             [S]
                ├── EVALUATION_AND_VALUE.md      [S]
                ├── HARVEST_COVERAGE.json         [S]
                ├── VALIDATION_RECEIPT.md        [S]
                ├── FILE_MANIFEST.sha256         [S]
                ├── candidates/                  [S]
                ├── comparisons/                 [S]
                ├── evidence/                    [S]
                ├── evaluation/                  [S]
                └── tools/                       [S]
```

The delivery ZIP must additionally retain the standalone package's existing `source_catalog/`, `tools/`, and `tests_offline/` assets, with a source manifest, install instructions and validation report. Those directories are package/engineering resources, **not new Odoo addons**.

Do not create a separate database model for every source category or inspection concern. The existing knowledge model is the appropriate shared catalogue; Odoo's existing business models remain the business facts.

---

## 3. Harvest ingestion and semantic normalization

### 3.1 Required harvest coverage

| Harvest resource | Source count | Target use |
|---|---:|---|
| Broker capabilities | 18 | Taxonomy, task routing and coverage tests |
| Rejection meanings | 12 | Candidate knowledge and explanations |
| Coaching scenarios | 56 | Source/evaluation records |
| Unique coaching patterns | 20 | Candidate coaching knowledge |
| Material inspection concerns | 32 | Candidate clarification/checklist knowledge |
| Proposed decision sequences | 12 | Reviewed advisory playbooks, not executable automations |
| Source text scenarios | 867 | Offline evidence and test-candidate index |
| Media references | 116 | Provenance only, not shipped images |
| Rejection aliases | 28 | Unresolved reconciliation queue |
| PP knowledge sections | 12 | Technical candidate harvest |
| Adversarial acceptance cases | 18 | Required test-design input |

### 3.2 Ingestion pipeline

```text
ORIGINAL SOURCE
    |
    v
SOURCE HASH + MEMBER/ROW VERIFICATION
    |
    v
NORMALIZATION TO STABLE CANDIDATE ID
    |
    v
OWNER AND CONFLICT RECONCILIATION
    |
    v
DRAFT KNOWLEDGE / OFFLINE EVALUATION
    |
    v
EXPLICIT SME ADJUDICATION
    |
    +------ unresolved / rejected --> remain non-operational
    |
    v
APPROVED IMMUTABLE KNOWLEDGE VERSION
    |
    v
PERMISSION-FILTERED ADVISORY RETRIEVAL
```

The original donor data must not be rewritten to appear verified. For every candidate, maintain its original file, SHA-256, row/selector, derived meaning, existing owner, original disposition, and review outcome.

### 3.3 Rejection catalogue

Preserve these exact 12 source codes:

| Code | Candidate interpretation | Mandatory boundary |
|---|---|---|
| `WRONG_FORM` | Form incompatibility | Buyer/line capability evidence required |
| `NO_FILM_PROGRAM` | Film not currently accepted | May be time-limited, not permanent exclusion |
| `MOISTURE_HIGH` | Moisture exceeds applicable tolerance | Measurement and buyer specification required |
| `LABELS_PAPER_HIGH` | Label or paper contamination | Record observation, verify actual tolerance |
| `METAL_PRESENT` | Metal contamination concern | Verify what is present and consequence |
| `SPEC_INCOMPLETE` | Missing required specifications | Ask for clarification, not auto-reject |
| `MFI_OUT_OF_RANGE` | MFI mismatch | Tested result, conditions and applicable spec required |
| `COLOR_WRONG` | Buyer color mismatch | Buyer-specific evidence required |
| `FILLER_HIGH` | Possible excessive filler/ash | Measurement and applicable tolerance required |
| `LOGISTICS_WINDOW` | Pickup/delivery timing conflict | Route logistics discussion to its owner |
| `QUALITY_HISTORY` | Prior attributable quality problem | Not proof of permanent incompatibility |
| `OTHER` | Unclassified refusal | Preserve original statement without forced classification |

**Implement:** A reviewed mapping of meaning → evidence prerequisites → possible next question → conditional recovery advice.

**Do not implement:** Automatic changes to offer state, permanent match exclusions, buyer capability records, or matching scores.

The 28 donor rejection aliases have no general automatic mapping authorization. An alias is usable only after a reviewer explicitly verifies its intended meaning and collision behavior.

### 3.4 Coaching catalogue

Preserve all 56 source records, but expose at most the **20 distinct patterns** as independently reviewable candidate guidance.

| Pattern IDs | Distinct coaching concern |
|---|---|
| 01–04 | MFI evidence, mixed PP/PE, delayed loads, wrong-polymer quotes |
| 05–08 | Buyer nonresponse, expired quotes, missed appointments, insufficient photographs |
| 09–12 | Low process yield, cancelled demand, discoloration, rejection-code coaching |
| 13–16 | Specification drift, freight terms, follow-up expiry, duplicate records |
| 17–20 | Payment terms, missing BOLs, changed buyer schedule, price-basis confusion |

Every pattern must retain links to all contributing scenario IDs and the original claimed SOP identifier.

**No source SOP ID is automatically authoritative.** A reference such as `SP-08`, `QA-03`, or `FIN-02` must resolve to a real, current approved procedure before advice can assert that the company requires it.

If the SOP cannot be verified, the scenario remains an evaluation example or a proposed coaching pattern.

### 3.5 Material-inspection knowledge

Preserve all 32 concerns, grouped for contextual retrieval:

| Group | Source keys |
|---|---|
| Material identity | `POLYMER_ID`, `FORM`, `GRADE`, `COLOR`, `SOURCE` |
| Quantity and recurrence | `MASS`, `CADENCE` |
| Physical properties | `MOISTURE`, `MFI`, `DENSITY`, `ASH`, `FILLER` |
| Contamination | `METAL`, `PVC`, `PE_PP`, `LABELS`, `FOOD_RESIDUE`, `ODOR`, `CONTAMINATION` |
| Inspection and testing | `PHOTOS`, `SAMPLE`, `TRIAL`, `WASHING`, `SORTING` |
| Packaging and freight | `BULK_PACKAGING`, `FREIGHT` |
| Documents and compliance | `HAZMAT`, `COA`, `CUSTODY`, `CERTIFICATION` |
| Commercial capability | `HISTORY`, `CAPACITY` |

These are **context-sensitive questions**, not universal prerequisites for every material.

The runtime must not turn all 32 into a mandatory form or automatically classify leads based on absent fields.

Examples of required discipline:

- A photograph may support an observed color or form; it cannot establish a verified MFI.
- A supplier's volume statement is not a scale ticket.
- A buyer-specific moisture tolerance is not a universal PP threshold.
- Missing a COA is not proof that the material cannot be sold.
- Historical rejection is not necessarily present buyer incapacity.

### 3.6 Decision sequences

Preserve these 12 reconstructed advisory sequences:

`WEB_LEAD_TRIAGE`, `MATERIAL_QUICK_ID`, `QUOTE_READINESS`, `MATCH_REQUEST`, `REJECTION_RECOVERY`, `QUALITY_DRIFT`, `FREIGHT_EXCEPTION`, `SUPPLIER_QUALIFY`, `COMMERCIAL_NEGOTIATION`, `DOCUMENT_READINESS`, `COACH_AND_LEARN`, and `REVERSE_PRODUCT_SOURCING`.

Each sequence may generate a checklist or explanation, but its steps must not be interpreted as permission to execute a workflow.

`MATCH_REQUEST` continues through the existing Gate/CEG authority, and `REVERSE_PRODUCT_SOURCING` remains hypothetical until actual buyer-demand and sourcing evidence exists.

---

## 4. Core knowledge model

### 4.1 Preserve existing model

Extend:

`plasticos.broker.knowledge`

Do not create another `broker.playbook`, `broker.rule`, or `broker.rejection.code` table for the same curated guidance.

Preserve the working fields already defined in v1:

- `name`, `code`, `version`, `topic`, `company_id`
- `trigger_terms`, `material_terms`, `polymer_scope`
- `risk_explanation`, `clarification_questions`, `recommended_next_step`
- `source_ref`, `source_sha256`, `source_kind`
- `state`, `review_rationale`, `approved_by`, `approved_at`

Add the minimum fields needed to preserve the harvest's actual semantics:

| Proposed field | Type | Why required |
|---|---|---|
| `candidate_id` | Char, indexed | Stable `BI-*` source identity |
| `semantic_kind` | Selection | Rejection, coaching, inspection, playbook or general guidance |
| `source_locator` | JSON | Exact member/row/selector and source digest |
| `owner_ref` | Char | Existing business/knowledge owner |
| `applicability` | JSON | Material/process/task-specific conditions |
| `evidence_prerequisites` | JSON | What must be established before a claim is usable |
| `adjudication_status` | Selection | Distinguishes unresolved, accepted, rejected and superseded source meanings |
| `review_evidence_ref` | Char | Provenance of the SME approval |

Do not store live seller/buyer facts inside these records.

Any JSON fields require bounded, validated input schemas at the ORM boundary. They are not free-form escape hatches for instructions or privileged references.

### 4.2 Approval lifecycle

Retain v1's `draft → approved → retired` lifecycle.

An additional adjudication status must describe the *meaning's source review*, not replace that publication lifecycle.

A candidate can become approved only if:

1. Its source locator resolves to the expected source identity.
2. Its meaning is reviewed against the applicable business owner.
3. Required technical or policy evidence is present.
4. Missing evidence and applicability limits are explicit.
5. An authorized reviewer records a rationale and review evidence.
6. No unverified numeric, buyer-demand, pricing or regulatory assertion is silently promoted.

Approval must be server-side, not just a button visibility rule.

Approved records are immutable. Corrections create a successor version. Retirement retains history.

The existing uniqueness rules must continue preventing concurrent approved duplicates. A successor approval must use a controlled transactional transition, including retirement of the predecessor when appropriate, rather than opening an uncontrolled visibility gap.

### 4.3 Initial data

The existing standalone addon ships **30 synthetic candidate records and eight PP KB candidates**, all as drafts.

Retain their identities and provenance. Do not accidentally turn them into operational defaults during upgrade.

Add `harvest_review_candidates.xml` for the nonduplicate review candidates derived from:

- 12 rejection meanings
- 20 distinct coaching patterns
- 32 inspection concerns

Target: **64 candidate knowledge entries**, subject to deterministic deduplication against the existing 38.

Eighteen capability headings are taxonomy, not 18 more playbooks by default. The 12 proposed decision sequences should initially remain non-executable evaluation/design assets; promote a sequence into knowledge only when a reviewed procedure warrants it.

Import must be deterministic and repeatable. Reinstalling or upgrading must not overwrite a previously approved version with unreviewed source text.

---

## 5. Advisory engine and public contract

### 5.1 Preserve the v1 API

Existing abstract model:

`plasticos.broker.advisor`

Existing public method:

`advise(task, description, limit, include_draft)`

Preserve `broker-advice/v1` for existing consumers or provide a tested compatibility projection.

Add a versioned **`broker-advice/v2` proposal** for structured context and source-backed explanation. Do not silently change the meaning of v1's fields.

### 5.2 Proposed v2 request

```json
{
  "schema": "broker-advice-request/v2",
  "task": "material_quality",
  "subject": {
    "model": "plasticos.intake",
    "id": 123
  },
  "question": "What do we need before quoting this material?",
  "limit": 5
}
```

Only a closed allowlist of supported subject models is permitted. The caller's subject locator is **not authorization**. Odoo resolves read access, scope, allowed fields and current revision server-side.

### 5.3 Proposed v2 response

```json
{
  "schema": "broker-advice/v2",
  "status": "guidance",
  "authority": "advisory_only",
  "subject": {
    "model": "plasticos.intake",
    "id": 123,
    "observed_revision": "<server-observed revision>"
  },
  "facts": [
    {
      "key": "polymer",
      "value": "PP",
      "basis": "reported",
      "evidence_ref": "intake:polymer_id"
    }
  ],
  "unknowns": [
    {
      "key": "mfi",
      "reason": "No attributable test result was supplied"
    }
  ],
  "knowledge": [
    {
      "ref": "BI-INSPECT-09@1",
      "source_ref": "<exact reviewed source>",
      "role": "procedural_guidance"
    }
  ],
  "questions": [
    "Do we have a measured MFI and its test conditions?"
  ],
  "recommendations": [
    {
      "action": "request_material_test",
      "description": "Ask the supplier for an attributable MFI test",
      "requires_human": true
    }
  ],
  "warnings": [
    "No current buyer compatibility or quoted price is established"
  ]
}
```

This is a candidate contract for implementation. It is not an existing Odoo RPC schema.

### 5.4 Distinguish evidence types

Every factual statement must preserve its basis:

- `reported`: supplier, buyer or operator statement
- `observed`: attributable visual/physical observation
- `measured`: test or measurement with required conditions
- `derived`: calculation from identified source facts
- `inferred`: unverified inference
- `approved`: authorized business fact or approved procedure, as appropriate

These categories must not be collapsed into one confidence score.

Missing, zero, false and unknown are different values. The service must not turn an unset float field into an asserted zero measurement.

### 5.5 Retrieval and reasoning

Preserve deterministic retrieval as the baseline.

Improve it in this order:

1. Enforce record access, active company and approval state.
2. Restrict by task and applicability.
3. Use server-resolved material/subject facts for technical scope.
4. Rank remaining knowledge by transparent lexical relevance.
5. Check prerequisite evidence before making a conclusion.
6. Generate questions or conditional guidance when prerequisites are missing.
7. Return exact approved knowledge versions and reasons for abstention.

The existing `services/retrieval.py` token matcher may remain for relevance. **It must not be used as evidence that a polymer, buyer requirement or contaminant is factually present.**

Technical claims must be gated by structured source facts. Example: `MFI_OUT_OF_RANGE` cannot conclude incompatibility from the words "high MFI"; it needs an attributable test, conditions and applicable specification.

Do not introduce vector search, embeddings, Neo4j, fine-tuning, or a new provider as mandatory v2 dependencies. Add such complexity only if measured retrieval performance requires it.

### 5.6 Abstention

The service must return a noncommercial abstention when:

- No approved knowledge is relevant.
- The question requires an unavailable current business fact.
- A required source has been retired.
- The evidence contradicts itself.
- A claim would require a price, live buyer demand, legal conclusion or verified quality measurement that the service does not possess.

Access failures must raise an actual access error, not return hidden record metadata.

---

## 6. Mack integration

### 6.1 Preserve current standalone Mack ownership

Continue evolving:

`plasticos_broker_intelligence_mack`

Do not make `plasticos_mack_workbench` a dependency.

The Development WIP is a **design donor**, not a migration target. Its most valuable reusable behavior is already represented in the standalone addon: source-bound intent, immutable receipts, company scope and idempotency.

### 6.2 Required user experience

A broker viewing an intake can select **Mack: Broker Advice**.

Mack receives the currently authorized intake facts and returns:

- Material interpretation with source qualifiers.
- Missing information.
- Quality concerns.
- Relevant reviewed technical knowledge.
- Suggested clarification questions.
- Conditional commercial next steps.
- Source references and an explicit advisory boundary.

The initial answer may be rendered deterministically from approved knowledge. The package must not pretend this is a complete generative Mack chat runtime.

### 6.3 Source-bound consultation

Extend existing `plasticos.broker.consultation`.

Keep the existing public method:

`record_from_source_message(intake_id, message_id)`

Mandatory behavior:

- Internal authenticated user.
- Single-company context until authoritative intake-company scope is established.
- Verify intake read access.
- Verify exact `mail.message` / intake thread relationship.
- Verify the requesting user is the actual native message author.
- Sanitize HTML safely.
- Store source-message hash, source timestamp, intake revision and advice-result digest.
- Preserve the exact approved knowledge references used.
- Idempotent retries return the original immutable receipt.
- Conflicting replay fails.
- No `sudo` access widening.

Optional attachment references may be included only after verifying they are linked to the source message and the user can read them. Keep checksums and locators, not duplicate file bytes.

### 6.4 Explicit nonexecution

Consultations must never:

- Send an offer or email.
- Modify buyer selections.
- Invoke Gate automatically.
- Modify intake or opportunity commercial state.
- Create an order.
- Record an approval.
- Infer human authorization from chat text.
- Post to an externally visible chatter audience.

Default to showing the answer in the wizard or consultation UI. Any later generated chatter reply requires a separate explicit internal-audience and notification-safety contract.

### 6.5 Generative Mack, subsequent phase

A future configured LLM may synthesize prose from the approved `broker-advice/v2` result, provided:

- The structured advice remains authoritative over the generated wording.
- Every factual claim has supporting evidence.
- Unknowns remain unknown.
- External provider configuration and data disclosure are approved.
- Failure falls back to deterministic advice or abstention.
- Generated text cannot call business actions.

This capability is not a prerequisite for completing the bounded v2 addon.

---

## 7. Web-lead qualification integration

### 7.1 Verified existing seam

The current implementation calls:

```text
plasticos.web.lead._qualification_signals(...)
    ↓
evaluate_economic_opportunity(...)
    ↓
derive_final_disposition(...)
```

`_qualification_signals()` is an Odoo model method and can be extended using `_inherit`.

The economic evaluator and deterministic validator remain owned by `plasticos_web_leads`. The bridge must not fork them.

### 7.2 Implement optional feature control

Add a setting on `plasticos.web.lead.config` through the optional addon:

`broker_intelligence_mode`

Initial supported values:

| Mode | Behavior |
|---|---|
| `off` | No knowledge injection; exactly existing qualification behavior |
| `shadow_only` | Supply approved advisory context only while existing `qualification_mode=shadow` |

Default: `off`.

No live-routing activation option in this delivery. Promotion into live qualification requires a later approved, tested change.

### 7.3 Narrow integration method

In `plasticos_broker_intelligence_web_leads/models/web_lead.py`:

- Call `super()._qualification_signals(...)`.
- Preserve all original signal fields and semantics.
- If integration is off, return the original result unchanged.
- If `shadow_only` and the existing qualification mode is `shadow`, read a bounded set of approved broker knowledge relevant to the reconciled lead evidence.
- Attach a separate namespaced advisory structure.

Illustrative additional context:

```json
{
  "broker_intelligence": {
    "schema": "broker-knowledge-context/v1",
    "authority": "knowledge_not_seller_evidence",
    "knowledge_refs": [
      "BI-INSPECT-09@1"
    ],
    "suggested_clarifications": [
      "Request MFI and test conditions if application fit requires it"
    ]
  }
}
```

The existing `evidence_refs` mapping must remain unchanged. Knowledge IDs are **not** seller-evidence IDs and cannot satisfy the validator's evidence gates.

Because the economic evaluator copies the qualification signals into its assessment context, this method offers an additive integration path without monkeypatching the plain Python evaluator. The coding agent must prove the exact current consumer tolerates the additional namespaced key before enabling it.

### 7.4 Strict protections

- No additional LLM call.
- No replacement of `web-lead-economic-assessment/v2`.
- No change to `derive_final_disposition`.
- No independent COLD/HOT override.
- No rewriting `canonical_payload`.
- No new intake or partner from advice.
- No invented mass or grade.
- No negative evidence derived solely from the knowledge catalogue.
- No auto-triggering the bridge on installation.

If any of these boundaries cannot be preserved, keep only the existing read-only web-lead advice action and report the injection seam as blocked.

### 7.5 Evaluation

Compare an unchanged baseline against knowledge-assisted recommendations on a broker-labelled holdout.

Initial priorities:

- False-COLD rate.
- Appropriate REVIEW rate.
- Missing-information recall.
- Unsupported material assertions.
- Explanation citation validity.
- Model-call count and latency.
- Zero unauthorized routing changes.

Do not claim model improvement from a self-generated synthetic fixture.

---

## 8. Rejection Intelligence integration

### 8.1 New optional bridge

Implement:

`plasticos_broker_intelligence_rejections`

Dependencies: core intelligence, `plasticos_offer`, `plasticos_matching`.

This separation is justified because the core advisory service should not pull in matching and offer modules for every installation.

### 8.2 Existing source fields

Use the native model extensions and current rejection narratives:

- `plasticos.offer.rejection_reason`
- `plasticos.match.result.rejection_reason`

Read the specific offer/match record under its existing ACLs. Do not create another authoritative rejection ledger.

### 8.3 Operator experience

Add an optional **Explain Rejection** action.

For a rejected or reviewable record, the wizard should show:

1. Original rejection statement.
2. Suggested code, where evidence supports one.
3. Explanation of what the code means.
4. Known and missing relevant facts.
5. Potential recovery questions.
6. Conditional next steps.
7. Exact knowledge source and approval status.

For ambiguous codes, return multiple possibilities or abstain.

The operator may manually update the existing business record through its native workflow if authorized. The advisory button itself performs no such write.

### 8.4 Non-negotiable behavior

A rejection suggestion must not:

- Automatically create `plasticos.match.exclusion`.
- Permanently blacklist a supplier or buyer.
- Change a match score.
- Change an offer state.
- Reset an expired or rejected offer.
- Send new terms to a buyer.
- Assume the buyer has a processing capability not documented in Odoo.

A one-time buyer rejection and a durable facility capability rule are different meanings. Never infer one from the other.

---

## 9. Security and permission architecture

### 9.1 Roles

Reuse existing core groups:

- **Broker Intelligence Reader:** approved knowledge and authorized advice.
- **Broker Intelligence Reviewer:** candidate inspection, source review, approval and retirement.

The manager/reviewer group may imply Reader, but all applicable record-rule unions must be tested rather than assumed to be restrictive.

### 9.2 Access rules

| Resource | Reader | Reviewer |
|---|---|---|
| Approved shared knowledge | Read | Read |
| Authorized company knowledge | Read approved | Read/review authorized records |
| Draft knowledge | No access | Read/write |
| Retired history | No ordinary advice retrieval | Read |
| Knowledge approval | Denied | Explicit method only |
| Mack consultations | Own/authorized subject scope | Authorized subject scope |
| Other-company consultations | Denied | Denied unless independently authorized |
| Offer/match advice | Subject read access required | Same subject access requirement |

Never use `sudo` as a shortcut for retrieving business facts.

Because the observed `plasticos.intake` does not have a canonical company field, preserve the standalone Mack bridge's single-company restriction until the authoritative company model is established.

### 9.3 Input safety

Validate and bound:

- Question length.
- Source text length.
- Result count.
- Knowledge reference count.
- JSON nesting and field types.
- Source identifiers.
- Attachment identifiers.
- URL and HTML content.
- Referenced model names.

Untrusted user text cannot supply a new policy, select a hidden model, authorize a reviewer, turn off evidence gates, or become a privileged instruction.

No new HTTP endpoint or unauthenticated API is required.

### 9.4 Provenance and confidentiality

Preserve exact source references but avoid returning private donor text or unauthorized contact/customer information.

Do not include the original 116 images in the addon. The harvest's media inventory is provenance only; image rights, labels and metadata require separate review.

---

## 10. PP technical knowledge integration

### 10.1 Source classification

Use the existing repository's `plasticos_kb_PP_v8.0.yaml` as a donor.

Relevant sections:

- Material grades
- Product-to-scrap mapping
- Quality tiers
- Recycling rules
- Contamination profiles
- Buyer profiles
- Quality indicators
- Inference rules
- Standards
- Processing guidance
- Market intelligence
- Metadata

It is a technically rich source, but its assertions must pass the same review process as the original ScrapGPT material.

### 10.2 Allowed initial use

Examples of plausible approved procedural guidance:

- Ask for appropriate MFI test conditions.
- Distinguish homopolymer and copolymer claims.
- Verify contamination composition.
- Request lot-specific evidence.
- Compare measured properties against an actual specification.
- Clarify processing history and application requirements.

### 10.3 Quarantine

Do not operationalize without separate evidence:

- Fixed buyer acceptance thresholds.
- Historical premiums or discounts.
- Live supply or demand.
- Buyer profiles with no actual company/facility evidence.
- Absolute food-contact or regulatory conclusions.
- The source's self-declared verification/confidence label.

The v8 file contains many null technical fields. Unknown values must remain unknown.

The dormant `plasticos_semantic_kernel` is not required for v2. If activated later, it may provide authoritative specification/observation representations only through its separately accepted owner contracts.

---

## 11. Odoo user interface

Preserve the existing Broker Intelligence menu and add no separate dashboard unless runtime testing proves one necessary.

| Surface | Required user action | Result |
|---|---|---|
| Broker Intelligence → Knowledge | Review candidate | Source, conflicts, prerequisites and approval controls |
| Broker Intelligence → Broker Advice | Ask question | Cited advice and uncertainty |
| Canonical Intake | Mack: Broker Advice | Contextual guidance |
| Intake chatter | Record Mack Consultation | Immutable source-bound result |
| Web Lead | Broker Advice | Read-only clarification guidance |
| Web Lead Configuration | Broker Intelligence mode | Off / shadow-only |
| Offer | Explain Rejection | Candidate cause and recovery advice |
| Match Result | Explain Rejection | Candidate cause and missing evidence |

Use native Odoo 19 lists, forms, dialogs and server actions.

No custom Owl application, dashboard framework or frontend build is necessary for this release.

The initial UI must clearly distinguish **Approved Knowledge**, **Unreviewed Candidate**, and **Missing Evidence**. Approved means a procedure is reviewed; it does not mean the current material or buyer satisfies it.

---

## 12. Implementation sequence

### Phase 0: Baseline and artifact integrity

**Before modification:**

- Verify both input ZIPs against the pinned hashes.
- Inspect all 48 original addon files.
- Validate the harvest's 25-file manifest and references.
- Inspect the current checkout's `INVARIANTS.md`, addon ownership, required validators, and module-version rules.
- Confirm no uncommitted user changes will be overwritten.
- Establish the standalone addon's baseline tests.
- Create an explicit current target file inventory and baseline receipt.

**Done when:** The agent can distinguish existing v1 functionality from the intended additions and has not substituted a stale or reconstructed source.

### Phase 1: Curated harvest projection

- Map all 18 capabilities to existing authority.
- Preserve the 12 rejection meanings.
- Preserve 56 coaching source rows linked to 20 distinct patterns.
- Preserve the 32 inspection concerns and 12 non-executable sequences.
- Generate only nonduplicate draft catalogue entries.
- Reconcile the 28 aliases without guessing equivalence.
- Validate all source links and hashes.
- Keep source-derived commercial claims quarantined.

**Done when:** Every candidate has a stable disposition; all expected counts reconcile; no draft has become approved automatically.

### Phase 2: Knowledge and advisory core

- Extend the existing knowledge model and approval rules.
- Implement the structured evidence-context helper.
- Implement the proposed v2 advisory contract while preserving v1 compatibility.
- Improve relevance filtering without creating new scoring authority.
- Return safe abstentions.
- Add source/permission tests.

**Done when:** Knowledge retrieval is deterministic, approval-scoped, source-bound and unable to invent business facts.

### Phase 3: Mack extension

- Preserve existing intake actions and consultation receipts.
- Add structured contextual advice.
- Include approved knowledge references and evidence status in frozen results.
- Harden verified message/attachment identity and idempotency.
- Retain single-company fail-closed behavior.
- No automatic chatter reply or outbound correspondence.

**Done when:** A permitted internal user receives cited advice and an immutable consultation receipt; unauthorized users and replays fail correctly.

### Phase 4: Web-lead bridge

- Add `broker_intelligence_mode` to the existing web-lead config through `_inherit`.
- Extend `_qualification_signals()` narrowly.
- Leave original qualification contract and deterministic validator unchanged.
- Keep default off.
- Add the approved knowledge context in shadow-only mode.
- Prove one provider call and unchanged routing.
- Run the 18 adversarial harvest cases, extended with real broker-labelled comparisons.

**Done when:** Knowledge can inform the existing recommender without independently changing lead classification.

### Phase 5: Rejection advisory bridge

- Create the optional fourth addon.
- Expose a read-only action on offers and match results.
- Map the 12 codes only to approved knowledge versions.
- Show contextual recovery questions.
- Preserve original rejection narratives.
- Prove no exclusion or commercial side effects.

**Done when:** A broker can inspect a rejection and obtain grounded advice while the native owner remains unchanged.

### Phase 6: Runtime validation and release

- Test clean installs in a disposable Odoo 19 database.
- Test updates from the original standalone v1 installation where applicable.
- Validate module manifests, XML, ACLs, record rules, data and dependencies.
- Run Odoo model tests and the offline corpus tests.
- Run cross-company and external-user negative tests.
- Confirm no unwanted mail, Gate, offer or document side effects.
- Run repository-required static/security checks against the exact final source.
- Build the ZIP from the exact validated tree.
- Reopen the ZIP and verify all declared files, paths, sizes, hashes and test receipts.

**Done when:** The installable archive and validation evidence refer to the same exact source state.

---

## 13. Mandatory acceptance matrix

| ID | Acceptance requirement | Evidence |
|---|---|---|
| BI-01 | All 18 broker capabilities have dispositions | Harvest coverage validation |
| BI-02 | All 12 rejection meanings preserved exactly | Catalogue test |
| BI-03 | 56 coaching rows resolve to 20 distinct patterns | Deduplication test |
| BI-04 | All 32 inspection concerns retained | Coverage test |
| BI-05 | Twelve decision sequences remain non-executable | Structural negative test |
| BI-06 | Original 38 draft cards remain non-operational | Upgrade/ACL test |
| BI-07 | Synthetic SOP cannot be approved without authoritative review evidence | Approval negative test |
| BI-08 | Missing technical measurement yields clarification, not a fabricated fact | Advice test |
| BI-09 | Tested MFI without conditions cannot prove compatibility | Technical negative test |
| BI-10 | Missing buyer-specific specification cannot produce a definite mismatch | Rejection negative test |
| BI-11 | Historical price examples cannot generate a live quote | Commercial negative test |
| BI-12 | One refusal cannot create a match exclusion | ORM side-effect test |
| BI-13 | Mack source-message replay is idempotent | Concurrent and sequential test |
| BI-14 | Unauthorized message/thread access is denied | Security test |
| BI-15 | Cross-company knowledge and consultation leakage is denied | Multi-company test |
| BI-16 | Web-lead bridge disabled means identical baseline behavior | Regression test |
| BI-17 | Shadow advice does not alter HOT/REVIEW/COLD routing | Integration test |
| BI-18 | Knowledge refs cannot masquerade as seller-evidence refs | Validation negative test |
| BI-19 | Provider failure preserves existing safe qualification behavior | Failure-injection test |
| BI-20 | Existing matching, offers and logistics remain owned by their native modules | Side-effect and contract tests |
| BI-21 | Core installs without Mack or web leads | Odoo module install test |
| BI-22 | Each bridge installs only with its declared dependencies | Dependency/install test |
| BI-23 | Repeated installs/upgrades preserve approved knowledge and receipts | Upgrade/replay test |
| BI-24 | All package files and source manifests reconcile | ZIP integrity check |
| BI-25 | No banned identifier, secrets, unwanted media or unexpected executable source is shipped | Security scan |

**Additional adversarial cases:** The harvest's `evaluation/adversarial_acceptance_cases.jsonl` defines 18 proposed scenarios. Convert applicable cases into executable tests; their existing `PROPOSED_NOT_RUN` status is not validation evidence.

### Required human-labelled evaluation

A separate broker-labelled holdout must test:

- False-COLD risk.
- Correct uncertainty handling.
- Material/contamination question usefulness.
- Technical factual correctness.
- Source-citation accuracy.
- Rejection-code agreement between reviewers.
- Time to an evidence-complete broker decision.
- Whether the proposed next step is accepted by a broker.

Split real examples by supplier, lot or time as appropriate to avoid evaluating near-duplicate cases seen during development.

A model improvement claim requires measured comparative evidence. Synthetic source coverage alone does not qualify.

---

## 14. Explicit exclusions

The coding agent must **not** implement these as part of v2:

- Another buyer matcher or local CEG scorer.
- Direct Gate/CEG/EIE clients inside the knowledge addon.
- A new CRM, intake or opportunity lifecycle.
- A new pricing/valuation engine.
- Autonomous commercial negotiation.
- Automatic email, offers, orders or purchase commitments.
- Automatic partner/buyer exclusion from a rejection suggestion.
- Activation of `plasticos_semantic_kernel`.
- Installation of the old `plasticos_mack_workbench`.
- A general-purpose agent orchestration framework.
- Vector database or LLM fine-tuning as a prerequisite.
- New document verification ownership.
- Web-lead live-routing activation.
- Production database operations or publication.

If an approved requirement genuinely requires one of these boundaries to change, report the evidence and stop the affected feature. Do not silently expand scope.

---

## 15. Required final deliverables

The coding agent must deliver:

**A. Installable source ZIP**

Suggested filename:

`PlasticOS_Broker_Intelligence_Harvest_Integrated_v2.zip`

Include the four addon directories, offline source/evaluation tools, and installation instructions. Do not include raw donor media or unrelated repository content.

**B. Build and source manifest**

Include:

- Input archive SHA-256 values.
- Source repository revisions.
- Exact final addon file inventory.
- SHA-256 of every shipped file.
- Declared module dependencies and versions.
- Harvest coverage counts.
- Any rejected/quarantined source entries.

**C. Validation report**

For every test, include execution environment, exact command or invocation, test count, result, relevant log and limitations.

Separate:

- Static validation
- Offline behavior tests
- Real Odoo module installation
- Odoo ORM/security tests
- Cross-addon integration
- Negative/adversarial tests

Do not mark unavailable runtime validation as passed.

**D. Implementation decision report**

Identify every meaningful change from standalone v1, the reason, owner, and proof. Explicitly dispose of all discovered in-scope defects.

**E. Installation runbook**

Cover clean install, existing-v1 upgrade, group assignment, candidate review, setting the web-lead bridge to shadow-only, disabling the integration, and rollback/recovery in a disposable test environment.

The runbook must state that module installation does not authorize changing production lead-routing configuration or sending commercial correspondence.

---

## 16. Completion contract for the coding agent

**The project is complete only when:**

1. The original standalone addon has been upgraded rather than duplicated.
2. All harvested meanings have an explicit, source-linked disposition.
3. Approved knowledge is separated from draft and unverified content.
4. Mack can obtain contextual, cited broker advice.
5. Web leads can consume approved context in shadow without changing routing.
6. Rejected offers and match results can receive source-backed recovery explanations.
7. Source authorization, company isolation, immutability and replay are proven.
8. No commercial owner or matching authority has been replaced.
9. Every in-scope test obligation passes or is explicitly blocked with evidence.
10. The delivered ZIP has been reconstructed and checked against the exact validated source.

**A green offline test suite alone does not satisfy completion.** Real Odoo 19 installation and ORM tests are mandatory for an installation-readiness claim.

**No PR or deployment is part of completion.**

---

## 17. Next Highest Leverage Move

Begin with a **source-bound reconciliation of the original standalone addon and the harvest**, followed by one coherent implementation of core catalogue/approval and advisory contracts. Then implement the independent Mack, web-lead and rejection bridges against that stable core.

Do not start with an LLM integration, new UI framework or fine-tuning. The highest-value result is a trustworthy brokerage reasoning foundation that can answer questions, explain uncertainty and propose meaningful human actions without inventing business reality.

**Devil's Advocate:** The greatest commercial risk is not a model producing a weak answer. It is treating plausible broker advice as verified buyer specifications, prices, compliance, or permission to act. The v2 product must remain useful precisely when it cannot reach a definite conclusion: identify what's missing, explain why it matters, and route the next decision to the actual owner.

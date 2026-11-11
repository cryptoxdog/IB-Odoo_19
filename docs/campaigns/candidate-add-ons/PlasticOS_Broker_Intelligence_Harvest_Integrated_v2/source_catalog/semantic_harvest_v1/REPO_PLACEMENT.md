# Proposed repo placement and migration ownership

**Target:** `https://github.com/cryptoxdog/IB-Odoo_19` Staging `64896c7fc976daa67d90ca51ff4570900ce7b0c7`. This is a **copy destination recommendation**, not an executed repository mutation or branch selection for development.

## A. Place the harvest pack as evidence, not as an installable addon

```text
IB-Odoo_19/
└── docs/
    └── campaigns/
        └── future-add-ons/
            └── PlasticOS_Broker_Intelligence_Semantic_Harvest_v1/
                ├── README.md
                ├── SEMANTIC_AUDIT.md
                ├── REPO_PLACEMENT.md
                ├── REVIEW_QUEUE.md
                ├── EVALUATION_AND_VALUE.md
                ├── HARVEST_COVERAGE.json
                ├── candidates/
                ├── comparisons/
                ├── evidence/
                ├── evaluation/
                └── tools/
```

The archive contains these files at its root; the operator can copy them into this path. **Do not** place raw images, malformed YAMLs or six historical generators under any Odoo addon installation path. This package contains JSONL and a read-only validator, with no business automation or module manifest.

## B. Exact semantic owners when examples are later approved

| Concern | Current authoritative owner | Where a *consumer* could use approved knowledge | Forbidden placement |
| --- | --- | --- | --- |
| Material identification, grade, form, filler and observed quality | `plasticos_material_profile`; optional passive `plasticos_semantic_kernel` under separate activation | `plasticos_broker_intelligence` approved guidance, read-only | New `res.partner`/material master tables or forced semantic-kernel install |
| Web lead material explanation and missing questions | `plasticos_web_leads/models/economic_evaluator.py` and `classification_engine.py`; ADR-016 | Optional `plasticos_broker_intelligence_web_leads` adapter, shadow first | Another HOT/COLD classifier, new provider call or a Gate triage path |
| Mack human consultation and explanations | Native Odoo chatter/intake; Development Mack WIP only has receipts and internal-review routes | Existing previously delivered `plasticos_broker_intelligence_mack` candidate, after Odoo DB test | Make legacy `plasticos_mack_workbench` a required dependency |
| Reject cause meaning and recovery suggestions | `plasticos_offer/models/offer.py`; `plasticos_matching/models/match_result.py` | Approved broker knowledge and operator UI suggestions | New offer state lifecycle; automatic match exclusion |
| Capability/gating, buyer scoring and matching | CEG DomainSpec behind `plasticos_gate` | Knowledge explains reviewed match results only | Local `buyer.matcher`, new scoring weights, direct CEG call |
| Enrichment and inferred buyer/source facts | EIE via Gate | Provenance-aware, read-only hypothesis explanation | In-Odoo enrichment inference fallback |
| Freight/time slot problems | `plasticos_logistics` | Guidance/warnings referenced by owner | New scheduler, dispatch writer or invented freight rates |
| Compliance documents | Native Documents and `plasticos_documents_native` | Checklist to ask reviewer for existing originals | New verification state or silent regulatory approval |
| Real prices, buyer commitments, offer terms | Native Odoo offer, CRM and current evidence | Explanation only after verified source is present | Model prices/canned premium as live defaults |
| Training/evaluation cases | This *docs*-scoped candidate pack until reviewed | Frozen evaluation fixture at approved consumer test owner later | Copy raw synthetic responses into live inference prompt as truth |

## C. Legacy/previous-addon comparison

The previously generated addon ZIP SHA-256 `efddf4dc53aae0e6c2e322e9cfa4cab61ad1db333a15e410138c67f7b105436b` has three **optional** modules:

- `plasticos_broker_intelligence`: draft/approved knowledge, a read-only `broker-advice/v1` advisor, and manual review. It already provides much of the storage and retrieval seam. **Do not build a competing knowledge table.**
- `plasticos_broker_intelligence_mack`: independent native-chatter consultation receipts, not full generative Mack. It intentionally does **not** depend on `plasticos_mack_workbench`.
- `plasticos_broker_intelligence_web_leads`: read-only advisory action, not a replacement for `web-lead-economic-assessment/v2`.

**None of those three names exists on the observed Staging source tree**, and the old `plasticos_mack_workbench` appears only on Development `d9933baaf517750779e592181d9d5ef4abdc3485`. Their presence in a standalone artifact is **not** evidence of installation in any Odoo database.

## D. Minimum viable admission path

1. Preserve this entire candidate pack in repo docs with source hashes and status `CANDIDATE_ONLY`.
2. Appoint a broker SME to adjudicate the 20 distinct coaching patterns and 12 rejection codes, including verified policy/SOP references.
3. Convert only approved, reviewed **nonprice** procedural meanings into successor `plasticos_broker_intelligence` knowledge versions. Avoid regenerating unreviewed cards as approved data.
4. First consumer: test evidence-aware clarifications against the existing `plasticos_web_leads` economic recommender in **shadow**, retaining its deterministic final disposition. Second consumer: Mack's **read-only** native Odoo consultation workflow after database installation proof.
5. Only after a real downstream outcome proves benefit, consider a named reason-code selection field at the **existing rejection owner**. The code taxonomy is not a mandate to alter Odoo schema now.

## E. Base and integration rules

- The repository's default branch is `Staging`, but **this harvest is not an instruction to build from Staging**. The user explicitly requested local artifact delivery; no PR, merge, branch mutation or installation is performed.
- Use exact current source owners when integrating later. Future branch revisions invalidate this revision-bound owner matrix.
- Do not clone a passive semantic kernel or create a domain-specific matcher inside Odoo. Gate/CEG remains the match/scoring authority; EIE remains enrichment owner.
- No commission, margin, offer, physical dispatch, financial document, or customer communication can arise from harvested text alone.

## F. Source evidence

- [Odoo invariants](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/INVARIANTS.md)
- [Web lead ADR-016](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/docs/adr/ADR-016-web-lead-triage-boundary.md)
- [Human review ADR-018](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/docs/adr/ADR-018-human-brokerage-checkpoints.md)
- [Matching README](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/plasticos_matching/README.md)
- [Semantic kernel README](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/plasticos_semantic_kernel/README.md)
- [Mack WIP on Development](https://github.com/cryptoxdog/IB-Odoo_19/blob/d9933baaf517750779e592181d9d5ef4abdc3485/plasticos_mack_workbench/README.md)
- [PP v8 knowledge donor](https://github.com/cryptoxdog/IB-Odoo_19/blob/64896c7fc976daa67d90ca51ff4570900ce7b0c7/plasticos_enrichment/knowledge_base/plasticos_kb_PP_v8.0.yaml)

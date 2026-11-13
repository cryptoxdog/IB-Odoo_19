# Deep semantic audit and meaning-to-owner reconciliation

## Method and statuses

Source-derived category and text examples are preserved exactly in JSONL. Titles, semantic contracts, owner comparisons, risks, and dispositions below are **reviewer inferences/recommendations**. The beneficiary was read at commit `64896c7fc976daa67d90ca51ff4570900ce7b0c7` and Mack's separate Development donor at `d9933baaf517750779e592181d9d5ef4abdc3485`. No claim about live Odoo databases, customer entitlements or deployed model behavior is made.

- **EXISTING:** corresponding business function and owner were found in repository source, not necessarily deployed.
- **PARTIAL:** authoritative lifecycle exists but reusable advisory expression/evaluation is not demonstrated.
- **DUPLICATE_CONCERN:** separate donor heading but same authoritative business concern as another heading.
- **UNPROVEN:** insufficient authoritative proof for the donor's specific algorithm or market claim.
- **REUSE / MERGE:** use current owner, not another engine. **REVISE / PROPOSE:** candidate advisory semantics only. **QUARANTINE:** not suitable as operational truth.

## 18 original broker capability categories

| ID | Original category (rows in corrected CSV) | Repo coverage / decision | Earliest evidenced owner | Extracted value and boundary |
| --- | --- | --- | --- | --- |
| BI-CAP-01 | **QUOTE** (25) | PARTIAL / **REVISE** | `plasticos_offer` | Draft readiness checklist and a no-invented-price benchmark. Source row 1. |
| BI-CAP-02 | **REJECT** (12) | PARTIAL / **PROPOSE** | `plasticos_offer, plasticos_matching` | A controlled, cross-owner rejection-code mapping without new rejection authority. Source row 3. |
| BI-CAP-03 | **MATERIAL_ID** (12) | PARTIAL / **REVISE** | `plasticos_material_profile, plasticos_web_leads` | Evidence-linked clarifier and labeled material identification evaluation cases. Source row 4. |
| BI-CAP-04 | **MATCHING** (12) | EXISTING / **REUSE** | `plasticos_matching (Gate/CEG)` | Adversarial matching acceptance cases only. Source row 5. |
| BI-CAP-05 | **DEAL** (12) | PARTIAL / **REVISE** | `plasticos_offer, plasticos_crm_bridge` | Broker-facing terms review, not auto-priced deal execution. Source row 6. |
| BI-CAP-06 | **RISK** (12) | PARTIAL / **PROPOSE** | `plasticos_web_leads, plasticos_matching, plasticos_logistics` | Multi-source advisory risk explanation with provenance. Source row 7. |
| BI-CAP-07 | **COMPLIANCE** (12) | PARTIAL / **REVISE** | `plasticos_documents, plasticos_documents_native` | Evidence-request scenarios, with legal claims quarantined for review. Source row 8. |
| BI-CAP-08 | **LOGISTICS** (12) | EXISTING / **REUSE** | `plasticos_logistics` | Logistics exception guidance and evaluation cases. Source row 9. |
| BI-CAP-09 | **MARKET** (12) | UNPROVEN / **QUARANTINE** | `plasticos_offer, plasticos_enrichment` | Evaluate provenance/currency, not a market-price engine. Source row 10. |
| BI-CAP-10 | **SOURCING** (12) | PARTIAL / **REVISE** | `plasticos_intake, plasticos_material_profile, plasticos_crm_bridge` | Structured missing-information prompts for Mack/web leads. Source row 12. |
| BI-CAP-11 | **TESTING** (12) | PARTIAL / **PROPOSE** | `plasticos_material_profile, plasticos_semantic_kernel (dormant)` | Material-inspection checklist and held-out quality cases. Source row 13. |
| BI-CAP-12 | **BUYER_MATCH** (12) | DUPLICATE_CONCERN / **MERGE** | `plasticos_matching (Gate/CEG)` | Merge candidate cases into MATCHING evaluation category. Source row 14. |
| BI-CAP-13 | **NEGOTIATION** (12) | PARTIAL / **REVISE** | `plasticos_offer, native CRM` | Coaching cases for live term negotiation review. Source row 15. |
| BI-CAP-14 | **QUALITY** (12) | PARTIAL / **REVISE** | `plasticos_material_profile, plasticos_documents, plasticos_offer` | Quality exception advisory and evidence checklist. Source row 16. |
| BI-CAP-15 | **CONTAMINATION** (12) | PARTIAL / **REVISE** | `plasticos_material_profile, plasticos_web_leads` | Evidence-aware material risk clarifiers and examples. Source row 17. |
| BI-CAP-16 | **PRICING** (12) | PARTIAL / **QUARANTINE** | `plasticos_offer, plasticos_logistics` | Test no-invented-price behavior, defer new valuation engine. Source row 18. |
| BI-CAP-17 | **FREIGHT** (12) | DUPLICATE_CONCERN / **MERGE** | `plasticos_logistics` | Merge freight inspection cases into logistics evaluation. Source row 19. |
| BI-CAP-18 | **SPECIFICATION** (12) | PARTIAL / **REVISE** | `plasticos_material_profile, CEG DomainSpec` | Comparison explanation and missing-spec questions only. Source row 20. |

### Broker capability dispositions with rationale

**BI-CAP-01 QUOTE** (REVISE). Keep pricing and terms as current source facts; qualify specifications and obtain broker approval. Risk: Price ranges are unsupported; quoting is not delegated to AI. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #1`.

**BI-CAP-02 REJECT** (PROPOSE). Classify operator-confirmed refusal cause and suggest a recovery, preserving raw buyer statement. Risk: Source code namespaces conflict; reject is not a permanent facility exclusion. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #3`.

**BI-CAP-03 MATERIAL_ID** (REVISE). Distinguish visual hint, supplier claim, and lab-confirmed polymer identity. Risk: Synthetic identification overstates visual certainty; hazardous burn tests not approved. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #4`.

**BI-CAP-04 MATCHING** (REUSE). Use reviewed, current source facts to request canonical Gate matching. Risk: Raw data invents processors/distances; no local ranking allowed. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #5`.

**BI-CAP-05 DEAL** (REVISE). Suggest negotiation options with actual terms and explicit broker consent. Risk: Fabricated numbers and unilateral commitments are not permissible. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #6`.

**BI-CAP-06 RISK** (PROPOSE). Identify evidence-backed risks, unknowns, and targeted verification actions. Risk: Do not hard-code subjective risk or create binding financial restrictions. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #7`.

**BI-CAP-07 COMPLIANCE** (REVISE). Request appropriate original documents; verification remains with designated owner. Risk: Source contains unsupported/outdated legal and export assertions. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #8`.

**BI-CAP-08 LOGISTICS** (REUSE). Use verified weights, routing and carrier constraints at the native logistics owner. Risk: Old trailer capacities, miles, rates are not live evidence. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #9`.

**BI-CAP-09 MARKET** (QUARANTINE). Research current source-backed indicators only as nonbinding context. Risk: Static synthetic prices, trends and regulatory demand claims are stale. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #10`.

**BI-CAP-10 SOURCING** (REVISE). Capture material, facility, cadence and evidence before asserting tradable inventory. Risk: Repeated source claim does not establish stock or verified supply. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #12`.

**BI-CAP-11 TESTING** (PROPOSE). Request the context-appropriate test with method, units and provenance. Risk: Do not treat synthetic test numbers or uninstalled semantic models as authority. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #13`.

**BI-CAP-12 BUYER_MATCH** (MERGE). Treat as MATCHING evidence collection, not a second matching concern. Risk: Synthetic buyer suggestions and distance claims conflict with Gate authority. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #14`.

**BI-CAP-13 NEGOTIATION** (REVISE). Expose alternatives for human choice using real accepted deal terms. Risk: No autonomous binding offers, discount authorization or auto-emails. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #15`.

**BI-CAP-14 QUALITY** (REVISE). Distinguish observed quality, test evidence, acceptance and claim disposition. Risk: Photos or inferred QC cannot authorize claim settlement. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #16`.

**BI-CAP-15 CONTAMINATION** (REVISE). Record observed contaminants and verification needs, not auto-processor suitability. Risk: Buyer tolerances and wash costs are not universal. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #17`.

**BI-CAP-16 PRICING** (QUARANTINE). Price advice requires verified bid/basis/currency/unit/time and cost evidence. Risk: Unverified spot values cannot become quote prices or market facts. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #18`.

**BI-CAP-17 FREIGHT** (MERGE). Reuse LOGISTICS/freight owners for rate/terms calculation. Risk: Never assume carrier rates, legality, or route distance. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #19`.

**BI-CAP-18 SPECIFICATION** (REVISE). Preserve polymer/form/grade/test facts; Gate/CEG alone owns match hard gates. Risk: Generic tolerances cannot become global hard filters. Exact donor locator: `scrap_plastic_broker_training_dataset_corrected.csv #20`.

### Irreducibility audit

- `MATCHING` and `BUYER_MATCH` remain **two donor taxonomic labels** but one Gate/CEG-owned match contract. A second Odoo matching owner fails the nonduplication test.
- `LOGISTICS` and `FREIGHT` remain **two donor taxonomic labels** but one logistics/freight authority. Split advisory prompts if useful; do not create another freight engine.
- `REJECT` and `RISK` are distinct: a **recorded refusal** is a business outcome, while a **risk hypothesis** is a suggestion; merging them would authorize unsupported refusal or exclusion.
- `MATERIAL_ID` and `SPECIFICATION` are distinct: an observation/identity assertion is not a buyer-specific normative requirement.
- `MARKET` and `PRICING` are distinct: describing a market trend does not set an offer's actual negotiated price. Neither has a supported live quote feed in this donor; both are quarantined as prices.
- `TESTING` and `QUALITY` are distinct: a laboratory/test method produces evidence, but quality acceptance or claim disposition belongs to the appropriate business owner.
- `COACH` is distinct from any execution task. A training scenario may suggest a behavior but does not authorize a commercial or operational effect.

## 12 source-defined rejection-code meanings

The donor's `rejection-code-library-v0_1.jsonl` defines 12 bare codes. These are **candidate explanations**. They do **not** replace `plasticos.offer.rejection_reason`, `plasticos.match.result.rejection_reason`, or the existing `plasticos.match.exclusion.reason` contract.

| Code | Severity (donor) | Proposed owner | Disposition | Non-authority guard |
| --- | --- | --- | --- | --- |
| `WRONG_FORM` | block | plasticos_material_profile + CEG DomainSpec | REVISE | Never create exclusion from suggested code |
| `NO_FILM_PROGRAM` | block | plasticos_facility_profile + CEG DomainSpec | PROPOSE | An old program refusal is not a permanent capability fact |
| `MOISTURE_HIGH` | block | plasticos_material_profile + buyer specification | REVISE | 2% in sample objection is not a universal tolerance |
| `LABELS_PAPER_HIGH` | block | plasticos_material_profile + buyer specification | REVISE | Require buyer-specific spec and observed evidence |
| `METAL_PRESENT` | block | plasticos_material_profile + quality owner | REVISE | A code suggestion is not permission to reject a lot |
| `SPEC_INCOMPLETE` | hold | plasticos_web_leads (REVIEW) + material profile | MERGE | In web leads missing facts are not a COLD verdict |
| `MFI_OUT_OF_RANGE` | block | plasticos_material_profile + CEG DomainSpec | REVISE | Do not enforce numeric gate locally |
| `COLOR_WRONG` | block | plasticos_material_profile + buyer specification | REVISE | No blanket rule across buyers |
| `FILLER_HIGH` | block | plasticos_material_profile + buyer specification | REVISE | No universal filler threshold |
| `LOGISTICS_WINDOW` | hold | plasticos_logistics | MERGE | Do not auto-dispatch |
| `QUALITY_HISTORY` | hold | plasticos_matching + historical quality claims | PROPOSE | Do not automatically create permanent exclusion |
| `OTHER` | hold | plasticos_offer + plasticos_matching | REUSE | Do not use as unreviewed catch-all for critical risks |

**Crucial namespace conflict:** the 867 donor prompt examples contain multiple `R-*` textual labels, while the core registry uses bare names. The alias ledger identifies all observed labels; only two even have an exact suffix match. **No numeric `R-01...R-09` meaning can be assigned by inference.** Two trailing extension JSONL lines are malformed. Even an exact textual suffix match is merely a reconciliation candidate, not an approved business alias.

## 56 coaching entries: 20 semantically distinct patterns

The original 56 entries are all retained with original prompts, outputs, locations and unsupported SOP identifiers. Only 20 distinct scenario/answer patterns exist, repeated across three blocks. `SP-08`, `QA-03`, `SAL-06` and representative other SOP identifiers had no indexed GitHub code-search hits. Absence of a hit is **not proof no policy exists**; every SOP remains `UNVERIFIED` until an explicit approved-source lookup.

| Pattern | Underlying coaching concern | Claimed SOP | Source repetitions | Owner to reconcile |
| --- | --- | --- | ---: | --- |
| BI-COACH-PATTERN-01 | Quote after context-appropriate MFI evidence | `SP-08` | 3 | plasticos_material_profile + plasticos_offer |
| BI-COACH-PATTERN-02 | Mixed PP/PE separation information | `SP-11` | 3 | plasticos_material_profile |
| BI-COACH-PATTERN-03 | Delayed inbound load recovery | `LOG-02` | 3 | plasticos_logistics |
| BI-COACH-PATTERN-04 | Wrong polymer quote correction; no invented price locks | `QA-03` | 3 | plasticos_offer + quality owner |
| BI-COACH-PATTERN-05 | Buyer nonresponse follow-up | `SAL-06` | 3 | native CRM / Mack coaching |
| BI-COACH-PATTERN-06 | Expired quote revision | `SAL-01` | 3 | plasticos_offer |
| BI-COACH-PATTERN-07 | Missed delivery appointment | `LOG-05` | 3 | plasticos_logistics |
| BI-COACH-PATTERN-08 | Insufficient photo evidence -> clarification; not automatic rejection | `QA-08` | 3 | plasticos_web_leads + material profile |
| BI-COACH-PATTERN-09 | Low process yield feedback | `QA-10` | 3 | quality owner + offer owner |
| BI-COACH-PATTERN-10 | Canceled buyer demand; possible new match requires Gate | `SAL-03` | 3 | plasticos_offer + Gate/CEG |
| BI-COACH-PATTERN-11 | Discoloration verification | `QA-05` | 3 | plasticos_material_profile + visual evidence |
| BI-COACH-PATTERN-12 | Rejection vocabulary training | `OPS-01` | 3 | plasticos_broker_intelligence |
| BI-COACH-PATTERN-13 | In-process specification drift needs operator review | `QA-07` | 3 | quality/document owner |
| BI-COACH-PATTERN-14 | Freight term discussion, not auto-pricing | `SAL-04` | 3 | plasticos_logistics + plasticos_offer |
| BI-COACH-PATTERN-15 | Expired follow-up window and reminder | `SAL-09` | 3 | native Odoo activities |
| BI-COACH-PATTERN-16 | Duplicate buyer/deal sheet issue; do not blindly merge | `OPS-03` | 3 | native CRM / offer owner |
| BI-COACH-PATTERN-17 | Payment term negotiation, not global net-30 rule | `FIN-02` | 2 | plasticos_offer + accounting |
| BI-COACH-PATTERN-18 | Missing BOL follow-up; no new Slack automation | `OPS-05` | 2 | plasticos_documents_native + logistics |
| BI-COACH-PATTERN-19 | Changed buyer fulfillment schedule | `SAL-08` | 2 | plasticos_logistics + offer owner |
| BI-COACH-PATTERN-20 | Virgin/recycled price basis confusion | `SAL-10` | 2 | plasticos_offer + live pricing evidence |

All coaching advice is **review-only**. In particular, the donor's suggestions for automatic Slack triggers, price locks, deal-sheet merges, buyer rerouting, discount terms or shipment holds must never be converted into Odoo actions without separate source-owner authority.

## 32 proposed material-inspection concerns

The source supports these as **questions to ask when relevant**, not a mandatory test checklist for every polymer or a source of global thresholds. The actual evidence authority remains with the existing material, documents, intake or facility owner. The 116 media assets lack verified labels, rights, subject consent where necessary and dataset join records; this ZIP contains a hash/reference inventory, **not the media bytes**.

| ID | Inspection meaning | Present source | Comparison / required boundary |
| --- | --- | --- | --- |
| BI-INSPECT-01 | Polymer identity | `scrap_plastic_broker_training_dataset_corrected.csv #4` | plasticos_material_profile + web-lead evidence |
| BI-INSPECT-02 | Physical material form | `scrap_plastic_broker_training_dataset_corrected.csv #1` | plasticos_material_profile |
| BI-INSPECT-03 | Material grade | `scrap_plastic_broker_training_dataset_corrected.csv #2` | plasticos_material_profile |
| BI-INSPECT-04 | Color and color consistency | `scrap_plastic_broker_training_dataset_corrected.csv #2` | plasticos_material_profile + web-lead vision |
| BI-INSPECT-05 | Material origin and production process | `scrap_plastic_broker_training_dataset_corrected.csv #8` | plasticos_material_profile + intake |
| BI-INSPECT-06 | Verified per-load weight | `scrap_plastic_broker_training_dataset_corrected.csv #9` | plasticos_web_leads + plasticos_intake |
| BI-INSPECT-07 | Supply rate and recurrence | `scrap_plastic_broker_training_dataset_corrected.csv #12` | plasticos_material_profile + CRM |
| BI-INSPECT-08 | Moisture and test method | `scrap_plastic_broker_training_dataset_corrected.csv #8` | plasticos_material_profile |
| BI-INSPECT-09 | Melt flow index and conditions | `scrap_plastic_broker_training_dataset_corrected.csv #8` | plasticos_material_profile |
| BI-INSPECT-10 | Density test or reported density | `scrap_plastic_broker_training_dataset_corrected.csv #4` | plasticos_material_profile |
| BI-INSPECT-11 | Ash content | `scrap_plastic_broker_training_dataset_corrected.csv #32` | plasticos_material_profile |
| BI-INSPECT-12 | Filler and additives | `scrap_plastic_broker_training_dataset_corrected.csv #32` | plasticos_material_profile |
| BI-INSPECT-13 | Metal contamination | `scrap_plastic_broker_training_dataset_corrected.csv #3` | plasticos_material_profile + quality |
| BI-INSPECT-14 | PVC mixing/contamination | `scrap_plastic_broker_training_dataset_corrected.csv #22` | plasticos_material_profile + quality |
| BI-INSPECT-15 | Mixed polyolefin stream | `scrap_plastic_broker_training_dataset_corrected.csv #11` | plasticos_material_profile |
| BI-INSPECT-16 | Label and paper contamination | `scrap_plastic_broker_training_dataset_corrected.csv #11` | plasticos_material_profile |
| BI-INSPECT-17 | Food or organic residues | `scrap_plastic_broker_training_dataset_corrected.csv #3` | plasticos_material_profile + quality |
| BI-INSPECT-18 | Odor and prior quality concerns | `scrap_plastic_broker_training_dataset_corrected.csv #23` | plasticos_material_profile + quality |
| BI-INSPECT-19 | Material photographs | `scrap_plastic_broker_training_dataset_corrected.csv #1` | plasticos_web_leads + ir.attachment |
| BI-INSPECT-20 | Packaging, bale condition and loading | `scrap_plastic_broker_training_dataset_corrected.csv #7` | plasticos_intake + plasticos_logistics |
| BI-INSPECT-21 | Prior contents and hazardous residues | `scrap_plastic_broker_training_dataset_corrected.csv #21` | plasticos_documents + material owner |
| BI-INSPECT-22 | Certificate of analysis | `scrap_plastic_broker_training_dataset_corrected.csv #8` | plasticos_documents_native |
| BI-INSPECT-23 | Chain-of-custody evidence | `scrap_plastic_broker_training_dataset_corrected.csv #8` | plasticos_documents_native |
| BI-INSPECT-24 | Representative sample/lot testing | `scrap_plastic_broker_training_dataset_corrected.csv #4` | plasticos_material_profile + documents |
| BI-INSPECT-25 | Trial processing/load acceptance | `scrap_plastic_broker_training_dataset_corrected.csv #6` | plasticos_offer + logistics |
| BI-INSPECT-26 | Cleaning/washing capability | `scrap_plastic_broker_training_dataset_corrected.csv #11` | facility capability / Gate matching |
| BI-INSPECT-27 | Sorting and separation | `scrap_plastic_broker_training_dataset_corrected.csv #14` | plasticos_material_profile + buyer capability |
| BI-INSPECT-28 | Certifications and compliance documentation | `scrap_plastic_broker_training_dataset_corrected.csv #14` | plasticos_documents_native |
| BI-INSPECT-29 | Supplier quality/performance history | `scrap_plastic_broker_training_dataset_corrected.csv #26` | plasticos_matching + CRM |
| BI-INSPECT-30 | Carrier weights and route feasibility | `scrap_plastic_broker_training_dataset_corrected.csv #2` | plasticos_logistics |
| BI-INSPECT-31 | General contamination characterization | `scrap_plastic_broker_training_dataset_corrected.csv #1` | plasticos_material_profile + web leads |
| BI-INSPECT-32 | Available buyer processing capability | `scrap_plastic_broker_training_dataset_corrected.csv #5` | CEG DomainSpec + facility evidence |

### Material requirements that most improve qualification

1. **Identity:** distinguish seller-reported polymer, image-level observation, and measured FTIR/density identity.
2. **Condition:** identify source process, form, grade, contamination, moisture, MFI and filler only when applicable and attributable.
3. **Commercial context:** distinguish per-load weight from monthly recurrence, actual availability from historical capacity, source geography from invented route miles.
4. **Verification:** retain original inspection/COA/chain-of-custody evidence; AI classification is not document verification.
5. **Compatibility:** measured lot data compared to **buyer-specific** requirements by the approved matching owner, not generic public thresholds.

## 12 reconstructed decision sequences

These sequences are **human-reviewed advisory process proposals**. Some are restatements of existing ADR flow, others are newly composed from donor scenarios and current Odoo boundaries. There is no executable orchestration in this harvest ZIP.

### BI-SEQ-01: Web lead enrichment and disposition

**Disposition:** `REUSE_EXISTING` · **Owner:** `plasticos_web_leads`.

1. Receive original seller payload
2. Normalize unit and text facts
3. Review photo observations separately
4. Reconcile conflicts and missing evidence
5. Evaluate economic recommendation
6. Apply existing deterministic HOT / REVIEW / COLD validator
7. Assign appropriate human review

**Non-authority guard:** ADR-016 already owns classification; knowledge can only supply evidence-based explanations.

### BI-SEQ-02: Material identity and inspection

**Disposition:** `EXTEND_ADVISORY` · **Owner:** `plasticos_material_profile + plasticos_web_leads`.

1. Obtain seller-reported polymer, form, source and samples
2. Compare observations without collapsing contradictory facts
3. Request suitable material test if uncertain
4. Maintain unknown as unknown
5. Return draft questions and risks, not verified identity

**Non-authority guard:** No photo-only polymer approval or unsafe burn-test instruction.

### BI-SEQ-03: Opportunity to draft-quote readiness

**Disposition:** `EXTEND_ADVISORY` · **Owner:** `plasticos_crm_bridge + plasticos_offer`.

1. Resolve active opportunity and lot snapshot
2. Verify material, load quantity and economics source
3. Separate seller ask from current buyer bid
4. Check current delivery and payment terms
5. Present uncertainty and options for broker review
6. Use native offer owner for any draft/issuance

**Non-authority guard:** No synthetic price or silent offer email. Sent state is not proof of delivery.

### BI-SEQ-04: Buyer-fit inquiry and offer selection

**Disposition:** `REUSE_EXISTING` · **Owner:** `plasticos_matching + Gate/CEG`.

1. Start from approved material/opportunity snapshot
2. Initiate canonical Gate match via Odoo
3. CEG executes hard gates and scoring
4. Persist match run and result with lineage
5. Human reviews candidate buyers
6. Owner creates draft offers where authorized

**Non-authority guard:** No local buyer scoring, invented buyer shortlist, or silent Gate fallback.

### BI-SEQ-05: Rejected offer / match recovery

**Disposition:** `PROPOSE_REASON_ADVISORY` · **Owner:** `plasticos_offer + plasticos_matching`.

1. Capture exact buyer refusal and subject
2. Treat rejection vocabulary as a proposed interpretation
3. Check measured spec and buyer-specific evidence
4. Offer clarifying questions and conditional recovery options
5. Broker confirms reason and appropriate next commercial action
6. Keep provenance without automatic permanent exclusion

**Non-authority guard:** A one-time refusal cannot become a global buyer restriction.

### BI-SEQ-06: Quality deviation and evidence review

**Disposition:** `EXTEND_ADVISORY` · **Owner:** `plasticos_documents + material profile`.

1. Observe discrepancy as report or test, with source
2. Determine which original/lot and spec revision it belongs to
3. Propose further inspection or hold to authorized operator
4. Retain earlier approved evidence, add a successor if corrected
5. Apply native verification or claim decision under existing owner

**Non-authority guard:** A coaching SOP is not an approved hold or financial instruction.

### BI-SEQ-07: Freight/appointment exception recovery

**Disposition:** `REUSE_EXISTING` · **Owner:** `plasticos_logistics`.

1. Identify actual load, weight basis and route
2. Check capacity, carrier and current schedule evidence
3. Propose alternatives, with uncertain costs explicit
4. Request approved logistics action and document it
5. Do not represent scheduling advice as physical dispatch

**Non-authority guard:** No guessed vehicle capacity, rate, permit or external communication.

### BI-SEQ-08: Supplier and repeat-stream qualification

**Disposition:** `EXTEND_ADVISORY` · **Owner:** `plasticos_intake + material profile + CRM`.

1. Record supplier-reported material stream and frequency
2. Distinguish current inventory from recurring capability
3. Request samples, photos and quality/volume verification
4. Document unresolved source risks
5. Have broker admit any marketable opportunity via native workflow

**Non-authority guard:** Supplier claim is not proof of stock or buyer demand.

### BI-SEQ-09: Terms negotiation and exceptions

**Disposition:** `EXTEND_ADVISORY` · **Owner:** `plasticos_offer`.

1. Read current native offer terms and expiration
2. Identify the precise disagreement and affected parties
3. Generate nonbinding options using only source-backed inputs
4. Broker chooses amendments via offer owner
5. Record actual counterparty response separately

**Non-authority guard:** No invented floor, ceiling, discount or standard net-30 restriction.

### BI-SEQ-10: Material and shipment evidence readiness

**Disposition:** `REUSE_EXISTING` · **Owner:** `plasticos_documents_native + native documents`.

1. Read document requirements for the specific operation
2. Identify missing originals and associations
3. Classify/OCR without implying verification
4. Route to authorized document reviewer
5. Return state of verification and unresolved gaps

**Non-authority guard:** Obsolete customs/regulatory answers remain quarantined; source receipts matter.

### BI-SEQ-11: Broker coaching and review-driven improvement

**Disposition:** `PROPOSE_ADVISORY` · **Owner:** `plasticos_broker_intelligence_mack + training corpus`.

1. Record a real broker task and approved outcome
2. Match observed case to a candidate coaching scenario
3. Surface source and unverified SOP status
4. Human resolves applicable owner/process
5. Label scenario and add to frozen evaluation only after review
6. Use feedback to propose knowledge revision, not change business fact

**Non-authority guard:** The 56 coaching rows do not establish that the referenced SOPs exist.

### BI-SEQ-12: Product-to-scrap reverse reasoning hypothesis

**Disposition:** `DEFER_ACTIVATION` · **Owner:** `material profile + optional semantic kernel / EIE`.

1. Observe a product/process clue and source
2. Retrieve relevant technical candidate from PP KB
3. Form a hypothesis of likely scrap type
4. Request verifying material evidence
5. Never promote hypothesis to current supply or buyer requirement

**Non-authority guard:** Do not use speculative KB buyer profiles as confirmed demand or live CEG rules.

## PP knowledge base: additional high-value crosswalk

The existing `plasticos_enrichment/knowledge_base/plasticos_kb_PP_v8.0.yaml` is indexed as **12 separate candidate sections** in `comparisons/pp_kb_crosswalk.jsonl` at an exact Git blob SHA. It covers grades, product-to-scrap mappings, quality indicators, contamination, recycling rules, process guidance and inference rules.

**Not admitted:** v8 numeric polymer tolerances, food-contact legality, 25-40% premiums, claimed 90%+ confidence as validated probabilities, processing-lifetime formulas, live buyer programs or hard-coded matching gates. These require scientific/regulatory/market source validation at their respective owners. The source `data_quality: verified` is a donor assertion, not independent external verification. The older PP v7.0r and template are research/comparison sources, not parallel canonical KBs.

## Core result

**Already owned:** identity, intake, triage, buyer match/scoring, offers, logistics, documents, and phase-human checkpoints. **Missing or unproven:** shared approved procedural advisory, reconciled rejection vocabulary, production Mack conversational reasoning, broker-labelled evaluation/feedback, reviewed SOPs and current-source pricing. This harvest proposes no second business owner or authorization system.

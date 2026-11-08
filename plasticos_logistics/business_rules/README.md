# Linda Logistics business requirements (BRS)

**Authoritative location:** `plasticos_logistics/business_rules/` inside the **logistics Odoo module**. Not `docs/`, and not a standalone service.

**Status:** Operator-directed local product requirement baseline upon merge to `Staging` (2026-10-23). The seven source BRS documents and three source machine/traceability files are preserved **byte-for-byte** from the supplied v1.1.1 campaign. Original in-document `Candidate` headers describe their **pre-registration source status**, not a later verdict on this local registration. The machine `rules.json` retains historical wording for exact provenance; it is **not by itself** the current full operating policy where explicitly superseded below.

## Mandatory agent and implementation use

1. Before work on `plasticos_logistics` or cross-module behavior that materially changes Linda, read this index, the relevant `BRS-0N.md` documents, `BRS-POS-10-linda-logistics-commercial-and-physical-communication.md`, the admitted `BRS-POS-09-R006` through `BRS-POS-09-R012` clauses in `SUPERSESSION.md`, and applicable Accepted repository ADRs under `docs/adr/`.
2. Treat non-superseded BRS requirements as **target behavior** to realize/test, not as an assertion that code or external systems already implement them. Never silently weaken or delete a business requirement to pass a test.
3. Read `SUPERSESSION.md` for the **narrow, later explicit operator rulings** on independent PO/SO issuance and fulfillment. These override only the identified older BRS assertions; every unrelated rule remains intact.
4. The BRS documents constrain **what** the logistics product must do. Accepted ADRs govern **architecture/ownership and boundaries**. Neither silently repeals the other; when a genuine unresolved conflict remains, flag that precise conflict and stop the affected design or change.
5. Each implementation/PR must identify the impacted BRS rule IDs and give an observable test or explicitly mark `NOT_RUN`/blocked. Changes to current business policy require an explicit decision/supersession entry, not an unlogged rewrite of source snapshots.
6. Do not treat the BRS source-pack checksums as runtime acceptance; they attest preservation only. No Gmail live send, release approval, DB migration or deployment is authorized by registration.

## BRS index

| File | Concern |
| --- | --- |
| [BRS-01.md](BRS-01.md) | Transaction, movement identity and company boundary |
| [BRS-02.md](BRS-02.md) | Supplier readiness and verified responses |
| [BRS-03.md](BRS-03.md) | Appointments and facility constraints |
| [BRS-04.md](BRS-04.md) | Freight policy and carrier booking |
| [BRS-05.md](BRS-05.md) | Dispatch, communications and confidentiality |
| [BRS-06.md](BRS-06.md) | Checkpoints, reminders and escalations |
| [BRS-07.md](BRS-07.md) | Delivery proof, documents and closeout |

**Aligned implementation plan:** [`../LINDA_BUILD_PLAN.md`](../LINDA_BUILD_PLAN.md) owns WP00-WP11, source-exact reminder clocks, 30 A-scenarios, and the 60-rule BRS-to-WP-to-source-AC crosswalk. This is the *same plan* distributed as a standalone Markdown download, not a second rule authority. **A plan cannot silently supersede a BRS**; when interpretations differ, inspect the ID-specific operator register and Accepted ADRs.

**Companions:** `rules.json` (all 60 historical source assertions), `OWNER_INDEX.json` (seven source concern owners), `BUSINESS_RULE_TRACEABILITY.csv`, `REGISTRY.json` (source hashes and rule inventory), `operator_intent.json` and `policy_resolution.json` (source provenance), and [SUPERSESSION.md](SUPERSESSION.md) (current operator amendments).

**Precedence:** explicit later operator decision > earlier contradictory candidate requirement; applicable canonical organizational law and Accepted architecture ADRs retain their own authority and must be reconciled if they conflict. Neither a draft build-plan statement nor a stale agent prompt can silently overwrite a registered requirement. Every materially superseded BRS clause must be cited by stable ID.

<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_BEGIN -->
## 2026-10-26 effective native-first logistics ↔ Documents alignment

**Proposed for repository admission, not an implemented/live workflow.** The 2026-10-27 reconciliation keeps these alignment files and matches every non-documentation blob to #316 head `53b18fd90046696e946a0d8e1e60e88595a5e143`. That match is not runtime acceptance. Read `EFFECTIVE_RULES.md` (all 60 current interpretations), `EFFECTIVE_RULES.json` (machine form), `NATIVE_DOCUMENTS_INTEROP.md` (one-owner architecture and exact native feature boundaries), `BRS_POS_CROSSWALK.csv` (cross-domain references), and `ALIGNMENT_ACCEPTANCE.md` (positive and adversarial tests). `OPEN_DECISIONS_AND_PROOFS.md` keeps unverified Odoo Enterprise capabilities and business disputes open.

The seven original `BRS-01..07.md`, 60 historical `rules.json`, `REGISTRY.json`, owner index and provenance remain **byte-for-byte unchanged**. The current `SUPERSESSION.md` including October 24 cancellation and October 25 inbound AI amendments is **preserved**, with one 2026-10-26 additive alignment section. These effective specs use immutable source IDs and do not create new duplicate BRS IDs. `BRS-POS-*` refers to the exact separate PlasticOS Native-First BRS v1.0.0 working artifact; the full cross-domain pack is **reference-only**, not a second copied authority inside this module.

**Coding agents:** cite both affected `BRS-##-R###` and `BRS-POS-##-R###` where applicable. Tests must assert positive and negative outcomes on the exact installed Odoo 19 Enterprise revision. No BRS installation permits external sends, native AI activation, migration, merge or deployment. If the next code PR branches from this new BRS PR, rebind any older remediation scripts hard-pinned to PR #305; do not bypass their SHA guards.
<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_END -->

The dated supersession of 2026-11-05 admits exactly one copied Native-First chapter, BRS-POS-10, and admits BRS-POS-09-R006 through BRS-POS-09-R012 as Linda external-send obligations. Every other BRS-POS chapter stays a cross-domain reference and is not a second copied authority. BRS-POS-04 through BRS-POS-08, BRS-POS-11 and BRS-POS-12 stay with their owners.

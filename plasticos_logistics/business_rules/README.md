# Linda Logistics business requirements (BRS)

**Authoritative location:** `plasticos_logistics/business_rules/` inside the **logistics Odoo module**. Not `docs/`, and not a standalone service.

**Status:** Operator-directed local product requirement baseline upon merge to `Staging` (2026-10-23). The seven source BRS documents and three source machine/traceability files are preserved **byte-for-byte** from the supplied v1.1.1 campaign. Original in-document `Candidate` headers describe their **pre-registration source status**, not a later verdict on this local registration. The machine `rules.json` retains historical wording for exact provenance; it is **not by itself** the current full operating policy where explicitly superseded below.

## Mandatory agent and implementation use

1. Before work on `plasticos_logistics` or cross-module behavior that materially changes Linda, read this index, the relevant `BRS-0N.md` documents, `SUPERSESSION.md`, and applicable Accepted repository ADRs under `docs/adr/`.
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

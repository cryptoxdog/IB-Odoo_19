# PlasticOS Export business requirements (BRS)

**Authoritative location:** `plasticos_export/business_rules/` inside the Export Odoo module. Not `docs/`, and not a standalone service.

**Status:** operator-approved module baseline (module approval and code grant, 2026-11-11). The 14 chapters, `rules.json` (120 rules) and `ACCEPTANCE.json` (120 cases) are byte copies of Export BRS v2.0.0 from the campaign pack `docs/campaigns/future-add-ons/PlasticOS_Export/EXPORT_BRS/`. `REGISTRY.json` records their SHA-256. Registration is not evidence that any rule is implemented; every acceptance case is `NOT_RUN`.

## Mandatory agent and implementation use

1. Before work on `plasticos_export`, or on a Logistics, Documents, Linda or native change made for Export, read this index, the relevant `BRS-EXP-NN.md` chapters, `SUPERSESSION.md`, and the accepted ADRs under `docs/adr/`.
2. Treat each rule as target behavior to realize and test, not as a claim that code already does it. Never weaken or delete a rule to pass a test.
3. Each implementation PR names the rule IDs it realizes and gives an observable test, or marks the case `NOT_RUN`/blocked. `BUSINESS_RULE_TRACEABILITY.csv` gives each rule its campaign slice and witness case.
4. The BRS say **what** Export must do. Accepted ADRs govern ownership and boundaries. When they conflict, name the exact conflict and stop the affected change.
5. A change of business policy is a dated entry in `SUPERSESSION.md`. Never edit a byte copy.
6. Phase `P2` rules (17, including FindTEU and ACE AESDirect) stay in force as requirements and are out of the Phase 1 campaign.
7. Nothing here authorizes an external send, native AI activation, a migration, a merge or a deployment.

## BRS index

| File | Concern |
| --- | --- |
| [BRS-EXP-01.md](BRS-EXP-01.md) | Native-first boundaries and minimality |
| [BRS-EXP-02.md](BRS-EXP-02.md) | Booking identity, six fields and schedule evidence |
| [BRS-EXP-03.md](BRS-EXP-03.md) | Document applicability, evidence and reporting |
| [BRS-EXP-04.md](BRS-EXP-04.md) | Phase 1: recycler FOB pickup and FAS port/rail |
| [BRS-EXP-05.md](BRS-EXP-05.md) | Phase 2: international sale and ocean obligations |
| [BRS-EXP-06.md](BRS-EXP-06.md) | Security, exceptions, readiness and acceptance |
| [BRS-EXP-07.md](BRS-EXP-07.md) | Transport equipment types, booking quantities and container identity |
| [BRS-EXP-08.md](BRS-EXP-08.md) | Multi-order commitments, partial fulfillment, buyer-optional cargo and allocation |
| [BRS-EXP-09.md](BRS-EXP-09.md) | Native Odoo 19 AI booking extraction, exact association and guarded transitions |
| [BRS-EXP-10.md](BRS-EXP-10.md) | Logistics/Linda handoff, schedule constraints and audience-safe packet issuance |
| [BRS-EXP-11.md](BRS-EXP-11.md) | Real-world booking correspondence, rolls and AI coordinator behavior |
| [BRS-EXP-12.md](BRS-EXP-12.md) | Phase 2 provider integrations (FindTEU + ACE AESDirect) |
| [BRS-EXP-13.md](BRS-EXP-13.md) | Booking form, extended fields and documentary reconciliation |
| [BRS-EXP-14.md](BRS-EXP-14.md) | Native Odoo reporting and operational intelligence views |

## Companions

| File | What it is |
| --- | --- |
| `rules.json` | The 120 rules, byte copy of `EXPORT_BRS/REGISTRY/rules.json`. |
| `ACCEPTANCE.json` / `ACCEPTANCE.md` | The 120 cases, byte copy of `EXPORT_BRS/ACCEPTANCE/cases.json`, and its table rendering. |
| `REGISTRY.json` | Chapter list, rule IDs in order, SHA-256 of every byte copy and its pack path. |
| `OWNER_INDEX.json` | Chapter to rule IDs and phases. |
| `BUSINESS_RULE_TRACEABILITY.csv` | Rule to campaign slice, proposed owner surface, refined brief and witness case, from `MODULE_DESIGN/RULE_REALIZATION_MATRIX.csv`. |
| `SUPERSESSION.md` | The v1.2 to v1.9 supersessions already folded into the text, and the place for future ones. |
| `OPEN_DECISIONS_AND_PROOFS.md` | Owner decisions and proofs still open. |
| `EFFECTIVE_RULES.json` / `EFFECTIVE_RULES.md` | The current statement of every rule, as Documents publishes its own. |

## Slice assignment

`BUSINESS_RULE_TRACEABILITY.csv` assigns every rule to exactly one slice of the campaign plan (`STRATEGIC_EXECUTION_PLAN_v2.8.md`), from the matrix's `proposed_owner_surface`: `P2` rules go to `PHASE2`; a surface naming `plasticos_export` to `S5`; Linda to `S4`; `plasticos_logistics` to `S2`; a Documents owner to `S3`; every native, cross-owner or release surface to `S6`, the combined Enterprise run. The `slice_basis` column states the reason for each row. A slice that finds a rule belongs elsewhere moves the row in its own PR and says why.

**Precedence:** an explicit later operator decision recorded in `SUPERSESSION.md` over an earlier rule; canonical organization law and accepted ADRs keep their own authority. A plan or prompt cannot overwrite a registered rule.

`tests/contracts/test_export_brs_registry.py` checks the byte copies, the rule order, the chapter headings, the supersession references and the traceability map. It is a source-integrity test, not a runtime test.

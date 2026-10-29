# Ordered source-authorized delivery graph (not dispatched)

| Unit | Purpose | Depends on | Effects |
| --- | --- | --- | --- |
| U00 | Source/runtime/manifest/ADR evidence and scoped no-change Gate/matching contract review | none | E01,E02,E03,E04 |
| U01 | Security and dead local path remediation before adding review UX | U00 | E05,E06,E07,E08,E09 |
| U02 | Capture completed Gate results into immutable typed per-field proposal projections | U01 | E10,E11,E12,E13 |
| U03 | Human approval, legacy Inject rewire, durable atomic writeback and retry | U02 | E14,E15,E16 |
| U04 | Native Odoo review UX, contact tab, company rules, addon manifest/tests wiring | U03 | E17,E18,E19,E20 |
| U05 | Non-destructive upgrade, retired cron/privilege cleanup, precise ADR-012 correction and README | U04 | E21,E22,E23,E24,E25,E26 |
| U06 | Odoo 19 Enterprise tests, negative controls, QA and independent review | U05 | E27,E28,E29,E30 |
| U07 | Operator-specific Staging shadow readiness and explicit source exclusions, not production activation | U06 | E31,E32,E33 |

## Gate stages

**U00: read-only precode.** Pin actual installed Odoo.sh Enterprise, Gate packet shape, dynamic actions and company/grant semantics. Establish no new app/repo needed; correct any newly observed source effects before code grant. No code mutation.

**U01: security-first.** Lock audit/terminal state and eliminate broad CRUD/legacy execution bypass. Guard retired cron manager privilege only with installed evidence. Risk reduction precedes UX.

**U02: data and evidence.** Add one narrow proposal-line model to existing addon. Keep read-only raw Gate summary/provenance, no writes. Make no-eligible-fields truthful.

**U03: server apply.** Native human decisions + row-lock CAS + strict allowlist + atomic actual provenance, plus safe legacy Inject compatibility and retry.

**U04: native review and company roles.** Forms, contact tab, record rules/ACL, manifest/init and test import registration.

**U05: migration/ADR.** Versioned additive upgrade only after actual installed version, retired crons OFF, cron group grant reconciled, ADR-012 corrected, README/current version aligned.

**U06: Enterprise/code audit.** All local and root tests, existing contract tests, ACL/RPC/tenant/replay, migration and restore, independent diff review.

**U07: ready-but-disabled.** Isolated staging shadow use with recorded-shape response, no live paid requests; operator separately decides publication/deployment. Auto-writeback remains off.

## Dependency placement

`U00 -> U01 -> U02 -> U03 -> U04 -> U05 -> U06 -> U07`. Each unit has exactly one source-owned effect allocation in `case.json`, with explicit source/consumer/negative-proof links. Full DAG and file change matrix are machine-readable under `DELIVERY/DEPENDENCY_GRAPH.json`, `PLAN/FILE_CHANGE_LEDGER.json` and `PLAN/SOURCE_EFFECT_TO_PROOF.json`.

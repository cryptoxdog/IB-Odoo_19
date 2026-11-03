# EXISTING WIP | preserve before correction

**Derived from:** same project `case.json`; not a replacement specification.

- **Target:** repo, `Staging` SHA, WIP base/head, affected PRs including stacked children and relevant merge-base facts.
- **Intended business result:** exact user decisions and scope.
- **What actually runs:** source paths/blobs, tests and environments; observed versus reported versus inferred.
- **Protected code:** existing correct methods, model identity, user flows, negative tests, callbacks, data revisions, accepted external contracts.
- **Applicable authority:** repo `INVARIANTS.md`, relevant full-path ADR(s), current module BRS/supersession and human decisions.

| Existing capability | Observed at immutable SHA | Test/host witness | PRESERVE / ALIGN / SPLIT / SUPERSEDE / RETIRE | Smallest justified correction | Regression falsifier |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

**Union coverage:** Expand effects across the whole relevant PR train, not just the first PR in order. For every changed/unchanged consumer include direct and transitive declarations, SQL/QWeb, security, mail/crons, possible installed Enterprise/DB actions, version/migrations, regression tests, rollback and release order.

**Drift policy:** A newer merged source-owner fix replaces a stale plan to rebuild the feature; preserve its SHA and observed behavior. An unresolved conflict may block only dependent work, not unrelated accepted history. A source plan `PASS` is not an Odoo EE test or authorized merge.

**Handoff:** one exact `case.json` digest, current accepted invariants and BRS IDs, cross-PR dependency order, source owner, smallest change units, protected tests and explicit open unknowns. No PR action or code authorized.

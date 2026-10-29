# Narrow source-owner ADR and doc amendments

| Repo owner | Original source/authority | Decision to adopt | Preserve |
| --- | --- | --- | --- |
| CEG | docs/FEATURE_GATES.md | Show repo defaults false, future disabled-to-ready verification, separated read health and paid worker; no current activation claim. | Other feature gates and SDK participation |
| CEG | engine/spec.yaml, engine/handlers.py, tests/architecture/test_seam_gate_only.py | Keep health-assess canonical read route; strictly no admin actions; consume real Gate owner declaration. | match/sync/resolve/outcomes behavior |
| Gate | constellation-gate/docs/adr/ADR-action-ownership.md | Narrow addition of health-assess -> CEG and comprehensive static/dynamic action/readiness contract. | Other accepted owners, nonreplay default |
| Gate | constellation-gate/src/constellation_gate/config/node_registry.yaml | Add advertised health route only to graph; do not permit admin/enrich on CEG. | EIE advertises enrich/graph-inference-result |
| EIE | docs/contracts/dependencies/constellation-gate.yaml | Version any change to accepted graph-inference-result durability/consume semantics; keep packet tenant authority. | Only Gate transport, per-tenant graph sync matching |
| Odoo | INVARIANTS.md and all Odoo ADRs | NO_CHANGE. Original upload retains Odoo source for methodological planning only. | Commercial, import, Web Lead, offers, Semantic Kernel |

No ADR is admitted in this ZIP. Each repository owner must allocate its own final ADR number/commit, accept scope and update dependent tests/contracts before coding.

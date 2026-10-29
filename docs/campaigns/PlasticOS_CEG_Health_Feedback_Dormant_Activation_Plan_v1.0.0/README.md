# PlasticOS CEG Health → Gate → EIE

## Scoped #2 dormant activation plan, v1.0.0 | 2026-10-29

**Bottom line:** The mechanism is partly built and **not ready for autonomous use**. This plan does not enable it. It defines the smallest source-owned repairs and proof gates before a separately authorized future activation.

**Only scope:** CEG health assessment, controlled automatic enrichment dispatch via Gate to EIE, graph-inference feedback returned via Gate, and verified health reassessment. **Explicitly deferred:** previous workstream #1 Offer Drafting, Web Lead PR #329, Semantic Kernel, inferred supply-demand program, Odoo changes, response agents, pricing, autonomous sales, paid calls or production deployment.

### Locked deployment posture

| Gate | Current required posture | Future target AFTER approval |
|---|---|---|
| `HEALTH_API_ENABLED` | OFF | ON, health-read-only route first |
| `AUTO_ENRICH_VIA_GATE` | OFF | ON only with active tenant budget, durable dispatch, proven Gate→EIE |
| `GRAPH_INFERENCE_FEEDBACK_ENABLED` | OFF | ON only after durable receive/converge/reassess feedback |
| `HEALTH_COMMERCIAL_MODE_ENABLED` | OFF (unchanged) | Remains OFF; excluded |
| Unvalidated/dormant domain packs, local fallback | OFF (unchanged) | Remain OFF |

Code-level defaults stay FALSE; **no flags have been changed**. A green plan does not constitute production activation authority.

### Start here

1. `EXECUTIVE_BRIEF.md`: why not ready and what to do.
2. `INVARIANTS/HEALTH_KERNEL.md`: scope, safety and failure predicates.
3. `PLAN/WHOLE_CHANGE_PLAN.md` and `PLAN/FILE_CHANGE_LEDGER.csv`: file-level owner dispositions and blast-radius accounting.
4. `PLAN/WIRING_AND_CONTRACTS.md`: two paths, each edge, success/failure semantics.
5. `PLAN/DELIVERY_GRAPH.json` and `DELIVERY/EXECUTION_GATES.md`: ordered bounded units and code-to-runtime proof barriers.
6. `ADRS/`: proposed source-owner ADRs/precise amendments, not yet adopted.
7. `EVIDENCE/SOURCE_REGISTER.json`, `CASE/case.json`, `ASSURANCE/`: immutable source refs, schema and package-only proof.

Original kernel v0.2.0 is preserved under `PLANNING_KERNEL/`. Its Odoo-specific manifest/precode validator cannot certify this cross-repository target without fabricating Odoo governance; the pack uses the kernel's case schema and a dedicated cross-repository effects/graph validator. No source-host authorizations, cross-repo edits, live EIE calls, deployments, merges, tests against running services or paid API usage occurred.

### Source epoch

- CEG `0d84ec8531baf604383c5ddc012f40aa84fc4b76`
- Gate `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`
- EIE `3f96eda98240789963b0e6534aa2151aed12658e`

Source code confirms contracts and gaps, **not current deployed behavior**. Full-runtime registry/tenant/action grants and actual worker environment are not observed. These remain explicit U00 prerequisites.

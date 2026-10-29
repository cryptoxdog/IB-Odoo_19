# #2 CEG Health activation invariants

**Business scope and disabled-until-proven posture are operator decisions.** Technical invariants below are proposed source-owner contracts for safe development, not already admitted canonical ADRs.

**H-01.** Exactly one scope: CEG graph health and enrichment feedback through Gate to EIE. No Offer Drafting, Web Lead PR329, Odoo Semantic Kernel, CRM writeback, payment, sales or procurement work.

**H-02.** Current intended deployment is DISABLED. No environment variable or deployed configuration is changed by this pack. Eventual enablement needs fresh explicit release/operator approval.

**H-03.** Code-level defaults for HEALTH_API_ENABLED, AUTO_ENRICH_VIA_GATE and GRAPH_INFERENCE_FEEDBACK_ENABLED remain false for fail-closed rollback.

**H-04.** Health assessment/report is read-only. Public/canonical health-assess calls cannot incur paid enrichment side effects merely by viewing health.

**H-05.** CEG exclusively owns health assessment, due entity discovery, ROI ordering and bounded scheduler. No additional Odoo health selector or local inference engine.

**H-06.** Gate is the only CEG-to-EIE routing authority. `health-assess` is CEG-owned; `enrich` and `graph-inference-result` remain EIE-owned. No CEG->EIE direct peer call or worker impersonation.

**H-07.** Tenant identity is canonical: signed packet tenant == domain id == Neo4j database; no payload override or cross-company/tenant data traversal.

**H-08.** No job is dispatched without explicit current tenant/field allowlist, bounded queue/rate, source freshness, provider budget authorization and operation state.

**H-09.** ROI estimates are advisory and cannot authorize paid spend alone. Existing assumed $1,000 deal value/expected improvement is not calibrated commercial evidence.

**H-10.** Durable identity and recovery must cover operation+input revision+tenant+target fields. Retried, reordered or repeated jobs cannot multiply paid work or resurrect stale data.

**H-11.** Transport acknowledgement, EIE accepted/durable result, graph sync and measured CEG health reassessment are different states; report each accurately.

**H-12.** Graph-inference feedback is attributable, tenant-bound, rule-versioned, confidence-filtered, bounded and consumed on an authorized convergence pass; no inference from the result can recursively self-trigger indefinite work.

**H-13.** EIE return-channel acceptance cannot silently discard work on queue-full, process restart or multi-worker routing; recoverable disposition is required before automation.

**H-14.** Disable must stop new paid requests, scheduled jobs and retries without erasing evidence; read-only health may be disabled independently if unsafe.

**H-15.** No activation based on unit mocks, feature flags printed true, an HTTP 200, queue length or a single packet. A real two-node Gate route, persistence and health change must be proven.

**H-16.** Scope includes only minimal required changes at authoritative source owners. Reuse Gate SDK and existing scheduling/evidence storage when sufficient; no new framework, transport or infrastructure by default.

**H-17.** Existing unrelated controls remain: health commercial tiers, GDPR erasure, unvalidated/dormant domain pack admission, legacy chassis and direct peer ingress are NOT enabled.

**H-18.** Source-owner approval, accepted ADRs, independent code review, runtime tests and exact deployment configuration are separate from this planning document. Unknown never counts as proof.

## Immediate falsifiers

- Any non-test automatic/paid enrichment dispatch with flags OFF: **FAIL**.
- Any authenticated `health-assess` read that silently spends EIE budget: **FAIL**.
- Graph entity loader returns `[]` because no production loader was supplied, while job reports successful scan: **FAIL**.
- Handler/action advertised but Gate rejects/unresolvably routes `health-assess`: **FAIL**.
- EIE accepts feedback packets but drops targets on queue-full or restart while reporting successful convergence: **FAIL**.
- A consumer's tenant/domain controls a different Neo4j database than its packet tenant: **FAIL**.
- An inferred field triggers repeated paid requests by echoing itself without new external evidence: **FAIL**.
- Repeated jobs overrun operator-approved hard spend/call ceilings: **FAIL**.
- Any code/ADR/flag modification to Offer Drafting, Odoo CRM, or Semantic Kernel: **SCOPE VIOLATION**.

## Inherited planning-kernel treatment

The supplied PlasticOS Odoo kernel and its Odoo `INVARIANTS.md` snapshot remain **byte-preserved as method inputs**. They are not silently promoted to governing constitutional authority over CEG, Gate or EIE. The transferable planning safeguards (POS-INV-26 blast-radius coverage, single-source ownership, independently verifiable changes, no hidden runtime permission) govern this *working plan* as operator requirements. Source owners must adopt the external technical invariants through their own accepted ADR process.

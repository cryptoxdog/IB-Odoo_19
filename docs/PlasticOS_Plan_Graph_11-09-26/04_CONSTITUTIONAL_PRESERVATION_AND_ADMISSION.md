# Constitution preservation and obsolete-rule adjudication (design only)

The *current admitted* `cryptoxdog/IB-Odoo_19/INVARIANTS.md` at `Staging@04bd0594...` is **v2.2.0**. The uploaded v3.0.0 r3, donor v3.1.0 and this v3.2.0 are unadmitted candidates. Do **not** replace the admitted file wholesale with a shorter elegant draft, because enforcement details and some prior policies would silently disappear. The owner must approve a complete clause-level reconciliation first.

| Existing v2.2 law / mechanism | Proposed home | Preservation or decision required |
|---|---|---|
| 1 Odoo 19 API/view compatibility | POS-INV-19 | Preserve forbidden-pattern CI scripts and exact Odoo 19 model checks; not just a summary |
| 2 acyclic addon graph | 19 | Keep precise `depends` and layer checks |
| 3 namespace | 19 + existing namespace policy | All `plasticos_*` names remain; no product rename |
| 4 deterministic seed doctrine | 19 + seed owner ADR | **CONFLICT** between blanket historical `noupdate` guidance and contextual seeded record lifecycles. Do not waive until admitted decision and migration proof |
| 5 graph isolation fallback | 17/18 | **CONFLICT**: legacy empty-return fallback versus typed durable failure evidence. Preserve safety while classifying unresolved outcomes; do not call empty success |
| 6 partner architecture | 01/02/05/19 | Preserve res.partner and facility data ownership and native fields |
| 7 layer dependency direction | 19 | Preserve module layer prohibitions and acyclic resolver |
| 8 effective ACL / record-rule completeness | 05/19 | **CONFLICT/REVIEW**: do not delete permissive rows without accepted replacement role matrix; effective ORM rights and workflows must remain safe |
| 9 external ID referential integrity | 19 | Preserve XML ID and load-order checks |
| 10 test isolation | 20 | Keep disposable approved fixture and rollback safety; no production test mutation |
| 11 API isolation | 17/18/20 | Preserve timeouts, auth and secure error semantics |
| 12 model name uniqueness | 19 | Preserve registry uniqueness checks |
| 13 field references | 19 | Preserve exact field/related-path checks |
| 14 migration safety | 19/20 | Preserve nondestructive/approved migration proof and version bump |
| 15 cron discipline | 15/19/20 | Native cron owner only, no new auto activation |
| 16 safe cross-addon imports | 19 | Preserve Odoo registry import-order checks |
| 17 file wiring | 19 | Preserve `__init__` and manifest include/load checks |
| 18 XML view compatibility | 19 | Preserve exact Odoo 19 view constraints |
| 19 external intelligence authority | 17/18 | Canonical Gate/Gate_SDK EIE/CEG transport and failure contract; no local shadow intelligence |
| 20 legacy identifier ban | BAN001 | Entire prohibition text **unchanged**; its sole blocking checker, precommit/CI wiring and negative controls remain intact |

### Proposed new constitutional content (already in source candidate)

- POS-INV-21: distinct PO, SO, stock, allocation, load, booking identities and legitimate cardinalities; no invented buyer or order.
- POS-INV-22: source revisions change only attributable dependent obligations; cannot cause an unapproved resend, posting or dispatch.
- POS-INV-23: commercial party/owner, shipper, legal risk, physical destination, transport arranger and event milestones remain distinct.

### Revised in this successor (not new identities)

- POS-INV-06: one original, many exact typed links; proposal vs accepted association separated; no partner-recency linking.
- POS-INV-16: native Documents AI and external intelligence output are **typed candidate evidence and proposed actions**, not a business-action grant; action owner owns validation and write.
- POS-INV-21: mandatory future-compatible **semantics**, explicitly not a mandate to mutate current singular schema or commence Export/physical operations now.
- POS-INV-22: scope-specific revision dependency and history, without automatic email/dispatch/financial effects.

### Admission frontier

**Gate A:** current admitted section-by-section v2.2 text + code/checker enforcement frozen and diffed. **Gate B:** operator rules on seed lifetime, external-intelligence failure outcomes and effective role ACL policy captured with testable acceptance. **Gate C:** reconcile accepted Logistics/Documents BRS, native Enterprise contracts and ADRs by exact ID; no BRS duplication. **Gate D:** design independent positive and negative tests; distinguish unexecuted design checks from runtime. **Gate E:** explicit operator approval of candidate constitutional meaning. **Only after E** may an authorized documentation-only repository change revise the admitted invariant source and agent rule references. Implementation and activation remain different authority and tests.

These are **design-time gates**, not a request to run a code campaign. A staged MVP does not require a rewritten constitution to perform independently authorized operations under the currently admitted law.

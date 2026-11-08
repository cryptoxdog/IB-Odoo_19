# v2.7.1 | Upstream file map + mandatory pre-code ripple gate

**New operator invariant:** **No code gets written until every ripple effect is accounted for.**

- `EXPORT_BRS/INTEROP/UPSTREAM_FILE_CHANGE_MAP_v2.7.md` is the exact source-pinned file-level change/new-file map; preserving the prior review avoids losing affected owners and paths.
- `EXPORT_BRS/INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md` is the single operating definition of the pre-code check. Seven evidenced root frontiers remain **OPEN**; this file is not a PASS receipt or code authorization.
- `GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r1.md` adds only **POS-INV-26** (Pre-Code Ripple-Effect Accountability), preserving all POS-INV-01..25 and BAN001 normative text byte-for-byte. The existing v3.3.0 DRAFT is retained as a distinct predecessor. Constitutional repository v2.2.0 remains unchanged.
- `GOVERNANCE/INVARIANT_NEGATIVE_PROBES.md` adds INV-P16 to make omissions and false 'no impact' determinations falsifiable.

**Precedence:** v2.7 technical architecture and all 120 frozen BRS/120 acceptance texts are unchanged. This update adds a mandatory **pre-code process gate**, not new export capability, not an implemented owner API, not a new addon and not semantic admission to the repository.

**Stop:** until all direct/transitive material ripple effects of a proposed slice have evidence, owner, disposition, migration and proof plan, **do not write code**. Newly discovered effects require reopening the affected map, not improvising implementation or silently expanding scope. No branch, PR, migration, external send or deployment is authorized by this ZIP.

**Privacy:** original evidence files remain in the pack. The ZIP is internal only and must not be committed whole to a public repository.

# v2.7.2 | Full blast-radius documentation and complete pre-code plan

**Latest operator wording:** "Blast radius must be fully documented and all changes accounted for and planned for." This strengthens the existing POS-INV-26 draft without changing the Odoo product architecture.

- `GOVERNANCE/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md` refines only POS-INV-26. The v3.4.0 r1 draft remains intact as provenance; POS-INV-01..25 and BAN001 are unchanged.
- `EXPORT_BRS/INTEROP/PRE_CODE_RIPPLE_CLOSURE_GATE.md` is the existing operative gate, now requiring one complete change-set plan, exact file/action and owner disposition for **every** material direct/transitive ripple, and acceptance before the first source/test/migration edit.
- `EXPORT_BRS/INTEROP/UPSTREAM_FILE_CHANGE_MAP_v2.7.md` remains the unchanged source-pinned candidate map. Its rows are inputs to, not substitutes for, a full blast-radius closure.
- `GOVERNANCE/INVARIANT_NEGATIVE_PROBES.md` updates INV-P16 so a missing plan, unsupported no-change or later unplanned edit is a negative witness.

**Current status: BLOCKED / IMPACT PLAN INCOMPLETE.** The seven RP-01..07 frontiers are known, not completely accepted or planned. No repository source, PR, Enterprise test or deployment was changed by this ZIP. This is a private working pack and includes private operator source evidence that must not be committed wholesale.

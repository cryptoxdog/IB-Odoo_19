# Preliminary existing v2.2.0 to draft v3.1.0 mapping (NOT ADMITTED)

**Observed source:** `cryptoxdog/IB-Odoo_19` Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112 `INVARIANTS.md` v2.2.0 Constitutional, source SHA `c16e99c575a262ff6279f2202e5959f777b2fc6f`. This is a heading-and-mechanism mapping, **not** the independent complete section-by-section v2.2-to-v3 adoption proof that the uploaded draft demands.

| v2.2 invariant | Candidate v3.1 home | Admission and non-weakening note |
|---|---|---|
| 1. Odoo 19 Compliance | POS-INV-19 | Existing explicit deprecated-pattern checks and CI remain in force; candidate prose alone is insufficient replacement |
| 2. Dependency Graph Acyclicity | POS-INV-19 | Preserve acyclic dependency and real manifest wiring |
| 3. Namespace Consistency | POS-INV-19 / existing namespace policy | Do not rename technical `plasticos_*` identifiers for the outward RecycleOS brand |
| 4. Deterministic Seed Doctrine | POS-INV-19; accepted data/ADR owners | **CONFLICT TO ADJUDICATE:** existing blanket seed `noupdate=1` language versus v3 contextual lifecycle rule; no automatic waiver of v2.2 until admitted |
| 5. Graph Isolation Boundary | POS-INV-17/18 | **CONFLICT TO ADJUDICATE:** old safe empty-return handling must not be represented as a successful canonical inference in the new durable failure-evidence contract |
| 6. Partner Architecture Integrity | POS-INV-01/02/05/19 | Preserve native `res.partner` fields and facility-profile model specifics in existing implementation policy |
| 7. Layer Dependency Direction | POS-INV-19 plus existing layer ownership | Preserve the current repository layer graph absent authorized ADR change |
| 8. Security Model Completeness | POS-INV-05/19 | **REVIEW REQUIRED:** existing per-model ACL/record-rule formula versus draft's no blanket ACL formula; do not weaken effective isolation |
| 9. External ID Referential Integrity | POS-INV-19 | Preserve XML ID and load-order checks |
| 10. Test Isolation | POS-INV-20 | Preserve safe DB isolation and transactional rollback requirements |
| 11. API Dependency Isolation | POS-INV-17/18/20 | Keep runtime isolation, timeout and secrets protections; failed attempts must not silently become successful outcomes |
| 12. Model Name Uniqueness | POS-INV-19 | Preserve `_name` uniqueness and Odoo registry checks |
| 13. Field Reference Safety | POS-INV-19 | Preserve field and related-path checks |
| 14. Migration Safety | POS-INV-19/20 | Preserve non-destructive, idempotent approved migrations |
| 15. Cron Job Discipline | POS-INV-15/19/20 | Preserve approved activation and cron checks pending explicit changes |
| 16. Cross-Addon Import Safety | POS-INV-19 | Preserve boot/registry import-order checks |
| 17. File Wiring Completeness | POS-INV-19 | Preserve `__init__` and manifest registration checks |
| 18. XML View Compatibility | POS-INV-19 | Preserve Odoo 19 XML/view compatibility checks |
| 19. Single External Intelligence Authority | POS-INV-17/18 | Keep canonical Gate/SDK transport and no shadow matcher |
| 20. Legacy Vendor Identifier Prohibition | BAN001 | **Word-for-word unchanged** in the v3.1 draft; existing canonical blocking checker remains source authority |

## Admission stop conditions

The identified conflicting or compressed details are not silently superseded by a newer draft or by this ZIP. A future authorized constitutional update must compare every normative clause, demonstrate no loss of enforcement, obtain explicit operator approval and prove scoped code/test/CI alignment. The v3.1 draft and this mapping are planning candidates only.

---
paths:
  - "plasticos_*/security/**"
  - "plasticos_security_base/**"
---
# Security — Path-Scoped Pointer

**Authority:** `71-plasticos-security-model.mdc` · `INVARIANTS.md` § Security

**Before ANY ACL edit:** `cat` the full CSV · check redundancy · match id-column format · never mix prefix styles.

**Every new model:** `security/ir.model.access.csv` in the **same module** that defines the model.

**Forbidden:** `sudo()` without inline justification · custom partner role booleans (use `customer_rank`/`supplier_rank`).

---
paths:
  - "plasticos_buyer_match_engine/**/*.py"
  - "plasticos_matching/**/*.py"
  - "plasticos_enrichment/**/*.py"
---
# Neo4j Boundary — Path-Scoped Pointer

**Authority:** `INVARIANTS.md` § Neo4j Integration · `87-plasticos-code-graph-rag.mdc` (code-graph ≠ Neo4j runtime)

- Odoo = transactions · Neo4j = scoring augmentation only
- Lazy-init driver · graph failures must not block Odoo startup
- ❌ Neo4j imports on registry load path · ❌ ORM constraints from graph results

**Pattern:** service class with try/except fallback to Odoo-only scoring (`graph_service.py`).

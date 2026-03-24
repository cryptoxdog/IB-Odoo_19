---
paths:
  - "plasticos_buyer_match_engine/**/*.py"
  - "plasticos_matching/**/*.py"
  - "plasticos_enrichment/**/*.py"
---
# Neo4j Integration Boundary

## Architecture
- Neo4j is used for graph-based scoring in `plasticos_buyer_match_engine`
- Odoo handles all transactional data — Neo4j is read-only augmentation
- Graph logic lives in service classes, NOT in Odoo model methods

## Hard Rules
- ✅ Graph logic isolated in service classes (e.g., `graph_service.py`)
- ✅ Graph failures wrapped in safe boundaries (try/except with graceful fallback)
- ✅ Neo4j connection lazy-initialized, never at import time
- ❌ Never import Neo4j driver at module top level (blocks Odoo registry)
- ❌ Never block Odoo startup on Neo4j connection failure
- ❌ Never write transaction data to Neo4j — Odoo is source of truth
- ❌ Never reference Neo4j results in Odoo ORM constraints or computed fields

## Pattern
```python
# ✅ GOOD — lazy connection, safe boundary
class GraphScoringService:
    def __init__(self):
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(uri, auth=(user, pwd))
            except Exception:
                _logger.warning("Neo4j unavailable — scoring will use Odoo-only fallback")
                return None
        return self._driver

    def score_matches(self, intake_id):
        driver = self._get_driver()
        if not driver:
            return []  # Graceful fallback
```

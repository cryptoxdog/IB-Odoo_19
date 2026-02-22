# Execute Cypher Query — Integrated

This spec is **integrated** into `plasticos_buyer_match_engine`.

- **Implementation:** `models/graph_service.py` — `PlasticosGraphService`
- **Pool:** `services/neo4j_pool.py` — `Neo4jConnectionPool` (no dependency on `plasticos_graph`)

## Public API

```python
# From any model or wizard with access to env:
self.env["plasticos.graph.service"].execute_cypher_query(
    query="MATCH (n:Facility) RETURN n.facility_id AS id LIMIT 5",
    params=None,
    metadata={"name": "my_query"},
)
# Returns: list[dict] (one dict per row via record.data())
# Raises: UserError if Neo4j not configured or query fails
```

## Config (System Parameters or .env)

Uri, user, and password are read from **System Parameters** first; if empty, **environment variables** are used (e.g. from `.env`):

| Source | Uri | User | Password |
|--------|-----|------|----------|
| System params | `plasticos_graph.neo4j_uri` | `plasticos_graph.neo4j_user` | `plasticos_graph.neo4j_password` |
| .env | `NEO4J_URI` or `NEO4J_URL` | `NEO4J_USER` | `NEO4J_PASSWORD` |

Other keys (pool, timeouts) from System Parameters only:

| Key | Purpose |
|-----|---------|
| `plasticos_graph.neo4j_pool_size` | Pool size (default 25) |
| `plasticos_graph.neo4j_connection_timeout` | Connection timeout seconds (default 30) |
| `plasticos_graph.neo4j_max_connection_lifetime` | Max connection lifetime seconds (default 3600) |
| `plasticos_graph.neo4j_cb_failure_threshold` | Circuit breaker failure threshold (default 5) |
| `plasticos_graph.neo4j_cb_timeout` | Circuit breaker open timeout seconds (default 60) |

## Behavior

- **`execute_cypher_query()`** — Uses `_get_pool()`; raises `UserError` when Neo4j is not configured or when the query / Neo4j fails (e.g. `ServiceUnavailable`, `Neo4jError`). Use for explicit Cypher runs (e.g. server action, script, debug).
- **`_execute_cypher()`** — Uses `_get_driver()` (optional pool); returns `[]` when config missing or on failure. Used internally by sync and match so hooks/cron do not break when Neo4j is absent.

Metrics (`get_metrics()`) from the original spec are not used in this module; logging is used instead. To add metrics later, wrap the session run in a metrics context inside `execute_cypher_query()`.

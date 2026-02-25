"""Neo4j single-instance driver with connection pooling.

Creates one ``neo4j.Driver`` per Odoo registry (database) and reuses it
across all requests.  The driver's internal pool handles connection
lifecycle.  A simple retry wrapper guards against transient network
errors.
"""

import logging
import threading

from neo4j import GraphDatabase

from odoo import models

_logger = logging.getLogger(__name__)

_driver_lock = threading.Lock()
_driver_cache: dict = {}  # keyed by db_name


class Neo4jDriver(models.AbstractModel):
    _name = "plasticos.neo4j.driver"
    _description = "Neo4j Driver (Pooled)"

    def _get_driver(self):
        """Return a cached ``neo4j.Driver`` for the current Odoo database."""
        db_name = self.env.cr.dbname
        if db_name not in _driver_cache:
            with _driver_lock:
                if db_name not in _driver_cache:
                    config = self.env["plasticos.neo4j.config"].sudo().search([], limit=1)
                    if not config:
                        raise ValueError("No Neo4j configuration found in plasticos.neo4j.config")
                    _driver_cache[db_name] = GraphDatabase.driver(
                        config.uri,
                        auth=(config.username, config.password),
                        max_connection_pool_size=50,
                    )
                    _logger.info("Neo4j driver created for db=%s uri=%s", db_name, config.uri)
        return _driver_cache[db_name]

    def execute(self, query, params=None, max_retries=2):
        """Execute a Cypher query with automatic retry on transient errors."""
        driver = self._get_driver()
        last_exc = None
        for attempt in range(1, max_retries + 2):
            try:
                with driver.session() as session:
                    return session.run(query, params or {}).data()
            except Exception as exc:
                last_exc = exc
                _logger.warning(
                    "Neo4j query attempt %d/%d failed: %s",
                    attempt, max_retries + 1, exc,
                )
                if attempt > max_retries:
                    raise
        raise last_exc  # pragma: no cover
